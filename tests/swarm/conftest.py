import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
import pytest
from app.swarm.infrastructure.database import Database
from app.swarm.application.service import Service
from app.swarm.domain.contracts import Command

@pytest.fixture
def service(tmp_path,monkeypatch):
    monkeypatch.setenv('SWARM_MEDIA_ROOT',str(tmp_path/'media'))
    monkeypatch.setenv('SWARM_LOCAL_ONLY','true')
    postgres=os.environ.get('SWARM_TEST_POSTGRES_DSN')
    if postgres:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url
        from uuid import uuid4
        database='swarm_test_'+uuid4().hex
        admin=create_engine(postgres,isolation_level='AUTOCOMMIT')
        with admin.connect() as c:c.execute(text('CREATE DATABASE '+database))
        dsn=make_url(postgres).set(database=database).render_as_string(hide_password=False)
    else:
        monkeypatch.delenv('SWARM_OBJECT_STORE_ENDPOINT',raising=False)
        dsn='sqlite:///'+str(tmp_path/'swarm.db')
    service=Service(Database(dsn));service.initialize()
    yield service
    service.db.engine.dispose()
    if postgres:
        with admin.connect() as c:c.execute(text('DROP DATABASE '+database+' WITH (FORCE)'))
        admin.dispose()

def command(service,action,obj=None,**payload):
    from uuid import uuid4
    return service.execute(Command(action=action,object_id=obj['id'] if obj else None,
        expected_version=obj['version'] if obj else None,idempotency_key=str(uuid4()),payload=payload))
