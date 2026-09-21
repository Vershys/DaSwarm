"""Native Windows executable entry, built by PyInstaller in GitHub Actions."""
import os
import subprocess
import sys
from pathlib import Path
root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
env=dict(os.environ,DASWARM_BUNDLE=str(root/'project.zip'))
subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'launcher.ps1')],env=env,check=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
