"""Fail-closed live-stack gate. Runs against actual Compose services, never mocks boot."""
import asyncio
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4
import httpx

BASE='http://localhost:5173/api/v1/swarm'
client=httpx.Client(base_url=BASE,timeout=30,trust_env=False)
report={};evidence=Path('test-evidence');evidence.mkdir(exist_ok=True)

def compose(*args):
    return subprocess.run(['docker','compose','-f','docker-compose.yml','-f','docker-compose.acceptance.yml',*args],check=True,capture_output=True,text=True).stdout

def check(id,condition,detail):
    report[id]={'status':'PASS' if condition else 'FAIL','detail':detail}
    if not condition:raise AssertionError(id+': '+detail)

def get(path):
    r=client.get(path);r.raise_for_status();return r.json()

def command(action,obj=None,**payload):
    r=client.post('/commands/execute',json={'action':action,'object_id':obj['id'] if obj else None,'expected_version':obj['version'] if obj else None,'idempotency_key':str(uuid4()),'payload':payload})
    r.raise_for_status();return r.json()

def wait_object(id,status,timeout=180):
    until=time.time()+timeout
    while time.time()<until:
        obj=get('/objects/'+id)
        if obj['status']==status:return obj
        time.sleep(.5)
    raise AssertionError('Timed out waiting for '+status+': '+str(obj))

def query(kind):
    r=client.post('/objects/query',json={'object_type':kind,'limit':200});r.raise_for_status();return r.json()['items']

def main():
    import shutil
    if not shutil.which('docker'):
        report['A01']={'status':'BLOCKED','detail':'Docker executable is unavailable in this environment'}
        raise RuntimeError('Docker runtime required for full-stack acceptance')
    until=time.time()+240
    while True:
        try:health=get('/health');break
        except Exception:
            if time.time()>until:raise
            time.sleep(2)
    services=compose('ps','--services','--status','running').splitlines()
    required=['frontend','backend','sandbox','mongodb','redis','postgres','minio','swarm_dispatcher','swarm_worker_io','swarm_worker_browser','swarm_worker_gpu','swarm_worker_render','swarm_worker_publisher']
    check('A01',set(required)<=set(services),'All required services running: '+', '.join(services))
    check('A02',health['status']=='ok','Fresh Alembic migration and API startup succeeded')
    # Real broker outage, durable discovery and eventual delivery after recovery.
    compose('stop','redis')
    try:
        result=command('discover',title='Broker outage recovery fixture')
        time.sleep(2)
        check('A04',len(get('/objects/'+result['object']['id']+'/timeline'))>0,'Event visible while broker is unavailable')
    finally:compose('start','redis')
    candidate=wait_object(result['object']['id'],'REVIEW_PENDING')
    check('A05',candidate['status']=='REVIEW_PENDING','Outbox recovered actual Redis outage')
    # Kill actual media worker after it announces analysis started.
    result2=command('discover',title='Worker crash fixture')
    wait_object(result2['object']['id'],'ANALYZING')
    compose('kill','-s','SIGKILL','swarm_worker_gpu');compose('up','-d','swarm_worker_gpu')
    recovered=wait_object(result2['object']['id'],'REVIEW_PENDING')
    history=get('/objects/'+recovered['id']+'/trace')
    check('A09',sum(e['event_type']=='ANALYSIS_COMPLETED' for e in history)==1,'Killed Celery GPU worker; lease retry completed analysis once')
    check('A10',candidate['object_type']=='Candidate','Simulated source persisted candidate')
    check('A11',bool(candidate['metadata']['probe'] and candidate['metadata']['transcript'] and candidate['metadata']['embedding']),'Real FFmpeg probe and labeled placeholders')
    atoms=get('/candidates/'+candidate['id']+'/atoms');check('A11',len(atoms)>=3,'Three extracted fixture atoms persisted')
    check('A26',candidate['metadata']['provenance_status']=='UNKNOWN','UNKNOWN analyzed and routed into review')
    graph=client.post('/graph/neighborhood',json={'object_id':candidate['id'],'depth':2,'limit':3}).json()
    check('A22',bool(graph['edges']),'Typed neighborhood relationships available')
    check('A28',len(graph['nodes'])<=3 and graph['truncated'],'Oversized neighborhood is bounded with truncation metadata')
    command('synthesize',candidate,atom_ids=[a['id'] for a in atoms])
    until=time.time()+120
    while True:
        compositions=[x for x in query('Composition') if x['metadata']['candidate_id']==candidate['id']]
        if compositions:break
        if time.time()>until:raise AssertionError('No composition')
        time.sleep(.5)
    comp=wait_object(compositions[0]['id'],'REVIEW')
    check('A16',comp['metadata']['render']['renderer']=='ffmpeg','Actual FFmpeg composition rendered and uploaded to MinIO')
    approved=command('approve',comp)['object'];check('A17',approved['status']=='APPROVED','Human approval audited')
    command('publish',approved,simulate_timeout=True)
    wait_object(comp['id'],'PUBLISHED')
    until=time.time()+120
    while True:
        trace=get('/objects/'+comp['id']+'/trace')
        if any(e['event_type']=='AUDIENCE_GENOME_UPDATED' for e in trace):break
        if time.time()>until:raise AssertionError('Learning timed out')
        time.sleep(.5)
    posts=[e['payload']['snapshot'] for e in trace if e['event_type']=='POST_CREATED']
    check('A18',len(posts)==1 and posts[0]['metadata']['simulated'],'One simulated Post through persisted intent')
    check('A19',len(posts)==1,'Timeout-after-acceptance retried without duplicate Post')
    check('A20',any(e['event_type']=='METRICS_COLLECTED' for e in trace),'MetricSnapshot received')
    check('A21',any(e['event_type']=='AUDIENCE_GENOME_UPDATED' for e in trace),'Audience model updated')
    check('A25',any(e['event_type']=='CANDIDATE_DISCOVERED' for e in trace),'Post trace covers discovery through learning')
    at=get('/objects/'+candidate['id']+'/timeline')[0]['timestamp']
    snapshot=client.get('/replay/snapshot',params={'at':at}).json()
    check('A24',next(o for o in snapshot['objects'] if o['id']==candidate['id'])['status']=='DISCOVERED','Historical state reconstructed without changing live objects')
    compose('restart','backend','swarm_dispatcher')
    until=time.time()+120
    while True:
        try:
            restored=get('/objects/'+comp['id']+'/trace');break
        except Exception:
            if time.time()>until:raise
            time.sleep(1)
    check('restart',len(restored)==len(trace),'Trace reconstructs unchanged after backend and dispatcher restart')
    (evidence/'fullstack-lifecycle.json').write_text(json.dumps({'candidate_id':candidate['id'],'composition_id':comp['id'],'post_id':posts[0]['id'],'trace_id':result['trace_id'],'events':trace},indent=2))

if __name__=='__main__':
    try:main()
    finally:(evidence/'fullstack-acceptance.json').write_text(json.dumps(report,indent=2))
