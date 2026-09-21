"""Executable ontology and policy contracts; no vendor-specific domain types."""
from pathlib import Path
from typing import Any
import os
import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3] / 'swarm_contracts'
def contract(name):
    return yaml.safe_load((ROOT / name).read_text())
BLUEPRINT = contract('05_IMPLEMENTATION_BLUEPRINT.yaml')
STATES = contract('06_STATE_MACHINES.yaml')
RELATIONS = contract('17_ONTOLOGY_RELATION_CONTRACTS.yaml')
RESOURCES = contract('08_QUEUE_WORKER_CONTRACTS.yaml')['task_to_resource']

class Conflict(ValueError): pass
class NotFound(ValueError): pass
class Forbidden(ValueError): pass

class ObjectRef(BaseModel):
    objectId: str
    objectType: str
    version: int | None = None

class Command(BaseModel):
    action: str
    object_id: str | None = None
    expected_version: int | None = None
    idempotency_key: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)
    mode: str = 'LIVE'

DEFAULT_CONFIG = {
    'routing_weights': {'semantic_fit': .55, 'novelty': .2, 'quality': .25},
    'model_version': 'heuristic-v1', 'lease_seconds': 30, 'max_attempts': 5,
    'max_media_bytes': 100_000_000, 'max_duration_seconds': 300,
    'max_resolution': 3840, 'graph_limit': 500,
    'exploration_fraction': .1, 'paused_queues': [],
    'providers': {'transcription': 'placeholder', 'embedding': 'placeholder', 'vision': 'placeholder'},
}

def validate_transition(kind, previous, target):
    if kind in STATES and target not in STATES[kind]['transitions'].get(previous, []):
        raise Conflict(f'Illegal {kind} transition: {previous} → {target}')

def validate_metadata(value):
    """Reject secrets at the write boundary, rather than try to redact history later."""
    forbidden = {'password', 'token', 'access_token', 'api_key', 'authorization', 'cookie', 'secret', 'credentials'}
    def walk(x):
        if isinstance(x, dict):
            for k,v in x.items():
                if k.lower() in forbidden or k.lower().endswith(('_password','_token','_api_key','_secret')):
                    raise Forbidden('Use secret_ref; credentials cannot enter domain state')
                walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
        elif isinstance(x,str):
            for k,v in os.environ.items():
                if any(s in k.upper() for s in ('PASSWORD','SECRET','API_KEY','ACCESS_TOKEN')) and len(v)>5 and v in x:
                    raise Forbidden('Configured secret detected in input')
    walk(value)
    return value
