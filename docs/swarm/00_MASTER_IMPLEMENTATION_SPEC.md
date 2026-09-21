# Manu-Swarm-Test — Turnkey Master Implementation Specification
Version: 1.0-preimplementation
Status: IMPLEMENTATION READY
Upstream base: `Simpleyyt/ai-manus`
Pinned upstream commit: `496547ce6a5f599333138342ec126a7ea8ec9646`

## 1. Product Definition

Manu-Swarm-Test is an object-centric autonomous media-intelligence, synthesis, distribution, observability, and learning system built as an extension of AI-Manus.

Its core lifecycle is:

```text
DISCOVER
  → NORMALIZE
  → DEDUPLICATE
  → ANALYZE
  → ATOMIZE
  → CLUSTER
  → SCORE
  → ROUTE
  → SYNTHESIZE (optional/conditional)
  → REVIEW (policy/config dependent)
  → PUBLISH
  → COLLECT METRICS
  → UPDATE AUDIENCE / ROUTING MODELS
```

The application includes a Palantir-style object-centric command center in which every meaningful entity, relationship, action, task, metric, alert, and historical transition is inspectable and causally traceable.

## 2. Non-Negotiable Architecture Invariants

1. Accounts, agents, workers, and content objects are separate concepts.
2. Workers are ephemeral and may service multiple accounts over time.
3. Every important entity has a canonical `object_id`.
4. Every important relationship is an explicit typed edge.
5. Every meaningful state transition emits a durable event.
6. Events carry `trace_id`, `correlation_id`, and `causation_id`.
7. Discovery eligibility is separate from exact-asset automatic-publish eligibility.
8. Unknown-provenance media remains useful for intelligence, motif learning, synthesis planning, and human review.
9. The UI shares selection, filter, and time context across compatible views.
10. The LLM decides high-level intent; deterministic code performs brittle execution.
11. Queues are at-least-once; every handler must be idempotent.
12. All external side effects require idempotency keys and persisted execution records.
13. The global graph is never dumped wholesale into the browser.
14. Dense relationship data has matrix/aggregate/table alternatives.
15. Every published post can be traced backward to discovery and forward to downstream learning.
16. Every human/system command that changes state is auditable.
17. V1 can operate fully with simulated/test accounts before platform credentials exist.
18. No model/provider choice is hard-coded into the domain model.

## 3. Implementation Target

### Existing upstream retained
- Python/FastAPI backend
- Vue 3 + TypeScript + Vite frontend
- MongoDB for upstream AI-Manus session/agent state
- Redis for upstream coordination
- Docker sandbox
- Browser tooling and VNC
- AI-Manus planner/executor/tool system

### Manu-Swarm additions
- PostgreSQL + pgvector
- Redis Streams for swarm event fan-out
- S3-compatible object storage (MinIO locally)
- Celery worker classes / queues
- object ontology
- append-only swarm event ledger
- command/query APIs
- realtime swarm WebSocket
- command center UI
- media analysis/synthesis pipeline
- account routing and evaluation pipeline

ClickHouse is explicitly optional and deferred until real telemetry volume justifies it.

## 4. Repository Layout

```text
Manu-Swarm-Test/
├── upstream AI-Manus files...
├── backend/app/swarm/
│   ├── domain/
│   │   ├── models/
│   │   ├── services/
│   │   ├── repositories/
│   │   └── policies/
│   ├── application/
│   │   ├── commands/
│   │   ├── queries/
│   │   ├── handlers/
│   │   ├── projectors/
│   │   └── subscriptions/
│   ├── infrastructure/
│   │   ├── postgres/
│   │   ├── redis/
│   │   ├── object_store/
│   │   ├── media/
│   │   ├── platform_adapters/
│   │   └── telemetry/
│   └── interfaces/
│       ├── api/
│       └── websocket/
├── frontend/src/swarm/
│   ├── api/
│   ├── shell/
│   ├── pages/
│   ├── components/
│   ├── stores/
│   ├── types/
│   └── design/
├── migrations/
├── docs/
└── tests/
```

