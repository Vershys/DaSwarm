"""Component evidence for P0. Docker/browser gates have independent, non-skipping runners."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from fastapi.testclient import TestClient
from app.swarm.application.service import Service
from app.swarm.application.worker import Worker
from app.swarm.infrastructure.database import objects,events,jobs,outbox,intents,remote_posts,edges,scores,Database
from app.swarm.infrastructure.dispatch import Dispatcher
from app.swarm.domain.contracts import Command,Conflict,Forbidden
from app.swarm.interfaces.api import create_app
from conftest import command

def all_type(s,kind):
    with s.db.engine.connect() as c: return s.query(c,kind)
def get(s,id):
    with s.db.engine.connect() as c:return s.get(c,id)
def drain(s):
    w=Worker(s)
    for _ in range(100):
        result=w.run_one()
        if result is None: return
        assert result,'Pipeline task failed; inspect ledger'
    raise AssertionError('Worker did not quiesce')
def discover_route(s):
    start=command(s,'discover');drain(s)
    return get(s,start['object']['id']),start

def lifecycle(s,timeout=False):
    candidate,start=discover_route(s)
    command(s,'synthesize',candidate);drain(s)
    composition=all_type(s,'Composition')[0]
    assert composition['status']=='REVIEW'
    composition=command(s,'approve',composition)['object']
    command(s,'publish',composition,simulate_timeout=timeout)
    if timeout:
        w=Worker(s);assert w.run_one() is False
        with s.db.engine.begin() as c:c.execute(jobs.update().values(not_before=0))
    drain(s)
    return candidate,start,composition

def test_A02_migration_repeatable(service):
    service.initialize()
    with service.db.engine.connect() as c:assert c.execute(select(func.count()).select_from(objects)).scalar()==0

def test_A03_A04_versioned_crud_durable_event(service):
    result=command(service,'discover');obj=result['object']
    updated=command(service,'update',obj,title='Updated')['object']
    assert updated['version']==2
    with pytest.raises(Conflict):command(service,'update',obj,title='Stale')
    with service.db.engine.connect() as c:
        event=service.timeline(c,obj['id'])[0]
        assert event['trace_id']==event['correlation_id']==result['trace_id']
        assert event['payload']['snapshot']['title']=='Dog helps deer reach shore'

def test_A05_outbox_broker_outage(service):
    command(service,'discover')
    def broken(e):raise ConnectionError()
    Dispatcher(service,broken).once()
    with service.db.engine.connect() as c:
        assert c.execute(select(func.count()).select_from(outbox).where(outbox.c.dispatched_at.is_(None))).scalar()>0
    delivered=[];Dispatcher(service,lambda e:delivered.append(e)).once()
    assert any(e['topic']=='task' for e in delivered)

def test_A06_A07_websocket_transport_reconnect(service):
    app=create_app(service)
    with TestClient(app) as client:
        with client.websocket_connect('/api/v1/ws/swarm?last_sequence=0') as ws:
            command(service,'discover');message=ws.receive_json()
            while message['type']!='swarm.event':message=ws.receive_json()
            first=message['sequence'];assert message['event']['trace_id']
        command(service,'discover',title='Second')
        with client.websocket_connect(f'/api/v1/ws/swarm?last_sequence={first}') as ws:
            messages=[ws.receive_json() for _ in range(3)]
            assert [m['sequence'] for m in messages]==list(range(first+1,first+4))

def test_A08_duplicate_delivery_and_key_conflict(service):
    cmd=Command(action='discover',idempotency_key='fixed')
    a=service.execute(cmd);b=service.execute(cmd);assert a==b
    assert len(all_type(service,'Candidate'))==1
    worker=Worker(service);assert worker.run_one(a['task_id']) is True
    assert worker.run_one(a['task_id']) is None
    with pytest.raises(Conflict):service.execute(Command(action='discover',idempotency_key='fixed',payload={'title':'different'}))

def test_A09_worker_process_kill_and_reclaim(service):
    start=command(service,'discover');w=Worker(service)
    assert w.run_one() is True;assert w.run_one() is True
    with service.db.engine.begin() as c:
        from app.swarm.infrastructure.database import config
        setting=c.execute(select(config)).mappings().one();data=dict(setting['data']);data['lease_seconds']=1
        c.execute(config.update().values(data=data))
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'backend'),'SWARM_TEST_ANALYSIS_DELAY':'60'}
    code='from app.swarm.application.worker import Worker;from app.swarm.application.service import Service;from app.swarm.infrastructure.database import Database;import sys;Worker(Service(Database(sys.argv[1]))).run_one()'
    p=subprocess.Popen([sys.executable,'-c',code,service.db.engine.url.render_as_string(hide_password=False)],env=env)
    deadline=time.time()+10
    try:
        while time.time()<deadline:
            if get(service,start['object']['id'])['status']=='ANALYZING':break
            time.sleep(.05)
        else:raise AssertionError('Child never reached ANALYSIS_STARTED')
        p.kill();p.wait(timeout=5)
    finally:
        if p.poll() is None:p.kill();p.wait()
    time.sleep(1.2);drain(service)
    assert get(service,start['object']['id'])['status']=='REVIEW_PENDING'
    with service.db.engine.connect() as c:
        assert c.execute(select(func.count()).select_from(events).where(events.c.event_type=='ANALYSIS_COMPLETED')).scalar()==1

def test_A10_A11_A12_A13_A14_A26_discovery_intelligence(service):
    a,start=discover_route(service);b,_=discover_route(service)
    assert a['status']=='REVIEW_PENDING' and a['metadata']['provenance_status']=='UNKNOWN'
    assert a['metadata']['probe']['duration_seconds']==42
    assert a['metadata']['transcript']['simulated'] and a['metadata']['embedding']['vector']
    assert len(all_type(service,'ContentAtom'))==6
    assert len(all_type(service,'TrendCluster'))==1
    assert a['metadata']['route_score']==b['metadata']['route_score']
    with service.db.engine.connect() as c:
        assert c.execute(select(func.count()).select_from(edges).where(edges.c.edge_type=='SIMILAR_TO')).scalar()==1
        score=c.execute(select(scores)).mappings().first();assert score['model_version'] and score['features'] and score['explanation']

def test_A15_worker_account_separation(service):
    a=command(service,'create',object_type='Account',title='Nature',metadata={'topic':'nature'})['object']
    b=command(service,'create',object_type='Account',title='Tech',metadata={'topic':'technology'})['object']
    command(service,'discover',topic='nature');command(service,'discover',topic='technology')
    w=Worker(service)
    for _ in range(30):
        if w.run_one() is None:break
    candidates=all_type(service,'Candidate')
    assert {x['metadata']['account_id'] for x in candidates}=={a['id'],b['id']}
    assert get(service,a['id'])['metadata']['topic']=='nature'
    assert get(service,b['id'])['metadata']['topic']=='technology'

def test_A16_A17_A18_A20_A21_A25_full_lifecycle(service,tmp_path):
    candidate,start,composition=lifecycle(service)
    posts=all_type(service,'Post');metrics=all_type(service,'MetricSnapshot');genomes=all_type(service,'AudienceGenome')
    assert len(posts)==len(metrics)==len(genomes)==1
    rendered=get(service,composition['id'])['metadata']['render']
    assert rendered['probe']['duration_seconds']==18
    assert Path(os.environ['SWARM_MEDIA_ROOT'],rendered['key']).stat().st_size>1000
    with service.db.engine.connect() as c:
        history=service.trace(c,start['trace_id']);names=[e['event_type'] for e in history]
        for name in ['COMPOSITION_APPROVED','PUBLISH_SUCCEEDED','METRICS_COLLECTED','AUDIENCE_GENOME_UPDATED']:assert name in names
        assert any(e['event_type']=='COMPOSITION_APPROVED' and e['actor_type']=='human' for e in history)
        assert c.execute(select(intents.c.status)).scalar()=='SUCCEEDED'
    # Restart the repository service and prove history remains reconstructible.
    reopened=Service(Database(service.db.engine.url.render_as_string(hide_password=False)));reopened.initialize()
    with reopened.db.engine.connect() as c:assert len(reopened.trace(c,start['trace_id']))==len(history)
    record={'candidate_id':candidate['id'],'trace_id':start['trace_id'],'task_ids':[x['id'] for x in all_type(service,'Task')],
      'composition_id':composition['id'],'post_id':posts[0]['id'],'metric_id':metrics[0]['id'],'audience_genome_id':genomes[0]['id'],
      'model_update_event':next(e['event_id'] for e in history if e['event_type']=='AUDIENCE_GENOME_UPDATED')}
    evidence=Path(__file__).resolve().parents[2]/'test-evidence';evidence.mkdir(exist_ok=True);(evidence/'lifecycle.json').write_text(json.dumps(record,indent=2))

def test_A19_timeout_after_acceptance(service):
    lifecycle(service,timeout=True)
    assert len(all_type(service,'Post'))==1
    with service.db.engine.connect() as c:
        assert c.execute(select(func.count()).select_from(remote_posts)).scalar()==1
        assert c.execute(select(intents.c.attempt_count)).scalar()==2

def test_A22_A28_bounded_graph(service):
    candidate,_=discover_route(service)
    with service.db.engine.connect() as c:
        full=service.neighborhood(c,candidate['id'],2,500);bounded=service.neighborhood(c,candidate['id'],2,3)
    assert len(full['nodes'])>3 and full['edges']
    assert len(bounded['nodes'])==3 and bounded['truncated'] and bounded['recommended_view']=='matrix'

def test_A24_replay_immutable(service):
    start=command(service,'discover');original=start['object'];at=original['created_at']
    with service.db.engine.connect() as c: at=service.timeline(c,original['id'])[0]['timestamp']
    drain(service)
    with service.db.engine.connect() as c:
        before=c.execute(select(func.count()).select_from(events)).scalar()
        snap=service.replay(c,at);obj=next(x for x in snap['objects'] if x['id']==original['id'])
        assert obj['status']=='DISCOVERED'
        assert service.get(c,original['id'])['status']=='REVIEW_PENDING'
        assert c.execute(select(func.count()).select_from(events)).scalar()==before
    with pytest.raises(Forbidden):service.execute(Command(action='discover',idempotency_key='replay',mode='REPLAY'))

def test_A27_secrets_rejected(service,monkeypatch):
    monkeypatch.setenv('SWARM_TEST_SECRET','do-not-leak-this-secret')
    for metadata in [{'access_token':'a'},{'nested':{'password':'a'}},{'description':'do-not-leak-this-secret'}]:
        with pytest.raises(Forbidden):command(service,'create',object_type='Account',title='bad',metadata=metadata)
    with service.db.engine.connect() as c: assert c.execute(select(func.count()).select_from(events)).scalar()==0

def test_agent_telemetry_contract(service):
    start=command(service,'discover')
    worker=Worker(service)
    assert worker.run_one() is True
    app=create_app(service)
    with TestClient(app) as client:
        response=client.get('/api/v1/swarm/agents/telemetry')
        assert response.status_code==200
        payload=response.json()
        assert {'known_agents','online','working','idle','stale','offline'}<=set(payload['summary'])
        agent=next(x for x in payload['agents'] if x['id']==worker.id)
        assert agent['kind']=='worker'
        assert agent['task']['id']==start['task_id']
        assert agent['task']['type']=='NORMALIZE'
        assert agent['target']['id']==start['object']['id']
        assert agent['stats']['assigned']>=1
        assert isinstance(agent['recent_activity'],list)

def test_controls_and_fencing(service):
    start=command(service,'discover')
    with service.db.engine.connect() as c:setting=service.settings(c)
    service.execute(Command(action='pause_queue',expected_version=setting['version'],payload={'queue':'NORMALIZE'},idempotency_key='pause'))
    assert Worker(service).claim() is None
    service.execute(Command(action='resume_queue',expected_version=setting['version']+1,payload={'queue':'NORMALIZE'},idempotency_key='resume'))
    w=Worker(service);job=w.claim();assert job
    task=get(service,job['task_id']);command(service,'cancel_task',task)
    assert w.execute(job) is False
    assert get(service,start['object']['id'])['status']=='DISCOVERED'

def test_auth_and_feature_flags(service,monkeypatch):
    monkeypatch.setenv('SWARM_LOCAL_ONLY','false')
    with TestClient(create_app(service)) as client:assert client.get('/api/v1/swarm/config').status_code==403
    monkeypatch.setenv('SWARM_LOCAL_ONLY','true');monkeypatch.setenv('SWARM_ENABLED','false')
    with TestClient(create_app(service)) as client:assert client.get('/api/v1/swarm/config').status_code==404
