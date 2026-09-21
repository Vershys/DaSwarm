"""Build one portable Windows .cmd containing launcher and complete source bundle."""
import base64
import io
import json
import subprocess
import zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
output=root/'dist-swarm';output.mkdir(exist_ok=True)
paths=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
# Include new tracked-for-release files even before final commit, but never local secrets.
paths+=['scripts/launcher.ps1','scripts/package_launcher.py','scripts/launcher_entry.py']
buffer=io.BytesIO()
with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name in sorted(set(paths)):
        p=root/name
        if not name or not p.is_file() or name.startswith(('.bootstrap/','.github/workflows/bootstrap-','release/')):continue
        z.writestr(name,p.read_bytes())
    if 'UPSTREAM_PIN' not in paths:
        z.writestr('UPSTREAM_PIN','Simpleyyt/ai-manus\n496547ce6a5f599333138342ec126a7ea8ec9646\n')
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
