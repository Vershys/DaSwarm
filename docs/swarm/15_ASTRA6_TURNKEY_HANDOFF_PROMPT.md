# Astra 6 Turnkey Implementation Prompt

You are implementing **Manu-Swarm-Test** as a production-quality extension of the public `Simpleyyt/ai-manus` repository.

## Base
Pin the initial working tree to upstream commit:

`496547ce6a5f599333138342ec126a7ea8ec9646`

Do not silently move to a newer upstream commit during the first implementation. If a newer upstream revision is required, document the change as an ADR and reconcile incompatibilities explicitly.

## Authoritative files
Read these in this order:

1. `00_MASTER_IMPLEMENTATION_SPEC.md`
2. `01_THEORY_SPEC.md`
3. `03_CONTROL_PLANE_SPEC.md`
4. `05_IMPLEMENTATION_BLUEPRINT.yaml`
5. `06_STATE_MACHINES.yaml`
6. `07_EVENT_CATALOG.yaml`
7. `08_QUEUE_WORKER_CONTRACTS.yaml`
8. `09_API_CONTRACT.yaml`
9. `10_DATABASE_SCHEMA.sql`
10. `11_SECURITY_RELIABILITY_OPERATIONS.md`
11. `12_ENV_CONTRACT.example`
12. `13_ACCEPTANCE_TEST_MATRIX.md`
13. `14_ADRS.md`
14. `17_ONTOLOGY_RELATION_CONTRACTS.yaml`
15. `18_PROJECTION_CONTRACTS.yaml`
16. `19_UI_VIEW_DATA_CONTRACTS.yaml`
17. `20_DETERMINISTIC_E2E_FIXTURE.yaml`
18. `21_RUNTIME_SERVICES_CONTRACT.yaml`
19. `PREIMPLEMENTATION_LOGIC_CHECKS.md`

The YAML codices are machine-readable summaries; the Markdown specs control when prose and code disagree.

## Implementation behavior
- Build the project, do not merely write a plan.
- Preserve upstream AI-Manus features.
- Add Manu-Swarm behind `SWARM_ENABLED`.
- Use migrations.
- Add tests with each implementation milestone.
- Keep real publishing disabled by default.
- Build a simulated source adapter and simulated platform adapter so the entire lifecycle can run locally without credentials.
- Use deterministic fixtures so the end-to-end acceptance demo is reproducible.
- Do not hard-code LLM/vision/transcription/generative-media vendors into domain models.
- Do not introduce Kubernetes, a graph database, or ClickHouse unless a failing acceptance/performance test provides evidence they are necessary.

## Required first pass
Implement through Milestone C before branching into media intelligence:
1. foundation and storage,
2. object/edge/event schemas,
3. outbox/idempotency,
4. realtime WebSocket,
5. Command Center shell,
6. shared selection/filter/time stores,
7. trace/replay primitives.

Then implement discovery→analysis→routing→synthesis→simulated publishing in the defined build order.

## Completion gate
Do not state that the turnkey build is complete until all P0 tests in `13_ACCEPTANCE_TEST_MATRIX.md` pass.

When a design ambiguity appears:
1. preserve the architecture invariants,
2. prefer the simplest implementation satisfying the acceptance tests,
3. record irreversible or cross-cutting changes as ADRs,
4. continue implementation without stalling for cosmetic decisions.
