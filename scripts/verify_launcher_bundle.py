"""Check the cross-platform source payload shipped in the single-file launcher."""
import base64
import io
from pathlib import Path
from zipfile import ZipFile
root=Path(__file__).resolve().parents[1]
cmd=(root/'dist-swarm/DaSwarm-Launcher.cmd').read_bytes()
with ZipFile(io.BytesIO(base64.b64decode(cmd.split(b'::DASWARM_ZIP::')[-1].strip()))) as bundle:
    names=bundle.namelist()
    assert len(names)==len(set(names)), 'Duplicate bundle entries'
    assert b'496547ce6a5f599333138342ec126a7ea8ec9646' in bundle.read('UPSTREAM_PIN')
    for name in names:
        if name.endswith('.sh'):
            assert b'\r\n' not in bundle.read(name), f'Windows line endings break Linux shell: {name}'
    assert b'pull_policy: build' in bundle.read('docker-compose.yml')
    assert b'chmod +x /app/dev.sh' in bundle.read('mockserver/Dockerfile')
print('Launcher source bundle passed Linux shell, pin, and startup checks')