## 5. Domain Object Contract

Every domain object extends:

```python
class SwarmObject:
    id: UUID
    object_type: SwarmObjectType
    version: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    tags: list[str]
    metadata: dict[str, Any]
```

Required object types:

- Candidate
- ContentAtom
- Composition
- Account
- AudienceGenome
- Source
- Creator
- TrendCluster
- ViralMotif
- Task
- AgentRun
- Worker
- Sandbox
- MediaAsset
- Post
- MetricSnapshot
- Experiment
- Alert
- Decision
- Annotation
- SavedInvestigation

## 6. Event Contract

```python
class SwarmEvent:
    event_id: UUID
    sequence: int
    event_type: str
    object_id: UUID | None
    object_type: str | None
    actor_type: str
    actor_id: str | None
    timestamp: datetime
    trace_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    severity: str
    payload: dict[str, Any]
    schema_version: int
    idempotency_key: str | None
```

Events are append-only. Corrections are represented by subsequent events.

## 7. Command Handling Rules

Every command handler MUST:

1. authorize/validate the command;
2. derive or accept an idempotency key;
3. load current object version;
4. reject stale optimistic-concurrency writes;
5. perform deterministic state transition;
6. persist domain change transactionally;
7. append event(s);
8. publish realtime notification only after durable commit;
9. enqueue derived work through an outbox;
10. return canonical object references.

Do not dual-write database + queue without an outbox or equivalent transactional handoff.

## 8. Queue Semantics

Delivery: at least once.

Every task must contain:

```yaml
task_id:
task_type:
object_ref:
trace_id:
correlation_id:
causation_event_id:
idempotency_key:
priority:
attempt:
max_attempts:
resource_class:
created_at:
not_before:
```

Worker semantics:

- claim with lease;
- heartbeat while running;
- update lease before expiry;
- mark success transactionally;
- exponential backoff with jitter;
- dead-letter after max attempts;
- cancellation token checked at safe points;
- duplicate delivery returns prior result when idempotency record exists.

Resource classes:

- `io`
- `browser`
- `cpu_media`
- `gpu_media`
- `llm`
- `render`
- `publisher`

## 9. Side-Effect Guard

Publishing and other externally visible actions require a persisted `ExecutionIntent`:

```yaml
execution_id:
action_type:
target_account_id:
input_object_ids:
idempotency_key:
requested_at:
status:
external_result_id:
attempt_count:
last_error:
```

A retried publisher must look up the execution intent before performing the side effect.

## 10. Media Pipeline Contract

### Analysis

```text
video
 → metadata extraction
 → scene/shot segmentation
 → frame sampling
 → transcript
 → OCR/on-screen text
 → audio features
 → semantic embeddings
 → temporal saliency
 → affect/arousal
 → atomization
 → candidate genome
```

### Synthesis

```text
eligible source atoms / original assets / generated assets
 → story plan
 → edit decision list
 → deterministic render
 → QC
 → variants
 → composition object
```

Deterministic rendering uses FFmpeg first. Generative editing is optional and provider-pluggable.

## 11. Scoring Interfaces

No score freezes model weights in code.

```python
score_breakout(candidate, context) -> ScoreResult
score_candidate(candidate, context) -> ScoreResult
score_route(candidate_or_composition, account, context) -> ScoreResult
score_atom(atom, query_or_account, context) -> ScoreResult
score_composition(composition, account, context) -> ScoreResult
```

Every score result includes:

```yaml
score:
model_version:
feature_snapshot:
explanation:
uncertainty:
created_at:
```

This preserves reproducibility.

## 12. Provenance Routing

Discovery is high-recall.

Provenance states:

- OWNED
- CREATOR_PERMISSION
- LICENSED
- PUBLIC_DOMAIN
- UNKNOWN
- RESTRICTED

