"""Isolated component-development host; production integrates with upstream app.main."""
from app.swarm.interfaces.api import create_app
app=create_app()
