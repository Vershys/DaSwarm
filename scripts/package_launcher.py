"""Build one portable Windows .cmd containing launcher and complete source bundle."""
import base64
import io
import json
import subprocess
import zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
output=root/'dist-swarm';output.mkdir(exist_ok=True)
# Read committed Git blobs, not checkout bytes: Windows checkout may convert shell
# scripts to CRLF, which makes their Linux interpreter paths invalid in containers.
entries=[]
for record in subprocess.check_output(['git','ls-tree','-rz','HEAD'],cwd=root).split(b'\0'):
    if not record: continue
    attributes,name=record.split(b'\t',1)
    mode,kind,sha=attributes.decode().split()
    name=name.decode()
    if kind!='blob' or name.startswith(('.bootstrap/','.github/workflows/bootstrap-','release/')): continue
    entries.append((name,mode,sha))
blobs=subprocess.run(['git','cat-file','--batch'],input=''.join(sha+'\n' for _,_,sha in entries).encode(),cwd=root,check=True,stdout=subprocess.PIPE).stdout
buffer=io.BytesIO();offset=0
with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name,mode,sha in entries:
        header_end=blobs.index(b'\n',offset)
        actual,kind,size=blobs[offset:header_end].decode().split()
        assert actual==sha and kind=='blob'
        offset=header_end+1;data=blobs[offset:offset+int(size)];offset+=int(size)+1
        info=zipfile.ZipInfo(name);info.create_system=3
        info.external_attr=int(mode,8)<<16;info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,data)
archive=buffer.getvalue();(output/'project.zip').write_bytes(archive)
ps=(root/'scripts/launcher.ps1').read_text()
# The .cmd extracts its two embedded resources and launches the WinForms control window.
header=r'''@echo off
setlocal
set "DASWARM_SELF=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$raw=[IO.File]::ReadAllText($env:DASWARM_SELF);$ps=$raw.Split(@('::DASWARM_PS::'),[StringSplitOptions]::None)[1].Split(@('::DASWARM_ZIP::'),[StringSplitOptions]::None)[0];$zip=$raw.Split(@('::DASWARM_ZIP::'),[StringSplitOptions]::None)[1];$dir=Join-Path $env:LOCALAPPDATA 'DaSwarm';[IO.Directory]::CreateDirectory($dir)|Out-Null;$env:DASWARM_BUNDLE=Join-Path $dir 'project.zip';[IO.File]::WriteAllBytes($env:DASWARM_BUNDLE,[Convert]::FromBase64String($zip.Trim()));$script=Join-Path $dir 'launcher.ps1';[IO.File]::WriteAllBytes($script,[Convert]::FromBase64String($ps.Trim()));& $script"
if errorlevel 1 pause
exit /b
'''
# Split markers must not appear literally in the extraction expression.
header=header.replace("@('::DASWARM_PS::')","@(('::DASWARM_'+'PS::'))").replace("@('::DASWARM_ZIP::')","@(('::DASWARM_'+'ZIP::'))")
cmd=header+'::DASWARM_PS::\n'+base64.b64encode(ps.encode('utf-8-sig')).decode()+'\n::DASWARM_ZIP::\n'+base64.b64encode(archive).decode()+'\n'
(output/'DaSwarm-Launcher.cmd').write_text(cmd,newline='\r\n')
print(json.dumps({'launcher':str(output/'DaSwarm-Launcher.cmd'),'source_bundle':str(output/'project.zip'),'bytes':len(cmd)}))
