"""Bounded FFmpeg media adapter for real candidate assets and test-only fixtures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse

import httpx


class Media:
    def __init__(self):
        self.root=Path(os.environ.get('SWARM_MEDIA_ROOT','/tmp/manu-swarm-media')).resolve()
        self.root.mkdir(parents=True,exist_ok=True)

    def path(self,key):
        p=(self.root/key).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError('Invalid asset path')
        return p

    def run(self,args,timeout=120):
        subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=timeout)

    def fixture(self):
        """Deterministic CI fixture. Production UI never invokes this path."""
        p=self.path('fixture-v1.mp4')
        if not p.exists():
            from uuid import uuid4
            temp=self.path('fixture-v1-'+uuid4().hex+'.part.mp4')
            self.run(['ffmpeg','-nostdin','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=12',
                      '-f','lavfi','-i','sine=frequency=440:sample_rate=22050','-t','42','-c:v','libx264',
                      '-threads','1','-pix_fmt','yuv420p','-c:a','aac',str(temp)])
            temp.replace(p)
        return p

    def _allowed_remote(self,url,provider):
        parsed=urlparse(url)
        if parsed.scheme!='https':
            raise ValueError('Remote media must use HTTPS')
        host=(parsed.hostname or '').lower()
        if provider=='wikimedia_commons':
            if host!='upload.wikimedia.org' and not host.endswith('.upload.wikimedia.org'):
                raise ValueError('Wikimedia media URL host is not allowed')
            return
        extra={x.strip().lower() for x in os.environ.get('SWARM_MEDIA_ALLOWED_HOSTS','').split(',') if x.strip()}
        if host not in extra:
            raise ValueError('Remote media host is not authorized for ingestion')

    def fetch(self,url,provider,settings):
        self._allowed_remote(url,provider)
        parsed=urlparse(url)
        suffix=Path(parsed.path).suffix.lower()
        if suffix not in ('.mp4','.webm','.ogv','.ogg','.mov','.m4v'):
            suffix='.media'
        digest=hashlib.sha256(url.encode()).hexdigest()
        p=self.path('source-'+digest+suffix)
        if p.exists():
            if p.stat().st_size>settings['max_media_bytes']:
                raise ValueError('Media byte limit exceeded')
            return p
        tmp=self.path(p.name+'.part')
        max_bytes=int(settings['max_media_bytes'])
        total=0
        try:
            with httpx.stream(
                'GET',
                url,
                follow_redirects=True,
                timeout=httpx.Timeout(15,read=120),
                headers={'User-Agent':os.environ.get('SWARM_HTTP_USER_AGENT','DaSwarm/0.2 live media ingestion')},
            ) as response:
                response.raise_for_status()
                length=response.headers.get('content-length')
                if length and int(length)>max_bytes:
                    raise ValueError('Media byte limit exceeded')
                with tmp.open('wb') as fh:
                    for chunk in response.iter_bytes(1024*256):
                        total+=len(chunk)
                        if total>max_bytes:
                            raise ValueError('Media byte limit exceeded')
                        fh.write(chunk)
            tmp.replace(p)
            return p
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def asset(self,obj,settings):
        meta=obj.get('metadata') or {}
        if meta.get('fixture'):
            return self.fixture()
        url=meta.get('media_url')
        if not url:
            raise ValueError('Candidate has no authorized media asset; metadata-only candidates cannot be analyzed as video')
        return self.fetch(str(url),str(meta.get('provider') or ''),settings)

    def probe(self,p,settings):
        if p.stat().st_size>settings['max_media_bytes']:
            raise ValueError('Media byte limit exceeded')
        result=subprocess.run(
            ['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],
            capture_output=True,text=True,check=True,timeout=20
        )
        probe=json.loads(result.stdout)
        video=next((s for s in probe['streams'] if s['codec_type']=='video'),None)
        if not video:
            raise ValueError('Media asset has no video stream')
        duration=float(probe['format'].get('duration') or video.get('duration') or 0)
        if duration<=0:
            raise ValueError('Could not determine video duration')
        if duration>settings['max_duration_seconds'] or max(video['width'],video['height'])>settings['max_resolution']:
            raise ValueError('Media dimensions/duration exceed policy')
        has_audio=any(s.get('codec_type')=='audio' for s in probe['streams'])
        return {
            'duration_seconds':duration,
            'width':video['width'],
            'height':video['height'],
            'codec':video['codec_name'],
            'has_audio':has_audio,
            'bytes':p.stat().st_size,
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
        }

    def fingerprint(self,p,settings):
        probe=self.probe(p,settings)
        result=subprocess.run(
            ['ffmpeg','-nostdin','-v','error','-ss',str(probe['duration_seconds']/2),'-i',str(p),
             '-frames:v','1','-vf','scale=8:8,format=gray','-f','rawvideo','pipe:1'],
            capture_output=True,check=True,timeout=30
        )
        pixels=result.stdout
        if len(pixels)!=64:
            raise ValueError('Could not fingerprint media')
        mean=sum(pixels)/64
        bits=''.join('1' if px>=mean else '0' for px in pixels)
        return {'sha256':probe['sha256'],'perceptual_hash':format(int(bits,2),'016x')}

    def render(self,source,key,segments,settings):
        source_probe=self.probe(source,settings)
        duration=source_probe['duration_seconds']
        p=self.path(key+'.mp4')
        tmp=self.path(key+'.part.mp4')
        if not segments or len(segments)>20:
            raise ValueError('Storyboard requires 1–20 atoms')
        filters=[]
        inputs=[]
        if source_probe['has_audio']:
            for i,s in enumerate(segments):
                a,b=float(s['start']),float(s['end'])
                if not 0<=a<b<=duration:
                    raise ValueError('Atom range outside source media')
                filters.extend([
                    f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]',
                    f'[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]'
                ])
                inputs.append(f'[v{i}][a{i}]')
            filters.append(''.join(inputs)+f'concat=n={len(segments)}:v=1:a=1[v][a]')
            args=['ffmpeg','-nostdin','-y','-i',str(source),'-filter_complex',';'.join(filters),
                  '-map','[v]','-map','[a]','-c:v','libx264','-threads','1','-c:a','aac',
                  '-movflags','+faststart',str(tmp)]
        else:
            for i,s in enumerate(segments):
                a,b=float(s['start']),float(s['end'])
                if not 0<=a<b<=duration:
                    raise ValueError('Atom range outside source media')
                filters.append(f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]')
                inputs.append(f'[v{i}]')
            filters.append(''.join(inputs)+f'concat=n={len(segments)}:v=1:a=0[v]')
            args=['ffmpeg','-nostdin','-y','-i',str(source),'-filter_complex',';'.join(filters),
                  '-map','[v]','-an','-c:v','libx264','-threads','1','-movflags','+faststart',str(tmp)]
        self.run(args,timeout=180)
        tmp.replace(p)
        probe=self.probe(p,settings)
        self.store(p)
        return {'key':p.name,'probe':probe,'renderer':'ffmpeg','source_media_sha256':source_probe['sha256'],'live_content':True}

    def store(self,p):
        endpoint=os.environ.get('SWARM_OBJECT_STORE_ENDPOINT')
        if not endpoint:
            return
        import boto3
        client=boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=os.environ['SWARM_OBJECT_STORE_ACCESS_KEY'],
            aws_secret_access_key=os.environ['SWARM_OBJECT_STORE_SECRET_KEY']
        )
        bucket=os.environ.get('SWARM_OBJECT_STORE_BUCKET','manu-swarm')
        try:
            client.head_bucket(Bucket=bucket)
        except client.exceptions.ClientError:
            client.create_bucket(Bucket=bucket)
        client.upload_file(str(p),bucket,p.name)
