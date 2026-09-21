"""PostgreSQL source of truth. SQLite is explicitly an isolated test backend."""
import os
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer, Float,
                        JSON, ForeignKey, UniqueConstraint, Index, Text)
from sqlalchemy.dialects.postgresql import JSONB

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid4())
metadata = MetaData()
J = JSON().with_variant(JSONB, 'postgresql')
objects = Table('swarm_objects', metadata,
    Column('id',String,primary_key=True), Column('object_type',String,nullable=False,index=True),
    Column('version',Integer,nullable=False), Column('title',String,nullable=False),
    Column('status',String,nullable=False,index=True), Column('tags',J,nullable=False),
    Column('metadata',J,nullable=False), Column('created_at',String,nullable=False),Column('updated_at',String,nullable=False))
edges = Table('swarm_edges',metadata,
    Column('id',String,primary_key=True), Column('from_object_id',String,ForeignKey('swarm_objects.id'),index=True),
    Column('to_object_id',String,ForeignKey('swarm_objects.id'),index=True),Column('edge_type',String,index=True),
    Column('metadata',J),Column('created_at',String),Column('valid_from',String),Column('valid_to',String),
    UniqueConstraint('from_object_id','to_object_id','edge_type'))
events = Table('swarm_events',metadata,
    Column('sequence',Integer,primary_key=True,autoincrement=True),Column('event_id',String,unique=True),
    Column('event_type',String,index=True),Column('object_id',String,index=True),Column('object_type',String),
    Column('actor_type',String),Column('actor_id',String),Column('timestamp',String,index=True),
    Column('trace_id',String,index=True),Column('correlation_id',String),Column('causation_id',String),
    Column('severity',String),Column('payload',J),Column('schema_version',Integer),Column('idempotency_key',String))
outbox = Table('outbox',metadata,Column('id',String,primary_key=True),Column('topic',String),
    Column('message_key',String),Column('payload',J),Column('created_at',String),
    Column('dispatched_at',String),Column('attempts',Integer,default=0),Column('last_error',String))
idem = Table('idempotency_records',metadata,Column('key',String,primary_key=True),
    Column('operation',String),Column('fingerprint',String),Column('result',J),Column('created_at',String))
intents = Table('execution_intents',metadata,Column('execution_id',String,primary_key=True),
    Column('action_type',String),Column('target_account_id',String),Column('input_object_ids',J),
    Column('idempotency_key',String,unique=True),Column('status',String),Column('external_result_id',String),
    Column('attempt_count',Integer),Column('last_error',String),Column('requested_at',String),Column('updated_at',String))
jobs = Table('swarm_jobs',metadata,Column('task_id',String,ForeignKey('swarm_objects.id'),primary_key=True),
    Column('task_type',String,index=True),Column('object_ref',J),Column('trace_id',String),Column('correlation_id',String),
    Column('causation_event_id',String),Column('idempotency_key',String,unique=True),Column('priority',Integer),
    Column('attempt',Integer),Column('max_attempts',Integer),Column('resource_class',String),
    Column('created_at',String),Column('not_before',Float),Column('lease_until',Float),Column('lease_token',String),
    Column('worker_id',String),Column('cancelled',Integer),Column('status',String,index=True),Column('payload',J))
projections = Table('swarm_projections',metadata,Column('object_id',String,primary_key=True),
    Column('object_type',String,index=True),Column('last_sequence',Integer),Column('state',J))
config = Table('swarm_config',metadata,Column('id',Integer,primary_key=True),Column('version',Integer),Column('data',J))
scores = Table('score_records',metadata,Column('id',String,primary_key=True),Column('object_id',String,index=True),
    Column('target_object_id',String),Column('score_type',String),Column('score',Float),Column('uncertainty',Float),
    Column('model_version',String),Column('features',J),Column('explanation',J),Column('created_at',String))
# Independent simulated-platform ledger models remote acceptance across process crashes.
remote_posts = Table('simulated_platform_posts',metadata,Column('key',String,primary_key=True),
    Column('external_id',String,unique=True),Column('account_id',String),Column('created_at',String))
Index('ix_pending_outbox',outbox.c.dispatched_at,outbox.c.created_at)

class Database:
    def __init__(self, dsn=None):
        dsn=dsn or os.environ.get('SWARM_POSTGRES_DSN','postgresql+psycopg://manus:manus@postgres/manu_swarm')
        dsn=dsn.replace('postgresql+asyncpg','postgresql+psycopg')
        self.engine=create_engine(dsn,pool_pre_ping=True,
          **({'connect_args':{'check_same_thread':False}} if dsn.startswith('sqlite') else {}))
    def migrate(self):
        from alembic.config import Config
        from alembic import command
        from pathlib import Path
        cfg=Config(); cfg.set_main_option('script_location',str(Path(__file__).resolve().parents[3]/'swarm_migrations'))
        cfg.attributes['engine']=self.engine
        command.upgrade(cfg,'head')
