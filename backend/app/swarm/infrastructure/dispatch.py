"""Transactional outbox relay. Broker outages never discard persisted work."""
import os
import time
import socket
import json
import threading
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from redis import Redis
from sqlalchemy import select, and_
from app.swarm.infrastructure.database import Database, outbox, jobs, now
from app.swarm.application.service import Service
from app.swarm.application.worker import Worker

broker=os.environ.get('SWARM_REDIS_URL','redis://redis:6379/1')
celery=Celery('manu_swarm',broker=broker)
celery.conf.update(task_acks_late=True,task_reject_on_worker_lost=True,worker_prefetch_multiplier=1,
                   broker_connection_retry_on_startup=True, broker_connection_timeout=3, task_publish_retry=False)

_agent_state={'state':'STARTING','task_id':None,'task_type':None,'target_id':None,'resource_class':None}
_agent_lock=threading.Lock()
_agent_stop=threading.Event()
_agent_thread=None
_agent_started=time.time()
_agent_last_cpu=time.process_time()
_agent_last_wall=time.time()

def _agent_id():
    return f'celery:{socket.gethostname()}:{os.getpid()}'

def _process_sensors():
    global _agent_last_cpu,_agent_last_wall
    wall=time.time()
    cpu=time.process_time()
    wall_delta=max(wall-_agent_last_wall,0.001)
    cpu_percent=max(0.0,min(100.0,(cpu-_agent_last_cpu)/wall_delta*100.0))
    _agent_last_cpu=cpu
    _agent_last_wall=wall
    rss_mb=None
    try:
        with open('/proc/self/statm',encoding='utf-8') as statm:
            pages=int(statm.read().split()[1])
        rss_mb=pages*os.sysconf('SC_PAGE_SIZE')/1024/1024
    except Exception:
        pass
    return {
        'cpu_percent':round(cpu_percent,1),
        'rss_mb':round(rss_mb,1) if rss_mb is not None else None,
        'process_uptime_seconds':round(max(0.0,wall-_agent_started),1),
        'threads':threading.active_count(),
    }

def _agent_payload():
    with _agent_lock:
        state=dict(_agent_state)
    return {
        'id':_agent_id(),
        'hostname':socket.gethostname(),
        'pid':os.getpid(),
        'role':os.environ.get('SWARM_AGENT_ROLE','Execution'),
        'queues':[x for x in os.environ.get('SWARM_AGENT_QUEUES','').split(',') if x],
        'state':state['state'],
        'task_id':state.get('task_id'),
        'task_type':state.get('task_type'),
        'target_id':state.get('target_id'),
        'resource_class':state.get('resource_class'),
        'heartbeat_at':time.time(),
        'sensors':_process_sensors(),
    }

def _presence_loop():
    client=Redis.from_url(broker,socket_connect_timeout=2,socket_timeout=2)
    while not _agent_stop.wait(1.0):
        try:
            payload=_agent_payload()
            client.setex('swarm:agent:'+payload['id'],5,json.dumps(payload,separators=(',',':')))
        except Exception:
            pass

@worker_process_init.connect
def _register_agent(**_kwargs):
    global _agent_thread,_agent_started,_agent_last_cpu,_agent_last_wall
    _agent_started=time.time()
    _agent_last_cpu=time.process_time()
    _agent_last_wall=time.time()
    _agent_stop.clear()
    with _agent_lock:
        _agent_state.update(state='IDLE',task_id=None,task_type=None,target_id=None,resource_class=None)
    _agent_thread=threading.Thread(target=_presence_loop,daemon=True,name='swarm-agent-heartbeat')
    _agent_thread.start()

@worker_process_shutdown.connect
def _unregister_agent(**_kwargs):
    _agent_stop.set()
    try:
        Redis.from_url(broker,socket_connect_timeout=1,socket_timeout=1).delete('swarm:agent:'+_agent_id())
    except Exception:
        pass

@celery.task(name='swarm.execute',acks_late=True)
def execute(task_id):
    service=Service(Database())
    worker_id=_agent_id()
    try:
        with service.db.engine.connect() as c:
            job=c.execute(select(jobs).where(jobs.c.task_id==task_id)).mappings().first()
        with _agent_lock:
            _agent_state.update(
                state='WORKING',
                task_id=task_id,
                task_type=job['task_type'] if job else None,
                target_id=(job['object_ref'] or {}).get('objectId') if job else None,
                resource_class=job['resource_class'] if job else None,
            )
        return Worker(service,worker_id=worker_id).run_one(task_id)
    finally:
        with _agent_lock:
            _agent_state.update(state='IDLE',task_id=None,task_type=None,target_id=None,resource_class=None)
        service.db.engine.dispose()

class Dispatcher:
    def __init__(self,s,publish=None):
        self.s=s; self.publish=publish or self.transport
    def transport(self,entry):
        if entry['topic']=='event':
            import json
            Redis.from_url(broker,socket_connect_timeout=2,socket_timeout=2).xadd(os.environ.get('SWARM_REDIS_STREAM','swarm:events'),{'event':json.dumps(entry['payload'])},maxlen=10000,approximate=True)
        else:
            celery.send_task('swarm.execute',args=[entry['payload']['task_id']],queue='swarm.'+entry['payload']['resource_class'])
    def once(self):
        with self.s.transaction() as c:
            entries=list(c.execute(select(outbox).where(outbox.c.dispatched_at.is_(None)).order_by(outbox.c.created_at).limit(100).with_for_update(skip_locked=True)).mappings())
            for entry in entries:
                try:
                    self.publish(entry)
                except Exception as exc:
                    c.execute(outbox.update().where(outbox.c.id==entry['id']).values(attempts=entry['attempts']+1,last_error=type(exc).__name__))
                    break
                c.execute(outbox.update().where(outbox.c.id==entry['id']).values(dispatched_at=now(),attempts=entry['attempts']+1,last_error=None))
        return len(entries)
    def requeue_due(self):
        # Republishing is deliberately at least once. SQL lease fencing chooses the winner.
        with self.s.transaction() as c:
            due=list(c.execute(select(jobs).where(and_(jobs.c.status.in_(['QUEUED','WAITING_RETRY','RUNNING']),jobs.c.not_before<=time.time(),jobs.c.lease_until<time.time(),jobs.c.cancelled==0)).limit(200)).mappings())
            for job in due:
                self.s.enqueue_outbox(c,'task',job['idempotency_key'],{'task_id':job['task_id'],'resource_class':job['resource_class']})

if __name__=='__main__':
    service=Service(Database()); service.initialize(); dispatcher=Dispatcher(service);tick=0
    while True:
        try:
            dispatcher.once()
            if tick%20==0: dispatcher.requeue_due()
        except Exception:
            # Never print connection strings or provider exception contents.
            import logging
            logging.getLogger('swarm').warning('Dispatcher unavailable; durable outbox retained')
        tick+=1;time.sleep(.5)
