"""Durable leases, fencing, bounded retries and live discovery/media pipeline."""
import os
import logging
import random
import threading
import time
from sqlalchemy import select, and_, or_, func
from app.swarm.application.service import Service, row
from app.swarm.infrastructure.database import objects, jobs, events, scores, intents, remote_posts, uid, now
from app.swarm.infrastructure.media import Media
from app.swarm.infrastructure.providers import get_provider
from app.swarm.domain.contracts import Conflict

class Worker:
    def __init__(self,service:Service,worker_id=None):
        self.s=service; self.id=worker_id or uid(); self.media=Media()
    def claim(self,task_id=None,resource=None):
        with self.s.transaction() as c:
            cfg=self.s.settings(c)['data']; t=time.time()
            q=select(jobs).where(and_(jobs.c.cancelled==0,jobs.c.not_before<=t,
                or_(jobs.c.status.in_(['QUEUED','WAITING_RETRY']),and_(jobs.c.status=='RUNNING',jobs.c.lease_until<t))))
            if task_id: q=q.where(jobs.c.task_id==task_id)
            if resource: q=q.where(jobs.c.resource_class==resource)
            if cfg['paused_queues']: q=q.where(jobs.c.task_type.not_in(cfg['paused_queues']))
            job=row(c.execute(q.order_by(jobs.c.priority.desc(),jobs.c.created_at).limit(1).with_for_update(skip_locked=True)))
            if not job: return None
            task=self.s.get(c,job['task_id']); trace=job['trace_id']; cause=job['causation_event_id']
            def transition(status,event):
                nonlocal task,cause
                task,ev=self.s.change(c,task['id'],task['version'],trace,cause,event,status=status);cause=ev['event_id']
            if job['status']=='RUNNING':
                transition('WAITING_RETRY','TASK_RETRY_SCHEDULED')
            if job['attempt']>=job['max_attempts']:
                if task['status']=='QUEUED':
                    transition('CLAIMED','TASK_CLAIMED');transition('RUNNING','TASK_STARTED');transition('WAITING_RETRY','TASK_RETRY_SCHEDULED')
                transition('DEAD_LETTER','TASK_DEAD_LETTERED')
                c.execute(jobs.update().where(jobs.c.task_id==task['id']).values(status='DEAD_LETTER'))
                return None
            if task['status']=='WAITING_RETRY': transition('QUEUED','TASK_CREATED')
            transition('CLAIMED','TASK_CLAIMED');transition('RUNNING','TASK_STARTED')
            if not row(c.execute(select(objects).where(objects.c.id==self.id))):
                self.s.create(c,'Worker',f'worker-{self.id[:8]}',metadata={'pid':os.getpid()},trace=trace,id=self.id)
            self.s.link(c,task['id'],self.id,'EXECUTED_BY',trace,cause)
            self.s.event(c,'WORKER_HEARTBEAT',self.s.get(c,self.id),trace,cause,{'task_id':task['id']})
            job.update(status='RUNNING',attempt=job['attempt']+1,lease_until=t+cfg['lease_seconds'],lease_token=uid(),worker_id=self.id,causation_event_id=cause)
            c.execute(jobs.update().where(jobs.c.task_id==task['id']).values(**job))
            return job
    def heartbeat(self,job):
        with self.s.transaction() as c:
            lease=self.s.settings(c)['data']['lease_seconds']
            result=c.execute(jobs.update().where(and_(jobs.c.task_id==job['task_id'],jobs.c.lease_token==job['lease_token'],jobs.c.status=='RUNNING',jobs.c.cancelled==0)).values(lease_until=time.time()+lease))
            return result.rowcount==1
    def execute(self,job):
        stop=threading.Event()
        def pulse():
            while not stop.wait(.5):
                if not self.heartbeat(job): return
        thread=threading.Thread(target=pulse,daemon=True);thread.start()
        try:
            artifacts=self.prepare(job)
            with self.s.transaction() as c:
                current=row(c.execute(select(jobs).where(jobs.c.task_id==job['task_id'])))
                if current['lease_token']!=job['lease_token'] or current['status']!='RUNNING' or current['cancelled']: return False
                self.apply(c,job,artifacts)
                task=self.s.get(c,job['task_id'])
                self.s.change(c,task['id'],task['version'],job['trace_id'],job['causation_event_id'],'TASK_SUCCEEDED',status='SUCCEEDED')
                c.execute(jobs.update().where(jobs.c.task_id==task['id']).values(status='SUCCEEDED',lease_until=0))
            return True
        except Exception as exc:
            logging.getLogger('swarm.worker').warning('Task %s (%s) failed: %s', job['task_id'], job['task_type'], type(exc).__name__)
            with self.s.transaction() as c:
                current=row(c.execute(select(jobs).where(jobs.c.task_id==job['task_id'])))
                if current['lease_token']!=job['lease_token'] or current['status']!='RUNNING': return False
                task=self.s.get(c,job['task_id'])
                task,ev=self.s.change(c,task['id'],task['version'],job['trace_id'],job['causation_event_id'],'TASK_RETRY_SCHEDULED',status='WAITING_RETRY',metadata={**task['metadata'],'last_error_class':type(exc).__name__})
                status='WAITING_RETRY'
                if job['attempt']>=job['max_attempts']:
                    task,ev=self.s.change(c,task['id'],task['version'],job['trace_id'],ev['event_id'],'TASK_DEAD_LETTERED',status='DEAD_LETTER');status='DEAD_LETTER'
                    self.s.create(c,'Alert','Task exhausted retries',metadata={'task_id':task['id'],'error_class':type(exc).__name__},trace=job['trace_id'])
                c.execute(jobs.update().where(jobs.c.task_id==task['id']).values(status=status,lease_until=0,not_before=time.time()+min(2**job['attempt'],60)+random.random()))
            return False
        finally: stop.set();thread.join(timeout=2)
    def run_one(self,task_id=None,resource=None):
        job=self.claim(task_id,resource)
        return self.execute(job) if job else None
    def fence(self,c,job):
        current=row(c.execute(select(jobs).where(jobs.c.task_id==job['task_id'])))
        if current['lease_token']!=job['lease_token'] or current['status']!='RUNNING' or current['cancelled'] or current['lease_until']<time.time():
            raise Conflict('Task lease no longer authorizes execution')

    def prepare(self,job):
        with self.s.db.engine.connect() as c:
            self.fence(c,job)
            obj=self.s.get(c,job['object_ref']['objectId']);cfg=self.s.settings(c)['data']
        kind=job['task_type']
        if kind=='DISCOVER':
            provider_name=str(obj['metadata'].get('provider') or 'wikimedia_commons')
            query=str(obj['metadata'].get('query') or job['payload'].get('query') or 'nature')
            budget=int(job['payload'].get('budget') or obj['metadata'].get('item_budget') or 8)
            return {'items':get_provider(provider_name).discover(query,budget),'provider':provider_name,'query':query}
        if kind=='NORMALIZE':
            asset=self.media.asset(obj,cfg)
            return {'probe':self.media.probe(asset,cfg)}
        if kind=='DEDUPLICATE':
            return self.media.fingerprint(self.media.asset(obj,cfg),cfg)
        if kind=='ANALYZE_VIDEO':
            with self.s.transaction() as c:
                obj=self.s.get(c,obj['id'])
                if obj['status']=='DEDUPED':
                    self.s.change(c,obj['id'],obj['version'],job['trace_id'],job['causation_event_id'],'ANALYSIS_STARTED',status='ANALYZING')
            time.sleep(float(os.environ.get('SWARM_TEST_ANALYSIS_DELAY','0')))
            asset=self.media.asset(obj,cfg)
            probe=self.media.probe(asset,cfg)
            if obj['metadata'].get('fixture') and os.environ.get('SWARM_TEST_SIMULATION','false').lower()=='true':
                import hashlib
                digest=hashlib.sha256(obj['title'].encode()).digest()
                return {
                    'probe':probe,
                    'analysis_mode':'test_fixture',
                    'transcript':{'provider':'test_fixture','model_version':'fixture-v1','text':'[Test fixture transcript]','simulated':True},
                    'embedding':{'provider':'test_fixture','model_version':'hash-fixture-v1','vector':[round(x/255,6) for x in digest],'simulated':True}
                }
            return {'probe':probe,'analysis_mode':'real_media_structural','transcript':None,'embedding':None}
        if kind=='RENDER':
            with self.s.transaction() as c:
                obj=self.s.get(c,obj['id'])
                candidate=self.s.get(c,obj['metadata']['candidate_id'])
                if obj['status']=='RENDER_QUEUED':
                    obj,_=self.s.change(c,obj['id'],obj['version'],job['trace_id'],job['causation_event_id'],'COMPOSITION_RENDER_STARTED',status='RENDERING')
            source=self.media.asset(candidate,cfg)
            return self.media.render(source,obj['id']+'-'+job['lease_token'],obj['metadata']['storyboard'],cfg)
        if kind=='PUBLISH':
            if os.environ.get('SWARM_TEST_SIMULATION','false').lower()!='true':
                raise Conflict('No live publishing provider is configured')
            return self.publish_remote(job,obj)
        return {}
    def publish_remote(self,job,obj):
        key='publish:'+obj['id']; account=obj['metadata']['account_id']
        with self.s.transaction() as c:
            self.fence(c,job)
            if self.s.get(c,account)['status']!='ACTIVE': raise Conflict('Account paused')
            intent=row(c.execute(select(intents).where(intents.c.idempotency_key==key)))
            if not intent:
                c.execute(intents.insert().values(execution_id=uid(),action_type='SIMULATED_PUBLISH',target_account_id=account,
                  input_object_ids=[obj['id']],idempotency_key=key,status='REQUESTED',external_result_id=None,
                  attempt_count=0,last_error=None,requested_at=now(),updated_at=now()))
            c.execute(intents.update().where(intents.c.idempotency_key==key).values(attempt_count=job['attempt'],updated_at=now()))
        # A separate committed remote record deliberately survives a client-side timeout.
        with self.s.transaction() as c:
            self.fence(c,job)
            if self.s.get(c,account)['status']!='ACTIVE': raise Conflict('Account paused')
            accepted=row(c.execute(select(remote_posts).where(remote_posts.c.key==key)))
            if not accepted:
                accepted={'key':key,'external_id':'sim-'+uid(),'account_id':account,'created_at':now()}
                c.execute(remote_posts.insert().values(**accepted))
                if job['payload'].get('simulate_timeout'): timed_out=True
                else: timed_out=False
            else: timed_out=False
        if timed_out: raise TimeoutError('Simulated response lost after platform accepted')
        return {'external_id':accepted['external_id'],'key':key}
    def apply(self,c,job,artifacts):
        s=self.s; obj=s.get(c,job['object_ref']['objectId']); kind=job['task_type']; trace=job['trace_id']; cause=job['causation_event_id']
        def change(status,event,metadata=None):
            nonlocal obj,cause
            patch={'status':status}
            if metadata is not None: patch['metadata']=metadata
            obj,ev=s.change(c,obj['id'],obj['version'],trace,cause,event,**patch);cause=ev['event_id']
        def next_task(kind,target=None,payload=None): s.schedule(c,kind,target or obj,trace,cause,payload)
        if kind=='DISCOVER':
            source=obj
            existing=[dict(x) for x in c.execute(select(objects).where(objects.c.object_type=='Candidate')).mappings()]
            created=0
            for item in artifacts.get('items',[]):
                duplicate=next((x for x in existing if x['metadata'].get('provider')==item.get('provider') and x['metadata'].get('external_id')==item.get('external_id')),None)
                if duplicate:
                    continue
                metadata={
                    **item,
                    'source_id':source['id'],
                    'media_type':'video',
                    'ingest_status':'media_ready' if item.get('media_url') else 'metadata_only',
                    'live':True,
                }
                candidate,ev=s.create(c,'Candidate',item.get('title') or item.get('external_id') or 'Discovered video',metadata=metadata,trace=trace,cause=cause,event_type='CANDIDATE_DISCOVERED')
                s.link(c,candidate['id'],source['id'],'SOURCED_FROM',trace,ev['event_id'])
                s.link(c,candidate['id'],source['id'],'FOUND_BY',trace,ev['event_id'])
                if item.get('media_url'):
                    s.schedule(c,'NORMALIZE',candidate,trace,ev['event_id'])
                created+=1
            source_meta={**source['metadata'],'last_discovery_count':created,'last_discovery_provider':artifacts.get('provider'),'last_discovery_query':artifacts.get('query'),'last_discovery_at':now()}
            s.change(c,source['id'],source['version'],trace,cause,'SOURCE_DISCOVERY_COMPLETED',metadata=source_meta)
        elif kind=='NORMALIZE':
            probe=artifacts.get('probe') or {}
            change('NORMALIZED','CANDIDATE_NORMALIZED',{**obj['metadata'],'probe':probe,'duration_seconds':probe.get('duration_seconds'),'ingest_status':'normalized'});next_task('DEDUPLICATE')
        elif kind=='DEDUPLICATE':
            others=c.execute(select(objects).where(and_(objects.c.object_type=='Candidate',objects.c.id!=obj['id']))).mappings()
            for other in others:
                other_hash=other['metadata'].get('perceptual_hash')
                near=other_hash and (int(other_hash,16)^int(artifacts['perceptual_hash'],16)).bit_count()<=3
                if near or other['metadata'].get('sha256')==artifacts['sha256']:
                    s.link(c,obj['id'],other['id'],'SIMILAR_TO',trace,cause)
            change('DEDUPED','CANDIDATE_DEDUPED',{**obj['metadata'],**artifacts});next_task('ANALYZE_VIDEO')
        elif kind=='ANALYZE_VIDEO':
            change('ANALYZED','ANALYSIS_COMPLETED',{**obj['metadata'],**artifacts,'analysis_live':True});next_task('ATOMIZE')
        elif kind=='ATOMIZE':
            duration=float((obj['metadata'].get('probe') or {}).get('duration_seconds') or obj['metadata'].get('duration_seconds') or 0)
            if duration<=0:
                raise ValueError('Cannot atomize media without a real duration')
            width=min(6.0,max(1.0,duration/3))
            anchors=[('opening',0.0),('middle',max(0.0,duration/2-width/2)),('ending',max(0.0,duration-width))]
            seen=set()
            for motif,start in anchors:
                end=min(duration,start+width)
                key=(round(start,3),round(end,3))
                if end<=start or key in seen:
                    continue
                seen.add(key)
                atom,ev=s.create(c,'ContentAtom',f'{obj["title"]} · {motif}',metadata={'candidate_id':obj['id'],'start':start,'end':end,'duration':end-start,'motif':motif,'extraction':'duration_based_live_media'},trace=trace,cause=cause,event_type='ATOM_CREATED')
                s.link(c,obj['id'],atom['id'],'HAS_ATOM',trace,ev['event_id'])
            next_task('CLUSTER')
        elif kind=='CLUSTER':
            title=obj['metadata']['topic']
            trend=row(c.execute(select(objects).where(and_(objects.c.object_type=='TrendCluster',objects.c.title==title))))
            if not trend: trend,_=s.create(c,'TrendCluster',title,metadata={'member_count':0},trace=trace,cause=cause,event_type='TREND_CREATED')
            s.link(c,obj['id'],trend['id'],'MEMBER_OF_TREND',trace,cause)
            s.change(c,trend['id'],trend['version'],trace,cause,'TREND_MEMBERSHIP_ADDED',metadata={**trend['metadata'],'member_count':trend['metadata']['member_count']+1})
            next_task('ROUTE')
        elif kind=='ROUTE':
            accounts=[dict(x) for x in c.execute(select(objects).where(and_(objects.c.object_type=='Account',objects.c.status=='ACTIVE'))).mappings()]
            if not accounts:
                a,_=s.create(c,'Account','Local Review',metadata={'topic':'*','platform':'local','adapter':'local_review','publishing_enabled':False},trace=trace,cause=cause)
                accounts.append(a)
            cfg=s.settings(c)['data'];rank=[]
            for account in accounts:
                features={'semantic_fit':1. if account['metadata'].get('topic')==obj['metadata'].get('topic') else (.5 if account['metadata'].get('topic')=='*' else .2),'novelty':.6,'quality':.8}
                score=sum(features[k]*v for k,v in cfg['routing_weights'].items())/sum(cfg['routing_weights'].values())
                record={'id':uid(),'object_id':obj['id'],'target_object_id':account['id'],'score_type':'route','score':score,'uncertainty':.35,'model_version':cfg['model_version'],'features':features,'explanation':{'method':'configurable weighted heuristic','weights':cfg['routing_weights']},'created_at':now()}
                c.execute(scores.insert().values(**record));s.link(c,obj['id'],account['id'],'MATCHES_ACCOUNT',trace,cause);rank.append((score,account))
            rank.sort(key=lambda x:(-x[0],x[1]['title']));score,account=rank[0]
            s.link(c,obj['id'],account['id'],'ROUTED_TO',trace,cause)
            change('ROUTED','ROUTE_DECIDED',{**obj['metadata'],'account_id':account['id'],'route_score':score,'model_version':cfg['model_version']})
            if obj['metadata']['provenance_status'] in ('UNKNOWN','RESTRICTED'):
                change('REVIEW_PENDING','CANDIDATE_REVIEW_REQUIRED')
            # Human controls synthesis and review. No covert auto-approval.
        elif kind=='COMPOSE':
            from app.swarm.infrastructure.database import edges
            atom_ids=list(c.execute(select(edges.c.to_object_id).where(and_(edges.c.from_object_id==obj['id'],edges.c.edge_type=='HAS_ATOM'))).scalars())
            requested=job['payload'].get('atom_ids') or atom_ids
            if not set(requested)<=set(atom_ids) or not requested: raise ValueError('Storyboard must use candidate atoms')
            atoms=[s.get(c,x) for x in requested]
            comp,ev=s.create(c,'Composition',obj['title']+' · composition',metadata={'account_id':obj['metadata']['account_id'],'candidate_id':obj['id'],
                 'storyboard':[{'atom_id':a['id'],'start':a['metadata']['start'],'end':a['metadata']['end']} for a in atoms],
                 'provenance_status':obj['metadata'].get('provenance_status','UNKNOWN'),'live_content':True},trace=trace,cause=cause,event_type='COMPOSITION_CREATED')
            s.link(c,comp['id'],obj['id'],'DERIVED_FROM',trace,ev['event_id'])
            for atom in atoms: s.link(c,comp['id'],atom['id'],'USES_ATOM',trace,ev['event_id'])
            s.link(c,comp['id'],obj['metadata']['account_id'],'ROUTED_TO',trace,ev['event_id'])
            comp,ev=s.change(c,comp['id'],comp['version'],trace,ev['event_id'],'COMPOSITION_RENDER_QUEUED',status='RENDER_QUEUED')
            change('COMPOSED','CANDIDATE_COMPOSED');next_task('RENDER',comp)
        elif kind=='RENDER':
            asset,ev=s.create(c,'MediaAsset','Rendered composition',metadata=artifacts,trace=trace,cause=cause)
            s.link(c,asset['id'],obj['metadata']['candidate_id'],'DERIVED_FROM',trace,ev['event_id'])
            s.link(c,obj['id'],self.id,'GENERATED_BY',trace,cause)
            change('REVIEW','COMPOSITION_RENDERED',{**obj['metadata'],'render':artifacts,'asset_id':asset['id']})
        elif kind=='PUBLISH':
            post,ev=s.create(c,'Post',obj['title']+' · simulated post',metadata={'account_id':obj['metadata']['account_id'],'external_id':artifacts['external_id'],'adapter':'simulated_platform','simulated':True},trace=trace,cause=cause,event_type='POST_CREATED')
            s.link(c,obj['id'],post['id'],'PUBLISHED_AS',trace,ev['event_id'])
            c.execute(intents.update().where(intents.c.idempotency_key==artifacts['key']).values(status='SUCCEEDED',external_result_id=artifacts['external_id'],updated_at=now()))
            change('PUBLISHED','PUBLISH_SUCCEEDED');next_task('COLLECT_METRICS',post)
        elif kind=='COLLECT_METRICS':
            metric,ev=s.create(c,'MetricSnapshot','Simulated response sample',metadata={'post_id':obj['id'],'account_id':obj['metadata']['account_id'],'views':1000,'shares':75,'completion_rate':.82,'watch_fraction':.78,'simulated':True},trace=trace,cause=cause,event_type='METRICS_COLLECTED')
            s.link(c,obj['id'],metric['id'],'MEASURED_BY',trace,ev['event_id']);s.link(c,obj['metadata']['account_id'],metric['id'],'MEASURED_BY',trace,ev['event_id']);next_task('UPDATE_MODEL',metric)
        elif kind=='UPDATE_MODEL':
            account=s.get(c,obj['metadata']['account_id']);genome_id=account['metadata'].get('audience_genome_id')
            genome=s.get(c,genome_id) if genome_id else None
            previous=genome['metadata'] if genome else {'samples':0,'mean_completion':0}
            count=previous['samples']+1;mean=previous['mean_completion']+(obj['metadata']['completion_rate']-previous['mean_completion'])/count
            data={'account_id':account['id'],'samples':count,'mean_completion':mean,'model_version':f'audience-v{count}','metric_id':obj['id']}
            if genome: genome,ev=s.change(c,genome['id'],genome['version'],trace,cause,'AUDIENCE_GENOME_UPDATED',metadata=data)
            else: genome,ev=s.create(c,'AudienceGenome',account['title']+' audience',metadata=data,trace=trace,cause=cause,event_type='AUDIENCE_GENOME_UPDATED')
            s.change(c,account['id'],account['version'],trace,ev['event_id'],'ACCOUNT_UPDATED',metadata={**account['metadata'],'audience_genome_id':genome['id']})
            s.link(c,obj['id'],genome['id'],'UPDATED_MODEL',trace,ev['event_id'])
        else: raise ValueError('No handler registered for '+kind)
