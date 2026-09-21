# Architecture Decision Records — Pre-Approved

## ADR-001: Extend AI-Manus rather than rewrite it
Status: Accepted.
Reason: upstream already supplies the agent loop, browser sandbox, VNC, MongoDB/Redis session layer, and Vue frontend.

## ADR-002: Pin initial implementation to upstream commit
Status: Accepted.
Pinned SHA: 496547ce6a5f599333138342ec126a7ea8ec9646.
Reason: prevents upstream drift during first implementation.

## ADR-003: PostgreSQL + pgvector is the swarm domain store
Status: Accepted.
MongoDB remains upstream session/agent state unless later migration is justified.

## ADR-004: No graph database in V1
Status: Accepted.
Store explicit edges in PostgreSQL. Add specialized graph storage only after measured query evidence.

## ADR-005: Event ledger + projections
Status: Accepted.
Durable append-only events provide traceability/replay; read projections provide UI speed.

## ADR-006: Transactional outbox
Status: Accepted.
Required for reliable DB→queue/event handoff.

## ADR-007: At-least-once jobs + idempotent handlers
Status: Accepted.
Avoid pretending exactly-once distributed execution exists.

## ADR-008: Deterministic publisher adapters
Status: Accepted.
LLM chooses intent/content; adapter performs platform call.

## ADR-009: FFmpeg-first synthesis
Status: Accepted.
Generative editing is an optional plugin, not a prerequisite.

## ADR-010: High-recall discovery
Status: Accepted.
Unknown provenance does not delete intelligence value; it changes exact-asset publish route.

## ADR-011: Object-centric UI
Status: Accepted.
All major views exchange canonical ObjectRefs and shared selection/time/filter context.

## ADR-012: ClickHouse deferred
Status: Accepted.
Add only after PostgreSQL metrics/event projections exhibit measured scale constraints.
