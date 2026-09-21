# Manu-Swarm-Test — Astra 6 Handoff Bundle

Status: **Implementation ready**

Upstream base: `Simpleyyt/ai-manus`  
Pinned commit: `496547ce6a5f599333138342ec126a7ea8ec9646`

## Start here

1. `00_MASTER_IMPLEMENTATION_SPEC.md`
2. `15_ASTRA6_TURNKEY_HANDOFF_PROMPT.md`
3. `13_ACCEPTANCE_TEST_MATRIX.md`
4. `PREIMPLEMENTATION_LOGIC_CHECKS.md`

## Bundle contents

- `00_MASTER_IMPLEMENTATION_SPEC.md`
- `01_THEORY_SPEC.md`
- `02_CORE_CODEX.yaml`
- `03_CONTROL_PLANE_SPEC.md`
- `04_CONTROL_PLANE_CODEX.yaml`
- `05_IMPLEMENTATION_BLUEPRINT.yaml`
- `06_STATE_MACHINES.yaml`
- `07_EVENT_CATALOG.yaml`
- `08_QUEUE_WORKER_CONTRACTS.yaml`
- `09_API_CONTRACT.yaml`
- `10_DATABASE_SCHEMA.sql`
- `11_SECURITY_RELIABILITY_OPERATIONS.md`
- `12_ENV_CONTRACT.example`
- `13_ACCEPTANCE_TEST_MATRIX.md`
- `14_ADRS.md`
- `15_ASTRA6_TURNKEY_HANDOFF_PROMPT.md`
- `16_DOMAIN_CONTRACTS.schema.json`
- `17_ONTOLOGY_RELATION_CONTRACTS.yaml`
- `18_PROJECTION_CONTRACTS.yaml`
- `19_UI_VIEW_DATA_CONTRACTS.yaml`
- `20_DETERMINISTIC_E2E_FIXTURE.yaml`
- `21_RUNTIME_SERVICES_CONTRACT.yaml`
- `PREIMPLEMENTATION_LOGIC_CHECKS.md`
- `preflight_validate.py`

## Preflight

Run:

```bash
python preflight_validate.py
```

The current bundle passes all automated pre-implementation contract checks.

## Implementation gate

Astra should not declare the first turnkey build complete until all P0 acceptance tests pass and the deterministic end-to-end fixture can be replayed after a full service restart.
