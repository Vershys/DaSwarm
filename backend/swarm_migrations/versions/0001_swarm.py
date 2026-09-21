"""Initial swarm schema, including a fenced job ledger and transactional projections."""
from alembic import op
from app.swarm.infrastructure.database import metadata
revision='0001_swarm'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    metadata.create_all(op.get_bind())
    if op.get_bind().dialect.name=='postgresql':
        op.execute('CREATE TABLE object_embeddings (object_id TEXT REFERENCES swarm_objects(id), embedding_kind TEXT NOT NULL, model_version TEXT NOT NULL, embedding vector(1536), PRIMARY KEY(object_id, embedding_kind, model_version))')
        op.execute("""CREATE FUNCTION swarm_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Event ledger is append-only'; END $$""")
        op.execute('CREATE TRIGGER immutable_swarm_events BEFORE UPDATE OR DELETE ON swarm_events FOR EACH ROW EXECUTE FUNCTION swarm_events_immutable()')

def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a tested backup')