Default route policy:

```text
OWNED / CREATOR_PERMISSION / LICENSED / PUBLIC_DOMAIN
    → may be eligible for automatic exact-asset publishing.

UNKNOWN
    → remains fully available for analysis, trend detection,
      motif extraction, synthesis planning, concept recreation,
      source discovery, and human review.
    → exact-asset automatic publishing defaults to REVIEW_REQUIRED.

RESTRICTED
    → intelligence/reference use only unless status changes.
```

Policy behavior must be feature-flagged/configurable without changing the domain schema.

## 13. UI Contract

Global shell:

```text
CommandBar
NavRail
ContextPanel
MainWorkspace
ObjectInspector
TimeRail
```

Global stores:

- selection
- filters
- time
- workspace
- streams
- alerts
- object cache

Required workspaces:

- Overview
- Operations
- Content Universe
- Graph
- Trends
- Accounts
- Synthesis
- Experiments
- Infrastructure
- Audit & Replay

All views consume canonical ObjectRefs.

## 14. Realtime Contract

Endpoint: `/api/v1/ws/swarm`

The stream is ordered by monotonically increasing `sequence`.

Reconnect protocol:

1. client supplies `last_sequence`;
2. server replays events `(last_sequence, current]`;
3. client applies idempotently;
4. server switches connection to live stream.

No client is allowed to rely on WebSocket delivery as the sole durable record.

## 15. Replay Contract

Replay state is generated from read-model projections at a requested timestamp or from deterministic event reconstruction.

`LIVE` and `REPLAY` are globally shared modes.

Replay must never mutate live state.

## 16. Persistence Boundaries

PostgreSQL:
- canonical swarm domain state
- object edges
- event ledger
- execution intents
- experiments
- annotations
- saved investigations
- read-model projections

pgvector:
- content/account/source embeddings at moderate scale

Redis:
- ephemeral cache
- realtime stream fanout
- queue broker/coordination
- worker heartbeats

S3/MinIO:
- original media
- proxy media
- thumbnails
- audio extracts
- transcripts
- rendered compositions
- manifests

MongoDB:
- upstream AI-Manus session/agent state only unless a deliberate migration ADR changes this.

## 17. Database Migration Rule

All Manu-Swarm PostgreSQL schema changes use Alembic.

Never edit a deployed schema manually.

Migration IDs are committed with the feature that needs them.

## 18. Secrets

Secrets are references, never regular domain object fields.

Use environment variables for local development and a secret-provider interface for production.

Platform tokens, LLM keys, and object-store credentials MUST NOT appear in:
- event payloads,
- logs,
- object metadata,
- saved investigations,
- browser-visible API responses.

## 19. Feature Flags

Required flags:

```text
SWARM_ENABLED
SWARM_REALTIME_ENABLED
SWARM_GRAPH_ENABLED
SWARM_SYNTHESIS_ENABLED
SWARM_REPLAY_ENABLED
SWARM_PUBLISH_ENABLED
SWARM_AUTOPUBLISH_ENABLED
SWARM_GENERATIVE_MEDIA_ENABLED
SWARM_CLICKHOUSE_ENABLED
```

V1 defaults `SWARM_PUBLISH_ENABLED=false`.

## 20. Observability

All backend requests and jobs propagate:

- request_id
- trace_id
- correlation_id
- task_id when applicable
- object_id when applicable

Metrics:

- queue depth
- queue oldest age
- job throughput
- retry count
- dead letters
- worker heartbeat
- worker utilization
- model latency
- model token/cost usage
- media processing latency
- render latency
- API latency/error rate
- event projection lag
- WebSocket replay lag

## 21. Required Failure Behavior

### Worker crash
Lease expires → task becomes claimable → next worker retries idempotently.

### DB commit succeeds, queue publish fails
Outbox dispatcher retries until work is enqueued.

### Queue delivers twice
Idempotency key returns prior successful execution.

