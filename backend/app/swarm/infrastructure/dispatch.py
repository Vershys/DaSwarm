"""Transactional outbox relay. Broker outages never discard persisted work."""
import os
import time
from celery import Celery
from redis import Redis
from sqlalchemy import select, and_
from app.swarm.infrastructure.database import Database, outbox, jobs, now
from app.swarm.application.service import Service
from app.swarm.application.worker import Worker

broker=os.environ.get('SWARM_REDIS_URL','redis://redis:6379/1')
celery=Celery('manu_swarm',broker=broker)
celery.conf.update(task_acks_late=True,task_reject_on_worker_lost=True,worker_prefetch_multiplier=1,
                   broker_connection_retry_on_startup=True, broker_connection_timeout=3, task_publish_retry=False)

@celery.task(name='swarm.execute',acks_late=True)
def execute(task_id):
    service=Service(Database()); return Worker(service).run_one(task_id)

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
