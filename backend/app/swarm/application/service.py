"""Transactional command, ontology, query and event services."""
import hashlib
import json
import os
import time
from contextlib import contextmanager
from sqlalchemy import select, update, func, or_, and_
from app.swarm.infrastructure.database import (Database, objects, edges, events, outbox, idem,
    jobs, config, projections, scores, now, uid)
from app.swarm.domain.contracts import (BLUEPRINT, STATES, RELATIONS, RESOURCES, DEFAULT_CONFIG,
    Conflict, Forbidden, NotFound, validate_metadata, validate_transition)

def row(result):
    r=result.mappings().first()
    return dict(r) if r else None

class Service:
    def __init__(self, db: Database): self.db=db
    def initialize(self):
        self.db.migrate()
        with self.db.engine.begin() as c:
            if not row(c.execute(select(config))): c.execute(config.insert().values(id=1,version=1,data=DEFAULT_CONFIG))
    @contextmanager
    def transaction(self):
        with self.db.engine.begin() as c:
            # Serialize writes to establish commit-ordered event cursors. Revisit only after measured load.
            c.execute(select(config.c.id).where(config.c.id==1).with_for_update()).first()
            yield c
    def settings(self,c): return row(c.execute(select(config)))
    def get(self,c,id):
        result=row(c.execute(select(objects).where(objects.c.id==id)))
        if not result: raise NotFound('Object not found')
        return result
    def event(self,c,kind,obj,trace=None,cause=None,payload=None,actor='worker',actor_id=None):
        trace=trace or uid(); eid=uid()
        data=validate_metadata(dict(payload or {}))
        if obj: data['snapshot']=obj
        validate_metadata(data)
        values=dict(event_id=eid,event_type=kind,object_id=obj['id'] if obj else None,
            object_type=obj['object_type'] if obj else None,actor_type=actor,actor_id=actor_id,
            timestamp=now(),trace_id=trace,correlation_id=trace,causation_id=cause,
            severity='info',payload=data,schema_version=1,idempotency_key=None)
        seq=c.execute(events.insert().values(**values)).inserted_primary_key[0]
        ev=dict(sequence=seq,**values)
        if obj:
            old=row(c.execute(select(projections).where(projections.c.object_id==obj['id'])))
            state=dict(object_id=obj['id'],object_type=obj['object_type'],last_sequence=seq,state=obj)
            if old: c.execute(projections.update().where(projections.c.object_id==obj['id']).values(**state))
            else: c.execute(projections.insert().values(**state))
        self.enqueue_outbox(c,'event',eid,ev)
        return ev
    def enqueue_outbox(self,c,topic,key,payload):
        c.execute(outbox.insert().values(id=uid(),topic=topic,message_key=key,payload=payload,created_at=now(),attempts=0))
    def create(self,c,kind,title,status=None,metadata=None,trace=None,cause=None,event_type=None,id=None):
        if kind not in BLUEPRINT['object_types']: raise ValueError('Unknown object type')
        state=STATES[kind]['initial'] if kind in STATES else 'ACTIVE'
        if status and kind in STATES and status!=state: raise Conflict('Create at initial state')
        obj=dict(id=id or uid(),object_type=kind,version=1,title=title,status=status or state,
                 metadata=validate_metadata(metadata or {}),tags=[],created_at=now(),updated_at=now())
        c.execute(objects.insert().values(**obj))
        ev=self.event(c,event_type or f'{kind.upper()}_CREATED',obj,trace,cause)
        return obj,ev
    def change(self,c,id,version,trace=None,cause=None,event_type='OBJECT_UPDATED',actor='worker',actor_id=None,**patch):
        obj=self.get(c,id)
        if obj['version']!=version: raise Conflict('Stale object version; refresh and retry')
        if patch.get('status') and patch['status']!=obj['status']:
            validate_transition(obj['object_type'],obj['status'],patch['status'])
        if set(patch)-{'status','metadata','title','tags'}: raise ValueError('Unsupported fields')
        validate_metadata(patch)
        obj.update(patch); obj.update(version=version+1,updated_at=now())
        res=c.execute(objects.update().where(and_(objects.c.id==id,objects.c.version==version)).values(**obj))
        if res.rowcount!=1: raise Conflict('Concurrent write')
        return obj,self.event(c,event_type,obj,trace,cause,actor=actor,actor_id=actor_id)
    def link(self,c,source,target,kind,trace,cause=None):
        a=self.get(c,source); b=self.get(c,target)
        contract=RELATIONS.get(kind)
        if not contract or a['object_type'] not in contract['from'] or b['object_type'] not in contract['to']:
            raise ValueError('Invalid ontology relationship')
        old=row(c.execute(select(edges).where(and_(edges.c.from_object_id==source,edges.c.to_object_id==target,edges.c.edge_type==kind))))
        if old: return old
        edge=dict(id=uid(),from_object_id=source,to_object_id=target,edge_type=kind,metadata={},
                  created_at=now(),valid_from=now(),valid_to=None)
        c.execute(edges.insert().values(**edge)); self.event(c,'EDGE_CREATED',None,trace,cause,{'edge':edge})
        return edge
    def schedule(self,c,kind,obj,trace,cause,payload=None):
        key=f'{trace}:{kind}:{obj["id"]}'
        old=row(c.execute(select(jobs).where(jobs.c.idempotency_key==key)))
        if old: return old['task_id']
        task,ev=self.create(c,'Task',kind,metadata={'task_type':kind,'object_ref':{'objectId':obj['id'],'objectType':obj['object_type']}},trace=trace,cause=cause,event_type='TASK_CREATED')
        c.execute(jobs.insert().values(task_id=task['id'],task_type=kind,
            object_ref={'objectId':obj['id'],'objectType':obj['object_type']},trace_id=trace,correlation_id=trace,
            causation_event_id=ev['event_id'],idempotency_key=key,priority=0,attempt=0,
            max_attempts=self.settings(c)['data']['max_attempts'],resource_class=RESOURCES[kind],created_at=now(),
            not_before=0,lease_until=0,lease_token=None,worker_id=None,cancelled=0,status='QUEUED',payload=payload or {}))
        self.enqueue_outbox(c,'task',key,{'task_id':task['id'],'resource_class':RESOURCES[kind]})
        return task['id']
    def query(self,c,kind=None,search='',status=None,limit=100,offset=0,filters=None):
        q=select(projections.c.state).where(projections.c.object_type==kind) if kind else select(projections.c.state)
        # Filter domain table in SQL; never materialize the whole ontology in the browser.
        ids=select(objects.c.id)
        if search: ids=ids.where(objects.c.title.ilike('%'+search[:200]+'%'))
        if status: ids=ids.where(objects.c.status==status)
        if filters:
            def predicate(f):
                op=f.get('op'); prop=f.get('property')
                if op in ('and','or'):
                    return (and_ if op=='and' else or_)(*[predicate(x) for x in f.get('children',[])])
                if prop not in ('object_type','status','title','version'): raise ValueError('Unsupported filter property')
                col=objects.c[prop]
                if op=='eq': return col==f['value']
                if op=='in': return col.in_(f['values'])
                if op=='gt': return col>f['value']
                if op=='lt': return col<f['value']
                raise ValueError('Unsupported filter operation')
            ids=ids.where(predicate(filters))
        q=q.where(projections.c.object_id.in_(ids)).order_by(projections.c.last_sequence.desc()).offset(max(0,offset)).limit(min(max(limit,1),200))
        return list(c.execute(q).scalars())
    def timeline(self,c,id): return [dict(x) for x in c.execute(select(events).where(events.c.object_id==id).order_by(events.c.sequence).limit(2000)).mappings()]
    def trace(self,c,trace_id): return [dict(x) for x in c.execute(select(events).where(events.c.trace_id==trace_id).order_by(events.c.sequence).limit(5000)).mappings()]
    def replay(self,c,at):
        # Windowed SQL projection: latest durable snapshot per object at a timestamp.
        ranked=select(events.c.payload,func.row_number().over(partition_by=events.c.object_id,order_by=events.c.sequence.desc()).label('rn')).where(and_(events.c.timestamp<=at,events.c.object_id.is_not(None))).subquery()
        snapshots=[x['snapshot'] for x in c.execute(select(ranked.c.payload).where(ranked.c.rn==1).limit(200)).scalars() if 'snapshot' in x]
        return {'mode':'REPLAY','at':at,'objects':snapshots,'limit':200,'read_only':True}
    def neighborhood(self,c,id,depth=2,limit=500,relations=None,at=None):
        limit=min(max(limit,1),self.settings(c)['data']['graph_limit'],2000); depth=min(max(depth,0),4)
        selected={id}; links={}; frontier={id}; truncated=False
        for _ in range(depth):
            if not frontier: break
            q=select(edges).where(or_(edges.c.from_object_id.in_(frontier),edges.c.to_object_id.in_(frontier)))
            if relations: q=q.where(edges.c.edge_type.in_(relations))
            if at: q=q.where(edges.c.created_at<=at)
            batch=list(c.execute(q.limit(limit*4+1)).mappings()); new=set()
            if len(batch)>limit*4: truncated=True
            for e in batch[:limit*4]:
                for v in (e['from_object_id'],e['to_object_id']):
                    if v not in selected:
                        if len(selected)>=limit: truncated=True; continue
                        selected.add(v); new.add(v)
                if e['from_object_id'] in selected and e['to_object_id'] in selected: links[e['id']]=dict(e)
            frontier=new
        nodes=[dict(x) for x in c.execute(select(objects).where(objects.c.id.in_(selected))).mappings()]
        if at:
            # Only selected IDs are reconstructed; historic graph must not show present-day state.
            nodes=[]
            for oid in selected:
                ev=row(c.execute(select(events).where(and_(events.c.object_id==oid,events.c.timestamp<=at)).order_by(events.c.sequence.desc()).limit(1)))
                if ev and 'snapshot' in ev['payload']: nodes.append(ev['payload']['snapshot'])
        return {'nodes':nodes,'edges':list(links.values()),'truncated':truncated,'limit':limit,'recommended_view':'matrix' if truncated or len(links)>len(nodes)*3 else 'graph'}
    def execute(self,command,actor_id='local-operator'):
        if command.mode!='LIVE': raise Forbidden('Replay is read-only')
        validate_metadata(command.payload)
        fingerprint=hashlib.sha256(json.dumps(command.model_dump(exclude={'idempotency_key'}),sort_keys=True).encode()).hexdigest()
        with self.transaction() as c:
            old=row(c.execute(select(idem).where(idem.c.key==command.idempotency_key)))
            if old:
                if old['fingerprint']!=fingerprint: raise Conflict('Idempotency key reused with different command')
                return old['result']
            p=command.payload; action=command.action; trace=uid(); result={}
            if action=='start_discovery':
                provider=str(p.get('provider') or 'wikimedia_commons')
                query=str(p.get('query') or 'nature').strip()[:200] or 'nature'
                budget=max(1,min(int(p.get('budget') or 8),25))
                title=f'{provider} · {query}'
                source=row(c.execute(select(objects).where(and_(objects.c.object_type=='Source',objects.c.title==title))))
                source_metadata={'provider':provider,'query':query,'item_budget':budget,'live':True}
                if not source:
                    source,ev=self.create(c,'Source',title,metadata=source_metadata,trace=trace,event_type='SOURCE_CREATED')
                    cause=ev['event_id']
                else:
                    source,ev=self.change(c,source['id'],source['version'],trace,None,'SOURCE_CONFIGURED',actor='human',actor_id=actor_id,metadata={**source['metadata'],**source_metadata})
                    cause=ev['event_id']
                task=self.schedule(c,'DISCOVER',source,trace,cause,{'query':query,'budget':budget})
                result={'object':source,'task_id':task,'trace_id':trace,'live':True}
            elif action=='discover':
                if os.environ.get('SWARM_TEST_SIMULATION','false').lower()!='true':
                    raise Forbidden('Fixture discovery is test-only; use start_discovery')
                source=row(c.execute(select(objects).where(and_(objects.c.object_type=='Source',objects.c.title=='Simulated wildlife source'))))
                if not source: source,_=self.create(c,'Source','Simulated wildlife source',metadata={'adapter':'simulated_source'},trace=trace)
                obj,ev=self.create(c,'Candidate',p.get('title','Dog helps deer reach shore'),metadata={
                    'provenance_status':p.get('provenance_status','UNKNOWN'),'media_type':'video',
                    'fixture':'E2E_FIXTURE_001','asset_signature':p.get('asset_signature','wildlife-fixture-v1'),
                    'duration_seconds':42,'topic':p.get('topic','nature')},trace=trace,event_type='CANDIDATE_DISCOVERED')
                self.link(c,obj['id'],source['id'],'SOURCED_FROM',trace,ev['event_id'])
                self.link(c,obj['id'],source['id'],'FOUND_BY',trace,ev['event_id'])
                task=self.schedule(c,'NORMALIZE',obj,trace,ev['event_id']); result={'object':obj,'task_id':task,'trace_id':trace}
            elif action=='create':
                obj,ev=self.create(c,p['object_type'],p['title'],metadata=p.get('metadata',{}),trace=trace)
                result={'object':obj,'trace_id':trace}
            elif action in ('pause_queue','resume_queue','configure'):
                setting=self.settings(c)
                if command.expected_version!=setting['version']: raise Conflict('Stale configuration version')
                data=dict(setting['data'])
                if action=='configure':
                    if set(p)-set(DEFAULT_CONFIG): raise ValueError('Unknown configuration keys')
                    data.update(p); self.validate_config(data)
                else:
                    if p['queue'] not in RESOURCES: raise ValueError('Unknown queue')
                    paused=set(data['paused_queues'])
                    paused.add(p['queue']) if action=='pause_queue' else paused.discard(p['queue'])
                    data['paused_queues']=sorted(paused)
                c.execute(config.update().where(config.c.id==1).values(version=setting['version']+1,data=data))
                self.event(c,{'pause_queue':'QUEUE_PAUSED','resume_queue':'QUEUE_RESUMED'}.get(action,'CONFIGURATION_UPDATED'),None,trace,payload={'configuration':data},actor='human',actor_id=actor_id)
                result={'version':setting['version']+1,'data':data}
            else:
                obj=self.get(c,command.object_id)
                if obj['version']!=command.expected_version: raise Conflict('Stale object version')
                original=self.timeline(c,obj['id']); trace=original[0]['trace_id']; cause=original[-1]['event_id']
                if action=='update': obj,ev=self.change(c,obj['id'],obj['version'],trace,cause,actor='human',actor_id=actor_id,**p)
                elif action in ('pause_account','resume_account'):
                    if obj['object_type']!='Account': raise ValueError('Select an Account')
                    obj,ev=self.change(c,obj['id'],obj['version'],trace,cause,'ACCOUNT_PAUSED' if action=='pause_account' else 'ACCOUNT_RESUMED',actor='human',actor_id=actor_id,status='PAUSED' if action=='pause_account' else 'ACTIVE')
                elif action in ('approve','reject'):
                    if obj['object_type']!='Composition': raise ValueError('Select a Composition')
                    obj,ev=self.change(c,obj['id'],obj['version'],trace,cause,'COMPOSITION_APPROVED' if action=='approve' else 'COMPOSITION_REJECTED',actor='human',actor_id=actor_id,status='APPROVED' if action=='approve' else 'REJECTED')
                elif action=='synthesize':
                    if obj['object_type']!='Candidate' or obj['status'] not in ('ROUTED','REVIEW_PENDING','HELD'): raise Conflict('Candidate is not ready for synthesis')
                    obj,ev=self.change(c,obj['id'],obj['version'],trace,cause,'COMPOSITION_REQUESTED',actor='human',actor_id=actor_id,status='SYNTHESIS_QUEUED')
                    self.schedule(c,'COMPOSE',obj,trace,ev['event_id'],p)
                elif action=='publish':
                    if os.environ.get('SWARM_TEST_SIMULATION','false').lower()!='true':
                        raise Forbidden('No live publishing provider is configured')
                    if obj['object_type']!='Composition' or obj['status']!='APPROVED': raise Conflict('Approve the composition first')
                    obj,ev=self.change(c,obj['id'],obj['version'],trace,cause,'PUBLISH_REQUESTED',actor='human',actor_id=actor_id,status='PUBLISH_QUEUED')
                    self.schedule(c,'PUBLISH',obj,trace,ev['event_id'],p)
                elif action=='cancel_task':
                    if obj['object_type']!='Task': raise ValueError('Select a Task')
                    obj,ev=self.change(c,obj['id'],obj['version'],trace,cause,'TASK_CANCELLED',actor='human',actor_id=actor_id,status='CANCELLED')
                    c.execute(jobs.update().where(jobs.c.task_id==obj['id']).values(cancelled=1,status='CANCELLED'))
                elif action=='annotate':
                    annotation,ev=self.create(c,'Annotation',p['body'][:120],metadata={'target_id':obj['id'],'body':p['body']},trace=trace,cause=cause,event_type='OBJECT_ANNOTATED')
                    obj=annotation
                else: raise ValueError('Unknown command')
                result={'object':obj,'trace_id':trace}
            self.event(c,'COMMAND_EXECUTED',None,trace,payload={'action':action,'object_id':command.object_id},actor='human',actor_id=actor_id)
            c.execute(idem.insert().values(key=command.idempotency_key,operation=action,fingerprint=fingerprint,result=result,created_at=now()))
            return result
    def validate_config(self,d):
        if not 1<=d['lease_seconds']<=3600 or not 1<=d['max_attempts']<=20: raise ValueError('Invalid retry/lease limits')
        if not 1<=d['graph_limit']<=2000: raise ValueError('Invalid graph limit')
        if not 0<=d['exploration_fraction']<=1: raise ValueError('Invalid exploration fraction')
        if set(d['routing_weights'])!={'semantic_fit','novelty','quality'} or any(not 0<=v<=1 for v in d['routing_weights'].values()) or sum(d['routing_weights'].values())<=0: raise ValueError('Invalid routing weights')
        for k in ('max_media_bytes','max_duration_seconds','max_resolution'):
            if not isinstance(d[k],(int,float)) or d[k]<=0: raise ValueError('Invalid media limit')
        if any(q not in RESOURCES for q in d['paused_queues']): raise ValueError('Unknown queue')
        if any(v!='placeholder' for v in d['providers'].values()): raise ValueError('Install a provider adapter before selecting it')
