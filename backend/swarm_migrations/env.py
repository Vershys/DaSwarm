from alembic import context
from app.swarm.infrastructure.database import metadata, Database
engine=context.config.attributes.get('engine') or Database().engine
with engine.connect() as connection:
    context.configure(connection=connection,target_metadata=metadata)
    with context.begin_transaction(): context.run_migrations()