### Publisher times out after external platform accepted post
Retry checks execution intent/external lookup before reposting.

### WebSocket disconnect
Client reconnects with `last_sequence` and replays gap.

### Analyzer partially succeeds
Intermediate artifacts may persist, but object state advances only after required stage completion.

### Render fails
Composition remains intact; render task retries independently.

### Bad model output
Structured schema validation rejects output; repair/retry bounded by policy; then human/error route.

### Dense graph query
Server returns aggregate/limited neighborhood with truncation metadata rather than crashing or sending the global graph.

## 22. Initial Capacity Target

V1 engineering target, not a permanent limit:

- 50–500 new candidates/day
- 3–5 test account profiles
- 4 concurrent browser/agent tasks
- 1 concurrent GPU-heavy media job by default
- 10k+ domain objects
- 1M event records without functional degradation
- graph queries scoped to <=500 nodes by default
- realtime event batches <=500ms under normal load

Concurrency is configuration-driven.

## 23. Build Order

### Milestone A — Foundation
- fork/pin upstream commit
- add swarm module
- PostgreSQL/pgvector/MinIO services
- migrations
- base object/edge/event models
- repository interfaces
- outbox
- unit tests

### Milestone B — Control Plane Shell
- Vue swarm route
- command bar/nav/inspector/time rail
- mocked object service
- selection/filter/time stores

### Milestone C — Event + Realtime
- event ledger
- Redis stream
- websocket
- event projectors
- trace explorer
- replay gap handling

### Milestone D — Discovery Prototype
- source adapters
- candidate normalization
- dedupe
- candidate table/stream
- no real publishing

### Milestone E — Analysis / Atomization
- media ingestion
- FFmpeg probe/scene segmentation
- transcript interface
- embedding interface
- atom generation
- candidate genome

### Milestone F — Trends / Routing
- clustering
- breakout score
- account profiles
- routing
- Audience Genome v0

### Milestone G — Graph
- Explore Around
- causal graph
- matrix/aggregate alternative
- linked selection

### Milestone H — Synthesis
- edit decision list
- storyboard
- deterministic FFmpeg render
- variants
- QC
- provenance route display

### Milestone I — Test Publishing
- one platform adapter
- execution intents
- approval queue
- metrics ingestion
- publishing disabled by default until explicitly configured

### Milestone J — Learning
- experiment model
- contextual exploration interface
- audience genome updater
- model/version lineage

## 24. Definition of Implementation Complete

The first turnkey implementation is complete when the Acceptance Matrix passes and this end-to-end scenario works:

1. a source adapter discovers a video;
2. Candidate object + event are persisted;
3. UI receives it live;
4. media pipeline analyzes and atomizes it;
5. candidate joins a trend cluster;
6. router matches it to one of the fake/test accounts;
7. user can Explore Around the Candidate;
8. provenance/trace is visible;
9. Synthesis creates an edit plan;
10. FFmpeg renders a composition variant;
11. review action changes state and is audited;
12. with publishing disabled, a simulated platform adapter produces a fake Post;
13. fake metric samples arrive;
14. account projection/Audience Genome updates;
15. Audit & Replay can reconstruct the lifecycle;
16. stopping/restarting a worker during the scenario does not duplicate external side effects or lose durable events.

## 25. Explicit Non-Goals for First Turnkey Build

- maintaining one browser per social account
- dedicated graph database
- Kubernetes
- fully autonomous account creation
- automatic publishing of unknown-provenance exact assets
- training proprietary foundation models
- perfect viral prediction
- simultaneously supporting every social platform
- implementing every generative video technique in V1

These are expansion points, not prerequisites.

## 26. Handoff Rule

Astra should treat this master spec, the two detailed specs, the codices, schemas, state machines, event catalog, SQL schema, queue contracts, and acceptance tests as the implementation contract.

If a coding decision conflicts with an invariant, preserve the invariant unless a documented ADR explicitly supersedes it.
