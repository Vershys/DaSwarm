"""Authenticated control plane and durable-cursor WebSocket transport."""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import select, func, and_, or_
from app.swarm.application.service import Service, row
from app.swarm.domain.contracts import Command, Conflict, Forbidden, NotFound, BLUEPRINT
from app.swarm.infrastructure.database import Database, objects, edges, events, jobs, scores, outbox
from app.swarm.infrastructure.media import Media
from app.swarm.infrastructure.providers import capabilities

def flag(name,default=True): return os.environ.get(name,str(default)).lower()=='true'

def install(app,service=None,auth=None):
    service=service or Service(Database());app.state.swarm=service
    async def local_auth(request:Request):
        # Standalone host binds loopback. Containers must use upstream auth or explicit local-only mode.
        if not flag('SWARM_LOCAL_ONLY',False): raise HTTPException(403,'Configure upstream authentication')
        return 'local-operator'
    authorization=auth or local_auth
    router=APIRouter(prefix='/api/v1/swarm',dependencies=[Depends(authorization)])
    def enabled():
        if not flag('SWARM_ENABLED'): raise HTTPException(404,'Swarm disabled')
    router.dependencies.append(Depends(enabled))
    @app.exception_handler(Conflict)
    async def conflict(request,exc): return JSONResponse(status_code=409,content={'detail':str(exc)})
    @app.exception_handler(Forbidden)
    async def forbidden(request,exc): return JSONResponse(status_code=403,content={'detail':str(exc)})
    @app.exception_handler(NotFound)
    async def missing(request,exc): return JSONResponse(status_code=404,content={'detail':str(exc)})
    @app.exception_handler(ValueError)
    async def invalid(request,exc): return JSONResponse(status_code=422,content={'detail':str(exc)})
    @router.get('/health')
    def health():
        with service.db.engine.connect() as c:
            seq=c.execute(select(func.max(events.c.sequence))).scalar() or 0
        caps=capabilities()
        return {'status':'ok','last_sequence':seq,'mode':'live','real_publishing':caps['publishing']['real']}

    @router.get('/capabilities')
    def capability_registry():
        return capabilities()
    @router.get('/config')
    def config():
        with service.db.engine.connect() as c: return {**service.settings(c),'ontology':BLUEPRINT,'capabilities':capabilities()}
    @router.post('/commands/execute')
    def command(cmd:Command,actor=Depends(authorization)):
        if cmd.action=='synthesize' and not flag('SWARM_SYNTHESIS_ENABLED'): raise Forbidden('Synthesis disabled')
        return service.execute(cmd,str(getattr(actor,'id',actor)))
    @router.post('/objects/query')
    @router.post('/candidates/query')
    def query(body:dict,request:Request):
        with service.db.engine.connect() as c:
            kind='Candidate' if request.url.path.endswith('/candidates/query') else body.get('object_type')
            return {'items':service.query(c,kind,body.get('search',''),body.get('status'),body.get('limit',100),body.get('offset',0),body.get('filters')),'limit':min(body.get('limit',100),200)}
    @router.get('/objects/{id}')
    def get_object(id:str):
        with service.db.engine.connect() as c: return service.get(c,id)
    @router.get('/objects/{id}/links')
    def links(id:str):
        with service.db.engine.connect() as c: return [dict(x) for x in c.execute(select(edges).where(or_(edges.c.from_object_id==id,edges.c.to_object_id==id)).limit(500)).mappings()]
    @router.get('/objects/{id}/timeline')
    def timeline(id:str):
        with service.db.engine.connect() as c: return service.timeline(c,id)
    @router.get('/objects/{id}/trace')
    def object_trace(id:str):
        with service.db.engine.connect() as c:
            ev=service.timeline(c,id)
            return service.trace(c,ev[0]['trace_id']) if ev else []
    @router.get('/traces/{trace_id}')
    def trace(trace_id:str):
        with service.db.engine.connect() as c: return service.trace(c,trace_id)
    @router.get('/replay/snapshot')
    def replay(at:str):
        if not flag('SWARM_REPLAY_ENABLED'): raise Forbidden('Replay disabled')
        datetime.fromisoformat(at)
        with service.db.engine.connect() as c: return service.replay(c,at)
    @router.post('/graph/neighborhood')
    @router.post('/graph/matrix')
    def graph(body:dict):
        if not flag('SWARM_GRAPH_ENABLED'): raise Forbidden('Graph disabled')
        with service.db.engine.connect() as c: return service.neighborhood(c,body['object_id'],body.get('depth',2),body.get('limit',500),body.get('relations'),body.get('at'))
    @router.post('/graph/path')
    def path(body:dict):
        with service.db.engine.connect() as c:
            graph=service.neighborhood(c,body['from_id'],4,500)
        adjacency={n['id']:[] for n in graph['nodes']}
        for e in graph['edges']:
            adjacency[e['from_object_id']].append(e['to_object_id']);adjacency[e['to_object_id']].append(e['from_object_id'])
        pending=[[body['from_id']]];seen=set()
        for p in pending:
            if p[-1]==body['to_id']: return {'path':p,'truncated':graph['truncated']}
            if p[-1] in seen: continue
            seen.add(p[-1]);pending.extend(p+[n] for n in adjacency.get(p[-1],[]) if n not in seen)
        return {'path':[],'truncated':graph['truncated']}
    @router.get('/operations/summary')
    def summary():
        with service.db.engine.connect() as c:
            return {'objects':dict(c.execute(select(objects.c.object_type,func.count()).group_by(objects.c.object_type)).all()),
              'tasks':dict(c.execute(select(jobs.c.status,func.count()).group_by(jobs.c.status)).all()),
              'pending_outbox':c.execute(select(func.count()).select_from(outbox).where(outbox.c.dispatched_at.is_(None))).scalar(),
              'last_sequence':c.execute(select(func.max(events.c.sequence))).scalar() or 0}
    @router.get('/queues')
    def queues():
        with service.db.engine.connect() as c:
            counts=c.execute(select(jobs.c.task_type,jobs.c.status,func.count().label('count')).group_by(jobs.c.task_type,jobs.c.status)).mappings()
            return {'counts':[dict(x) for x in counts],'paused':service.settings(c)['data']['paused_queues']}
    @router.get('/agents/telemetry')
    def agent_telemetry():
        """Live operator view over task executors.

        Heartbeat freshness is derived from the same lease that fences task writes,
        so a green agent card means the worker is still renewing authority to act.
        """
        now_ts=time.time()
        with service.db.engine.connect() as c:
            cfg=service.settings(c)['data']
            lease_seconds=float(cfg['lease_seconds'])
            workers=[dict(x) for x in c.execute(select(objects).where(objects.c.object_type=='Worker').order_by(objects.c.created_at)).mappings()]
            all_jobs=[dict(x) for x in c.execute(select(jobs).where(jobs.c.worker_id.is_not(None)).order_by(jobs.c.created_at.desc())).mappings()]
            by_worker={}
            for job in all_jobs:
                by_worker.setdefault(job['worker_id'],[]).append(job)
            agents=[]
            role_names={
                'browser':'Discovery',
                'gpu_media':'Media analysis',
                'render':'Rendering',
                'publisher':'Publishing',
                'io':'Ingest / I/O',
                'cpu_media':'Media processing',
                'llm':'Reasoning',
            }
            for worker in workers:
                history=by_worker.get(worker['id'],[])
                active=next((j for j in history if j['status']=='RUNNING'),None)
                latest=active or (history[0] if history else None)
                if active:
                    heartbeat_at=float(active['lease_until'])-lease_seconds
                    heartbeat_age=max(0.0,now_ts-heartbeat_at)
                    lease_remaining=max(0.0,float(active['lease_until'])-now_ts)
                    state='WORKING' if lease_remaining>0 else 'STALE'
                else:
                    heartbeat_at=None
                    heartbeat_age=None
                    lease_remaining=0.0
                    state='IDLE'
                target=None
                task_obj=None
                started_at=None
                recent=[]
                if latest:
                    try:
                        task_obj=service.get(c,latest['task_id'])
                    except Exception:
                        task_obj=None
                    ref=latest.get('object_ref') or {}
                    object_id=ref.get('objectId')
                    if object_id:
                        try:
                            target=service.get(c,object_id)
                        except Exception:
                            target=None
                    start_ev=row(c.execute(select(events).where(and_(
                        events.c.object_id==latest['task_id'],
                        events.c.event_type=='TASK_STARTED'
                    )).order_by(events.c.sequence.desc()).limit(1)))
                    started_at=start_ev['timestamp'] if start_ev else None
                    trace_rows=c.execute(select(events).where(events.c.trace_id==latest['trace_id']).order_by(events.c.sequence.desc()).limit(8)).mappings()
                    recent=[{
                        'event_type':x['event_type'],
                        'timestamp':x['timestamp'],
                        'object_id':x['object_id'],
                        'object_type':x['object_type'],
                        'severity':x['severity'],
                    } for x in trace_rows]
                assigned=len(history)
                succeeded=sum(1 for j in history if j['status']=='SUCCEEDED')
                failed=sum(1 for j in history if j['status'] in ('WAITING_RETRY','DEAD_LETTER'))
                resource=(latest or {}).get('resource_class')
                agents.append({
                    'id':worker['id'],
                    'label':worker['title'],
                    'kind':'worker',
                    'role':role_names.get(resource,resource or 'Execution'),
                    'state':state,
                    'pid':worker['metadata'].get('pid'),
                    'resource_class':resource,
                    'queue':('swarm.'+resource) if resource else None,
                    'task':None if not latest else {
                        'id':latest['task_id'],
                        'type':latest['task_type'],
                        'status':latest['status'],
                        'attempt':latest['attempt'],
                        'max_attempts':latest['max_attempts'],
                        'priority':latest['priority'],
                        'started_at':started_at,
                        'payload':latest.get('payload') or {},
                    },
                    'target':None if not target else {
                        'id':target['id'],
                        'object_type':target['object_type'],
                        'title':target['title'],
                        'status':target['status'],
                    },
                    'trace_id':(latest or {}).get('trace_id'),
                    'heartbeat_at':heartbeat_at,
                    'heartbeat_age_seconds':heartbeat_age,
                    'lease_remaining_seconds':lease_remaining,
                    'stats':{
                        'assigned':assigned,
                        'succeeded':succeeded,
                        'retry_or_dead_letter':failed,
                    },
                    'recent_activity':recent,
                })
            working=sum(1 for a in agents if a['state']=='WORKING')
            stale=sum(1 for a in agents if a['state']=='STALE')
            return {
                'server_time':now_ts,
                'lease_seconds':lease_seconds,
                'summary':{
                    'known_agents':len(agents),
                    'working':working,
                    'idle':sum(1 for a in agents if a['state']=='IDLE'),
                    'stale':stale,
                },
                'agents':agents,
            }
    def collection(kind):
        def endpoint():
            with service.db.engine.connect() as c: return service.query(c,kind)
        return endpoint
    for path,kind in [('accounts','Account'),('workers','Worker'),('trends','TrendCluster'),('experiments','Experiment')]:
        router.add_api_route('/'+path,collection(kind),methods=['GET'])
    for path in ('candidates','accounts','workers','tasks','trends','compositions','experiments'):
        router.add_api_route('/'+path+'/{id}',get_object,methods=['GET'])
    @router.get('/candidates/{id}/atoms')
    def atoms(id:str):
        with service.db.engine.connect() as c:
            ids=c.execute(select(edges.c.to_object_id).where(and_(edges.c.from_object_id==id,edges.c.edge_type=='HAS_ATOM'))).scalars()
            return [service.get(c,x) for x in ids]
    @router.get('/accounts/{id}/audience-genome')
    def genome(id:str):
        with service.db.engine.connect() as c:
            account=service.get(c,id);gid=account['metadata'].get('audience_genome_id')
            return service.get(c,gid) if gid else None
    @router.get('/accounts/{id}/performance')
    def performance(id:str):
        with service.db.engine.connect() as c:
            ids=c.execute(select(edges.c.to_object_id).where(and_(edges.c.from_object_id==id,edges.c.edge_type=='MEASURED_BY'))).scalars()
            return [service.get(c,x) for x in ids]
    @router.get('/scores/{id}')
    def score(id:str):
        with service.db.engine.connect() as c: return [dict(x) for x in c.execute(select(scores).where(scores.c.object_id==id)).mappings()]
    @router.get('/media/{key}')
    def media(key:str):
        path=Media().path(key)
        if not path.exists(): raise NotFound('Asset not found')
        return FileResponse(path,media_type='video/mp4')
    app.include_router(router)
    @app.websocket('/api/v1/ws/swarm')
    async def stream(ws:WebSocket):
        if not flag('SWARM_ENABLED') or not flag('SWARM_REALTIME_ENABLED'):
            await ws.close(code=1008);return
        # Upstream auth is shared through a dependency adapter supplied by integration.py.
        ws_auth=getattr(app.state,'swarm_ws_auth',None)
        if ws_auth:
            try: await ws_auth(ws)
            except Exception: await ws.close(code=1008);return
        elif not flag('SWARM_LOCAL_ONLY',False): await ws.close(code=1008);return
        origin=ws.headers.get('origin')
        if origin and origin.split('://',1)[-1]!=ws.headers.get('host'):
            await ws.close(code=1008);return
        try: cursor=max(0,int(ws.query_params.get('last_sequence','0')))
        except ValueError: await ws.close(code=1008);return
        await ws.accept()
        try:
            while True:
                def batch():
                    with service.db.engine.connect() as c:
                        return [dict(x) for x in c.execute(select(events).where(events.c.sequence>cursor).order_by(events.c.sequence).limit(200)).mappings()]
                entries=await asyncio.to_thread(batch)
                for ev in entries:
                    await ws.send_json({'type':'swarm.event','sequence':ev['sequence'],'topic':'objects','serverTime':ev['timestamp'],'event':ev})
                    cursor=ev['sequence']
                if not entries:
                    await ws.send_json({'type':'heartbeat','sequence':cursor})
                    await asyncio.sleep(.25)
        except (WebSocketDisconnect,RuntimeError): pass
    return service

@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(app.state.swarm.initialize)
    yield

def create_app(service=None):
    app=FastAPI(title='Manu-Swarm Control Plane',lifespan=lifespan)
    install(app,service)
    return app
