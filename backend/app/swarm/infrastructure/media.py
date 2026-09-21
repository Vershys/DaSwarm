"""Bounded, shell-free deterministic FFmpeg adapter and object storage."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Protocol

class TranscriptionProvider(Protocol):
    def transcribe(self,asset: Path) -> dict: ...
class EmbeddingProvider(Protocol):
    def embed(self,text: str) -> dict: ...
class PlaceholderIntelligence:
    def transcribe(self,asset): return {'provider':'placeholder','model_version':'fixture-v1','text':'[Simulated transcript: wildlife rescue]','simulated':True}
    def embed(self,text):
        digest=hashlib.sha256(text.encode()).digest()
        return {'provider':'placeholder','model_version':'hash-fixture-v1','vector':[round(x/255,6) for x in digest], 'simulated':True}

class Media:
    def __init__(self):
        self.root=Path(os.environ.get('SWARM_MEDIA_ROOT','/tmp/manu-swarm-media')).resolve(); self.root.mkdir(parents=True,exist_ok=True)
    def path(self,key):
        p=(self.root/key).resolve()
        if not p.is_relative_to(self.root): raise ValueError('Invalid asset path')
        return p
    def run(self,args):
        subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=120)
    def fixture(self):
        p=self.path('fixture-v1.mp4')
        if not p.exists():
            from uuid import uuid4
            temp=self.path('fixture-v1-'+uuid4().hex+'.part.mp4')
            self.run(['ffmpeg','-nostdin','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=12',
                      '-f','lavfi','-i','sine=frequency=440:sample_rate=22050','-t','42','-c:v','libx264',
                      '-threads','1','-pix_fmt','yuv420p','-c:a','aac',str(temp)])
            temp.replace(p)
        return p
    def probe(self,p,settings):
        if p.stat().st_size>settings['max_media_bytes']: raise ValueError('Media byte limit exceeded')
        result=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],capture_output=True,text=True,check=True,timeout=20)
        probe=json.loads(result.stdout); video=next(s for s in probe['streams'] if s['codec_type']=='video')
        duration=float(probe['format']['duration'])
        if duration>settings['max_duration_seconds'] or max(video['width'],video['height'])>settings['max_resolution']: raise ValueError('Media dimensions/duration exceed policy')
        return {'duration_seconds':duration,'width':video['width'],'height':video['height'],'codec':video['codec_name'],'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    def fingerprint(self,p,settings):
        probe=self.probe(p,settings)
        result=subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(probe['duration_seconds']/2),'-i',str(p),'-frames:v','1','-vf','scale=8:8,format=gray','-f','rawvideo','pipe:1'],capture_output=True,check=True,timeout=30)
        pixels=result.stdout
        if len(pixels)!=64: raise ValueError('Could not fingerprint media')
        mean=sum(pixels)/64
        bits=''.join('1' if p>=mean else '0' for p in pixels)
        return {'sha256':probe['sha256'],'perceptual_hash':format(int(bits,2),'016x')}

    def render(self,key,segments,settings):
        source=self.fixture(); self.probe(source,settings)
        p=self.path(key+'.mp4'); tmp=self.path(key+'.part.mp4')
        if not segments or len(segments)>20: raise ValueError('Storyboard requires 1–20 atoms')
        filters=[]; inputs=[]
        for i,s in enumerate(segments):
            a,b=float(s['start']),float(s['end'])
            if not 0<=a<b<=42: raise ValueError('Atom range outside fixture')
            filters.extend([f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]',f'[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]'])
            inputs.append(f'[v{i}][a{i}]')
        filters.append(''.join(inputs)+f'concat=n={len(segments)}:v=1:a=1[v][a]')
        self.run(['ffmpeg','-nostdin','-y','-i',str(source),'-filter_complex',';'.join(filters),'-map','[v]','-map','[a]',
                  '-c:v','libx264','-threads','1','-c:a','aac','-movflags','+faststart',str(tmp)])
        tmp.replace(p); probe=self.probe(p,settings)
        self.store(p)
        return {'key':p.name,'probe':probe,'renderer':'ffmpeg','simulated_content':True}
    def store(self,p):
        endpoint=os.environ.get('SWARM_OBJECT_STORE_ENDPOINT')
        if not endpoint: return # test-only local filesystem
        import boto3
        client=boto3.client('s3',endpoint_url=endpoint,
            aws_access_key_id=os.environ['SWARM_OBJECT_STORE_ACCESS_KEY'],
            aws_secret_access_key=os.environ['SWARM_OBJECT_STORE_SECRET_KEY'])
        bucket=os.environ.get('SWARM_OBJECT_STORE_BUCKET','manu-swarm')
        try: client.head_bucket(Bucket=bucket)
        except client.exceptions.ClientError: client.create_bucket(Bucket=bucket)
        client.upload_file(str(p),bucket,p.name)
