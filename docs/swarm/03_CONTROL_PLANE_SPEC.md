# Manu-Swarm-Test — Command Center / Control Plane Specification
Version: 0.2
Status: Architecture freeze candidate
Companion to: `Manu-Swarm-Test_THEORY_SPEC.md`

---

## 1. Purpose

The **Manu-Swarm Command Center** is the human-facing control plane for the entire swarm.

It is not a conventional KPI dashboard. It is an **object-centric operational intelligence environment**: every candidate, content atom, source, trend, account, task, agent run, worker, composition, experiment, post, metric, alert, and decision can be inspected, linked, filtered, replayed, and traced to its causes and effects.

The design is inspired by the operational interaction patterns visible in Palantir Gotham/Foundry — ontology-backed objects, linked views, graph exploration, map/timeline coordination, selection-driven detail panels, saved explorations, and action-oriented object views — but the visual system and implementation are original to Manu-Swarm.

The central UX invariant is:

> **Any important thing visible anywhere in the system must resolve to a canonical Swarm Object ID, and selecting that object must propagate context to every compatible view.**

The central backend invariant is:

> **Every meaningful state transition must be traceable through an append-only event ledger using correlation, causation, and trace identifiers.**

---

## 2. Research-Driven Interaction Principles

### 2.1 Overview → filter/zoom → detail

The primary interaction model follows the information-visualization principle of providing an overview first, then filtering/zooming, then details on demand. Manu-Swarm implements this at three nested scales:

1. System overview.
2. Domain/workspace overview.
3. Object detail / causal trace.

### 2.2 Coordinated multiple views

All compatible views participate in a shared selection/filter context.

Selecting a candidate in a table can simultaneously:

- highlight its node in the graph,
- focus its discovery timestamp in the timeline,
- highlight its source and trend cluster,
- open its object inspector,
- show related tasks and worker runs,
- filter media/metric panels.

This is **brushing and linking** at the application level.

### 2.3 Object ontology as the interaction substrate

The UI does not pass around arbitrary page-specific data structures. It passes canonical object references.

```ts
type ObjectRef = {
  objectId: string
  objectType: SwarmObjectType
  version?: number
}
```

All major tables, graphs, timelines, media cards, and alerts render or resolve ObjectRefs.

### 2.4 Temporal context is global

A global time model exists in two modes:

- `LIVE`
- `REPLAY`

Every time-aware workspace reads the same `TimeContext`.

```ts
type TimeContext = {
  mode: "LIVE" | "REPLAY"
  rangeStart: string
  rangeEnd: string
  cursor: string | null
}
```

The timeline is not decorative. It changes the object state shown elsewhere.

### 2.5 Sparse relations use graph views; dense relations use matrix/aggregate views

Node-link diagrams are excellent for following paths and exploring small/sparse neighborhoods, but become difficult as graphs become dense. The UI therefore supports:

- node-link graph for path-oriented exploration,
- adjacency matrix for dense neighborhoods,
- aggregate cluster view above graph complexity thresholds,
- table/list fallback for high-cardinality object sets.

### 2.6 Provenance is visible

Analytic and operational history is a first-class object.

Users must be able to answer:

- Why did this candidate exist?
- Who/what found it?
- Which model analyzed it?
- Why was it routed to this account?
- Which source atoms became this composition?
- Which worker rendered it?
- Which post resulted?
- What happened after publishing?
- Which later model update used that result?

---

## 3. Screen Anatomy

Desktop-first target: 1440px+ wide, optimized at 1920×1080 and larger.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ TOP COMMAND BAR                                                            │
│ Search / Command Palette | LIVE/REPLAY | Health | Alerts | Budget | User   │
├──────┬───────────────────────────────┬──────────────────────────┬───────────┤
│      │                               │                          │           │
│ NAV  │ CONTEXT / FILTER / LAYERS     │ MAIN WORKSPACE           │ INSPECTOR │
│ RAIL │                               │                          │           │
│      │                               │                          │           │
│      │                               │                          │           │
│      │                               │                          │           │
├──────┴───────────────────────────────┴──────────────────────────┴───────────┤
│ GLOBAL TIME RAIL / EVENT DENSITY / REPLAY CURSOR                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Top command bar

Always visible.

Elements:

- global search / command palette,
- workspace breadcrumb,
- LIVE / REPLAY toggle,
- ingestion rate,
- queue lag,
- active workers,
- active accounts,
- unresolved alerts,
- current LLM/media-compute spend,
- storage use,
- connection indicator,
- user/system controls.

Global command palette shortcut: `Ctrl/Cmd + K`.

Examples:

```text
> candidate VID-8291
> account NatureMoments
> trend robot dogs
> trace post POST-483
> open synthesis COMP-912
> pause publisher queue
> replay 2026-09-20 18:00
```

### 3.2 Navigation rail

Primary workspaces:

1. Overview
2. Operations
3. Content Universe
4. Graph
5. Trends
6. Accounts
7. Synthesis
8. Experiments
9. Infrastructure
10. Audit & Replay

The rail is icon-first but reveals labels on expansion.

### 3.3 Context panel

The left context panel changes by workspace and contains:

- object type filters,
- saved views,
- source/platform filters,
- status filters,
- dynamic histograms,
- layer visibility,
- graph relation toggles,
- metric selectors,
- saved investigations.

### 3.4 Object inspector

Right-side, collapsible. Never a blocking modal for ordinary inspection.

Tabs:

- Summary
- Links
- Timeline
- Metrics
- Provenance
- Runs
- Assets
- Raw

Inspector actions are contextual:

```text
Explore Around
Open Source
Open Media
Route
Send to Synthesis
Compare
Pin
Annotate
Replay Trace
Pause/Resume (when operational object)
```

### 3.5 Global TimeRail

Collapsible bottom panel.

Displays:

- event density histogram,
- publish events,
- candidate discoveries,
- model decisions,
- worker failures,
- account events,
- alert markers,
- selected object's lifecycle.

Controls:

- drag time range,
- scrub cursor,
- jump to event,
- LIVE button,
- playback speed for replay,
- compare two time windows.

---

## 4. Visual Language

The visual system should feel like an operational intelligence console rather than a consumer analytics app.

### 4.1 Density

- compact spacing,
- visible information hierarchy,
- minimal decorative whitespace,
- collapsible detail instead of modal proliferation,
- tables and lists remain first-class,
- charts must support a decision or exploration task.

### 4.2 Color semantics

Base UI is neutral graphite/steel.

Semantic color is reserved for state:

```text
healthy / active      → cool green
attention / degraded  → amber
failure / critical    → red
queued / inactive     → slate
selected / focus      → cyan-blue
experimental          → violet
replay / historical   → desaturated blue-gray
```

Do not encode object types only by color; pair color with icon/shape/label.

### 4.3 Typography

- compact sans-serif for UI and data,
- monospaced font for IDs, traces, hashes, timestamps and logs,
- tabular numerals for metrics.

### 4.4 Motion

Motion is functional:

- subtle transition when selection propagates,
- pulse only for genuinely live/new events,
- no perpetual decorative animation,
- graph physics settle quickly and can be frozen.

---

## 5. Workspaces

## 5.1 Overview — "Situation Board"

Purpose: answer “what is happening right now?”

Layout:

```text
┌───────────────────────────────┬──────────────────────────────┐
│ SYSTEM HEALTH                 │ ACTIVE ALERTS                │
│ queues/workers/ingest         │ severity + object refs       │
├───────────────────────────────┼──────────────────────────────┤
│ LIVE CANDIDATE STREAM         │ TREND SURGES                 │
│ latest + best breakout        │ velocity clusters            │
├───────────────────────────────┼──────────────────────────────┤
│ ACCOUNT FLEET                 │ PUBLISH / RESPONSE           │
│ health + next action          │ posts + performance          │
├───────────────────────────────┴──────────────────────────────┤
│ RECENT CAUSAL EVENTS / SYSTEM ACTIVITY                      │
└──────────────────────────────────────────────────────────────┘
```

Key behaviors:

- every tile is drillable,
- selections propagate to inspector,
- no orphan KPI card with no underlying object set.

---

## 5.2 Operations — "Swarm Live"

Purpose: observe work in motion.

Primary visualization: stage lanes.

```text
DISCOVER → FETCH → ANALYZE → ATOMIZE → ROUTE → SYNTHESIZE → REVIEW → PUBLISH
```

Each task card is an ObjectRef.

Alternative views:

- lane view,
- worker assignment view,
- queue depth/time plot,
- causal dependency graph.

Task card:

```text
TASK-84912
ANALYZE_VIDEO
Candidate VID-291
Worker gpu-01
Running 00:41
Trace T-938ad
```

Clicking it shows:

- parent candidate,
- task events,
- agent/model calls,
- worker logs,
- media assets,
- downstream dependent tasks.

---

## 5.3 Content Universe

Purpose: high-volume content intelligence.

Default:

- virtualized object table,
- media preview drawer,
- filter/histogram context panel.

Columns:

```text
Candidate
Source
Age
Category
Breakout
Arousal
Novelty
Quality
Best Account
Route Value
Trend
Provenance
State
```

Views:

- Table
- Card wall
- Embedding map
- Timeline
- Similarity neighborhood

Selecting candidates supports compare mode.

---

## 5.4 Graph — "Swarm Ontology"

Purpose: inspect relationships.

Node types:

- Candidate
- Atom
- Composition
- Account
- Source
- Creator
- TrendCluster
- ViralMotif
- Task
- AgentRun
- Worker
- Post
- Experiment
- Alert
- Decision
- Asset

Edge types:

```text
FOUND_BY
SOURCED_FROM
HAS_ATOM
MEMBER_OF_TREND
MATCHES_ACCOUNT
ROUTED_TO
DERIVED_FROM
USES_ATOM
GENERATED_BY
EXECUTED_BY
PUBLISHED_AS
MEASURED_BY
PART_OF_EXPERIMENT
TRIGGERED
CAUSED
UPDATED_MODEL
SIMILAR_TO
```

Core action: **Explore Around**.

Example:

```text
Explore Around Candidate VID-291
  depth = 2
  relations = [FOUND_BY, MEMBER_OF_TREND, MATCHES_ACCOUNT, DERIVED_FROM]
```

Graph modes:

- force-directed,
- layered causal,
- radial neighborhood,
- adjacency matrix,
- cluster aggregate.

For dense neighborhoods, automatically recommend matrix/cluster mode rather than drawing unreadable “hairballs.”

---

## 5.5 Trends

Purpose: detect and understand emergent content movements.

Views:

- trend velocity table,
- cluster bubble/embedding view,
- time series,
- cross-platform heat grid,
- candidate stream by cluster,
- source contribution chart.

Trend object detail:

```text
Trend: "robot dogs in public"
Started: 11:32
Acceleration: +412%
Sources: 73
Platforms: 4
Best account fit:
  TechClips .91
  Unexpected .84
Saturation: .38
```

---

## 5.6 Accounts — "Fleet"

Each account is a durable object.

Fleet table:

```text
Account
Platform
State
Audience Size
Posts 24h
Next Action
Queue
Health
7d Growth
Audience Genome Drift
Recent Saturation
```

Account detail:

- audience genome radar/distribution,
- semantic cluster performance,
- motif performance,
- duration response curve,
- post timeline,
- source mix,
- current experiments,
- recent failures,
- related candidates awaiting route.

---

## 5.7 Synthesis Studio

Purpose: make the Synthesis Fabric inspectable and controllable.

Screen:

```text
┌──────────────────────────────┬──────────────────────────────┐
│ SOURCE / MEDIA PREVIEW       │ COMPOSITION PREVIEW          │
│                              │                              │
├──────────────────────────────┴──────────────────────────────┤
│ SOURCE TIMELINE WITH ATOMS / SALIENCY / AROUSAL            │
├─────────────────────────────────────────────────────────────┤
│ STORYBOARD: [A1] [A4] [B2] [GEN] [C7]                      │
├──────────────────────────────┬──────────────────────────────┤
│ VARIANTS                     │ PREDICTED RESPONSE           │
│ 8s / 14s / 23s               │ retention/share/account-fit  │
└──────────────────────────────┴──────────────────────────────┘
```

Atom timeline overlays:

- scene cuts,
- transcript,
- saliency,
- affect,
- payoff,
- setup dependency,
- selected clips.

Drag/drop ObjectRefs from candidate/atom lists into storyboard.

---

## 5.8 Experiments

Purpose: track causal learning rather than merely report metrics.

Experiment object:

```text
EXP-102
Account: NatureMoments
Question: Does immediate payoff outperform 2s setup?
Variants: A/B/C
Primary metric: completion-adjusted shares
Status: running
Exposure: 31%
```

Views:

- experiment table,
- variant outcome distributions,
- confidence/uncertainty,
- audience segment response,
- historical experiment lineage.

---

## 5.9 Infrastructure

Purpose: see the physical swarm.

Views:

- worker grid,
- CPU/GPU/RAM,
- queue depth,
- queue age,
- task throughput,
- sandbox count,
- browser/VNC sessions,
- error rates,
- API latency,
- model usage,
- storage,
- network/download/upload rates.

A worker is clickable like every other object.

Worker detail:

- hardware,
- active task,
- recent tasks,
- logs,
- crashes,
- resource timeline,
- sandbox links,
- agent runs.

---

## 5.10 Audit & Replay

Purpose: reconstruct history.

Input:

```text
Object ID / Trace ID / Post ID / Time Range
```

Output:

```text
09:41:08 Scout-3 discovered VID-291
09:41:10 metadata normalized
09:41:16 video analysis started on gpu-01
09:41:49 7 atoms produced
09:41:52 classified into Trend T-88
09:41:55 Router matched NatureMoments .94
09:42:02 Synthesis requested
09:43:11 Composition COMP-91 rendered
09:45:00 Review approved
09:50:00 Post POST-122 published
10:05:00 metrics sample #1
...
18:00:00 AudienceGenome v73 updated
```

The replay cursor can reconstruct the dashboard as it looked at a historical point.

---

## 6. The Swarm Ontology

All core objects share:

```py
class SwarmObject:
    id: UUID
    object_type: str
    version: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    tags: list[str]
    metadata: dict
```

Canonical object types:

```text
Candidate
ContentAtom
Composition
Account
AudienceGenome
Source
Creator
TrendCluster
ViralMotif
Task
AgentRun
Worker
Sandbox
MediaAsset
Post
MetricSnapshot
Experiment
Alert
Decision
Annotation
SavedInvestigation
```

All relationships are explicit edges:

```py
class SwarmEdge:
    id: UUID
    from_object_id: UUID
    to_object_id: UUID
    edge_type: str
    created_at: datetime
    valid_from: datetime | None
    valid_to: datetime | None
    metadata: dict
```

This is the linking substrate for the entire UI.

---

## 7. Event Ledger and Causal Trace

Every meaningful change emits a durable `SwarmEvent`.

```py
class SwarmEvent:
    event_id: UUID
    sequence: int
    event_type: str

    object_id: UUID | None
    object_type: str | None

    actor_type: str       # agent | worker | human | scheduler | platform
    actor_id: str | None

    timestamp: datetime

    trace_id: UUID
    correlation_id: UUID
    causation_id: UUID | None

    severity: str
    payload: dict

    schema_version: int
```

### 7.1 IDs

- `trace_id`: one end-to-end story.
- `correlation_id`: group of related operations.
- `causation_id`: exact parent event.

Example:

```text
DISCOVERED
  └─ caused ANALYSIS_QUEUED
        └─ caused ANALYSIS_COMPLETED
              └─ caused ROUTE_DECIDED
                    └─ caused COMPOSITION_REQUESTED
                          └─ caused PUBLISH_QUEUED
```

This supports both debugging and human sensemaking.

---

## 8. Storage Architecture

### 8.1 Existing AI-Manus services retained

- MongoDB — AI-Manus session and agent state.
- Redis — existing message queues / session coordination.
- Docker sandbox layer.

### 8.2 Manu-Swarm domain services added

**PostgreSQL + pgvector**
- canonical swarm objects,
- relationships,
- durable event ledger,
- account state,
- experiment state,
- saved investigations,
- vector references / moderate-scale embeddings.

**Redis Streams**
- live event fanout,
- queue notifications,
- worker heartbeat stream,
- UI realtime stream.

**MinIO / S3-compatible object storage**
- source media,
- proxies,
- thumbnails,
- rendered compositions,
- transcripts,
- derived assets.

**ClickHouse — optional phase 2**
- high-volume time-series telemetry,
- post metric snapshots,
- worker/queue telemetry,
- event aggregation.

### 8.3 Why no graph database initially

The product needs graph *visualization* immediately, but not necessarily a dedicated graph database.

Initial graph traversal can be served from:

```text
swarm_objects
swarm_edges
```

using indexed SQL and recursive CTEs.

Add a graph database only if measured traversal/query workloads justify it.

---

## 9. Read Model / Projection Architecture

The event ledger is not queried directly for every screen.

Projectors create read-optimized views:

```text
events
  │
  ├──► account_projection
  ├──► candidate_projection
  ├──► operations_projection
  ├──► worker_projection
  ├──► trend_projection
  ├──► experiment_projection
  ├──► alert_projection
  └──► trace_projection
```

This provides fast UI loading while preserving causal history.

---

## 10. API Structure

Prefix:

```text
/api/v1/swarm
```

### 10.1 Objects

```text
GET  /objects/{id}
POST /objects/query
GET  /objects/{id}/links
GET  /objects/{id}/timeline
GET  /objects/{id}/trace
```

### 10.2 Graph

```text
POST /graph/neighborhood
POST /graph/path
POST /graph/matrix
```

### 10.3 Operations

```text
GET  /operations/summary
GET  /queues
GET  /workers
GET  /workers/{id}
GET  /tasks/{id}
```

### 10.4 Content

```text
POST /candidates/query
GET  /candidates/{id}
GET  /candidates/{id}/atoms
GET  /trends
GET  /trends/{id}
```

### 10.5 Synthesis

```text
GET  /compositions/{id}
POST /compositions
POST /compositions/{id}/variants
POST /compositions/{id}/render
```

### 10.6 Accounts

```text
GET  /accounts
GET  /accounts/{id}
GET  /accounts/{id}/audience-genome
GET  /accounts/{id}/performance
```

### 10.7 Experiments

```text
GET  /experiments
POST /experiments
GET  /experiments/{id}
```

### 10.8 Replay

```text
GET /traces/{trace_id}
GET /replay/snapshot?at={timestamp}
```

---

## 11. Realtime Protocol

WebSocket:

```text
/api/v1/ws/swarm
```

Client subscribes to channels:

```json
{
  "op": "subscribe",
  "topics": [
    "objects",
    "tasks",
    "workers",
    "queues",
    "alerts",
    "metrics",
    "traces"
  ]
}
```

Event envelope:

```json
{
  "type": "swarm.event",
  "topic": "tasks",
  "sequence": 182934,
  "serverTime": "2026-09-20T21:18:22.193-05:00",
  "event": {
    "eventId": "...",
    "eventType": "TASK_STATE_CHANGED",
    "objectId": "...",
    "objectType": "Task",
    "traceId": "...",
    "correlationId": "...",
    "causationId": "...",
    "payload": {}
  }
}
```

Client reconnect:

```text
lastSequence = 182934
```

Server replays missing events before resuming live stream.

---

## 12. Frontend State Model

Add Pinia stores:

```text
selectionStore
timeStore
filterStore
workspaceStore
streamStore
objectCacheStore
alertStore
```

### 12.1 Global selection context

```ts
type SelectionState = {
  primary: ObjectRef | null
  selected: ObjectRef[]
  hovered: ObjectRef | null
  pinned: ObjectRef[]
}
```

Any view can publish selection.

Any view can subscribe.

### 12.2 Filter context

Filters are serializable and shareable.

```ts
type FilterExpression =
  | { op: "eq"; property: string; value: unknown }
  | { op: "gt"; property: string; value: number }
  | { op: "lt"; property: string; value: number }
  | { op: "in"; property: string; values: unknown[] }
  | { op: "and"; children: FilterExpression[] }
  | { op: "or"; children: FilterExpression[] }
  | { op: "link"; edgeType: string; target: FilterExpression }
```

Saved investigations persist:

- filters,
- time range,
- selected layers,
- graph position,
- open objects,
- annotations,
- workspace layout.

---

## 13. Frontend Technology

Upstream AI-Manus currently uses:

- Vue 3,
- TypeScript,
- Vite,
- Vue Router,
- Axios,
- mitt,
- NoVNC,
- Monaco,
- Reka UI,
- Tailwind utilities.

Manu-Swarm extends it with:

```text
Pinia                     global state
@tanstack/vue-query       server-state caching
Apache ECharts            charts/time-series/heat grids
Sigma.js + Graphology     WebGL graph
MapLibre GL JS            optional geographic views
TanStack Virtual          large lists/tables
HLS.js                    streamed media preview when needed
```

Do not replace the upstream stack merely to obtain a dashboard library.

---

## 14. Frontend Repository Structure

```text
frontend/src/
├── swarm/
│   ├── api/
│   │   ├── objects.ts
│   │   ├── graph.ts
│   │   ├── operations.ts
│   │   ├── content.ts
│   │   ├── accounts.ts
│   │   ├── synthesis.ts
│   │   ├── experiments.ts
│   │   └── realtime.ts
│   │
│   ├── shell/
│   │   ├── SwarmShell.vue
│   │   ├── CommandBar.vue
│   │   ├── NavRail.vue
│   │   ├── ContextPanel.vue
│   │   ├── ObjectInspector.vue
│   │   └── TimeRail.vue
│   │
│   ├── pages/
│   │   ├── OverviewPage.vue
│   │   ├── OperationsPage.vue
│   │   ├── ContentUniversePage.vue
│   │   ├── GraphPage.vue
│   │   ├── TrendsPage.vue
│   │   ├── AccountsPage.vue
│   │   ├── SynthesisPage.vue
│   │   ├── ExperimentsPage.vue
│   │   ├── InfrastructurePage.vue
│   │   └── AuditReplayPage.vue
│   │
│   ├── components/
│   │   ├── object/
│   │   ├── graph/
│   │   ├── timeline/
│   │   ├── charts/
│   │   ├── tables/
│   │   ├── media/
│   │   ├── alerts/
│   │   ├── workers/
│   │   └── synthesis/
│   │
│   ├── stores/
│   │   ├── selection.ts
│   │   ├── time.ts
│   │   ├── filters.ts
│   │   ├── workspace.ts
│   │   ├── streams.ts
│   │   └── alerts.ts
│   │
│   ├── types/
│   │   ├── object.ts
│   │   ├── event.ts
│   │   ├── filter.ts
│   │   └── workspace.ts
│   │
│   └── design/
│       ├── tokens.css
│       ├── density.css
│       └── object-types.ts
```

---

## 15. Backend Repository Structure

Fit the existing AI-Manus domain/infrastructure/interfaces pattern.

```text
backend/app/swarm/
├── domain/
│   ├── models/
│   │   ├── object.py
│   │   ├── edge.py
│   │   ├── event.py
│   │   ├── trace.py
│   │   └── workspace.py
│   │
│   ├── services/
│   │   ├── object_service.py
│   │   ├── graph_service.py
│   │   ├── trace_service.py
│   │   ├── replay_service.py
│   │   └── selection_service.py
│   │
│   └── repositories/
│       ├── object_repository.py
│       ├── event_repository.py
│       └── edge_repository.py
│
├── application/
│   ├── commands/
│   ├── queries/
│   ├── projectors/
│   └── subscriptions/
│
├── infrastructure/
│   ├── postgres/
│   ├── redis/
│   ├── object_store/
│   └── telemetry/
│
└── interfaces/
    ├── api/
    │   ├── objects.py
    │   ├── graph.py
    │   ├── operations.py
    │   ├── content.py
    │   ├── accounts.py
    │   ├── synthesis.py
    │   ├── experiments.py
    │   └── replay.py
    └── websocket/
        └── swarm_stream.py
```

---

## 16. Cross-View Interaction Contract

Views must implement:

```ts
interface SwarmView {
  acceptsSelection(types: SwarmObjectType[]): boolean
  onSelectionChanged(selection: SelectionState): void
  onTimeContextChanged(time: TimeContext): void
  onFiltersChanged(filters: FilterExpression[]): void
}
```

### Example

User selects Post `POST-122`.

System:

1. Object Inspector loads `POST-122`.
2. Graph highlights:
   - account,
   - composition,
   - source candidates,
   - experiment,
   - metric snapshots.
3. TimeRail zooms to post lifecycle.
4. Accounts page highlights owning account.
5. Synthesis panel can open generating composition.
6. Audit view exposes trace.
7. Metric panels scope to POST-122.

No page-specific glue code should be required beyond adapters to the shared selection contract.

---

## 17. Object Drag/Drop Contract

Custom media type:

```text
application/x-manu-swarm-object
```

Payload:

```json
[
  {
    "objectId": "...",
    "objectType": "ContentAtom"
  }
]
```

Examples:

- drag Candidate into graph,
- drag Atom into Synthesis storyboard,
- drag Account into comparison panel,
- drag Trend into investigation workspace.

---

## 18. Saved Investigations

A SavedInvestigation is the Manu-Swarm equivalent of a persistent analytical workspace.

```yaml
SavedInvestigation:
  id: uuid
  title: string
  created_by: string
  filters: [...]
  time_context: {...}
  selected_objects: [...]
  pinned_objects: [...]
  visible_layers: [...]
  graph_state: {...}
  annotations: [...]
  layout: {...}
```

The goal is to let an analyst close the app and reopen the *same line of reasoning*.

---

## 19. Alerts

Alerts are objects, not toast messages.

```yaml
Alert:
  id: uuid
  severity: info|warning|critical
  type: queue_lag|worker_failure|account_failure|trend_surge|cost_spike|...
  related_objects: [...]
  opened_at: datetime
  acknowledged_at: datetime|null
  resolved_at: datetime|null
  status: open|acknowledged|resolved
```

An alert can be:

- searched,
- filtered,
- linked,
- annotated,
- replayed,
- included in an investigation.

---

## 20. Command/Action Model

Read and write operations are visually distinct.

Actions include:

```text
Pause Account
Pause Queue
Retry Task
Cancel Task
Re-route Candidate
Request Synthesis
Approve Composition
Reject Composition
Publish Draft
Open Experiment
Pin to Investigation
Annotate
```

Every command emits events into the ledger.

No invisible writeback.

---

## 21. Performance / Scale Rules

### UI

- virtualize tables beyond ~200 visible rows,
- avoid rendering thousands of DOM graph nodes,
- use WebGL for graph/map,
- aggregate graph neighborhoods before visual overload,
- batch realtime updates,
- decouple live ingestion from animation frame rate.

### Realtime

Target:

- queue/worker status updates: 1–5 Hz,
- high-volume candidate events: batch every 250–500 ms,
- metrics refresh: adaptive, normally 5–60 seconds,
- critical alerts: immediate.

### Graph

Default neighborhood limits:

```text
soft node limit: 500
hard interactive node limit: 2,000
```

Above this, require:

- cluster aggregation,
- relation filtering,
- matrix mode,
- sampled/summary mode.

Exact thresholds are measured during implementation, not treated as universal constants.

---

## 22. Testing

### 22.1 Unit

- filter serializer,
- selection propagation,
- time context,
- object/edge schemas,
- event causality,
- projector idempotency.

### 22.2 Integration

- event → projection → WebSocket → view update,
- selection in table → graph + inspector,
- replay snapshot consistency,
- dropped object → synthesis storyboard,
- command → event ledger → object update.

### 22.3 E2E

Playwright scenarios:

```text
discover candidate
→ observe live event
→ open candidate
→ Explore Around
→ route to account
→ send to synthesis
→ approve
→ inspect causal trace
```

### 22.4 Load

Simulate:

- 500 candidate events/min,
- 50 active workers,
- 5k tracked accounts,
- 100k graph objects,
- 1M+ event ledger records.

The UI should query subsets/projections, never dump the global graph into the browser.

---

## 23. Implementation Phases

### Phase UI-0 — Shell

Build:

- SwarmShell,
- NavRail,
- CommandBar,
- ObjectInspector,
- TimeRail,
- design tokens,
- routing.

Use mocked data.

### Phase UI-1 — Object substrate

Build:

- SwarmObject/SwarmEdge schemas,
- object query API,
- SelectionStore,
- FilterStore,
- object inspector,
- virtualized object table.

### Phase UI-2 — Event substrate

Build:

- durable SwarmEvent ledger,
- Redis live stream,
- `/ws/swarm`,
- TimeStore,
- event timeline,
- trace explorer.

### Phase UI-3 — Operational views

Build:

- Overview,
- Operations,
- Infrastructure,
- alerts.

### Phase UI-4 — Intelligence views

Build:

- Content Universe,
- Trends,
- Accounts.

### Phase UI-5 — Graph

Build:

- sparse node-link explorer,
- Explore Around,
- matrix mode,
- linked brushing.

### Phase UI-6 — Synthesis

Build:

- source preview,
- atom timeline,
- storyboard,
- variant comparison,
- render job monitoring.

### Phase UI-7 — Audit/Replay

Build:

- point-in-time snapshots,
- trace reconstruction,
- replay mode.

### Phase UI-8 — Experiments

Build:

- experiment objects,
- variants,
- uncertainty,
- model-update lineage.

---

## 24. Research Basis

### Palantir interaction patterns

Public Palantir documentation demonstrates several interaction principles directly applicable to Manu-Swarm:

- Object Explorer makes object data the unit of search/exploration and allows users to move between object sets, tables, object views and visual analyses.
- Workshop applications use object data and links as primary building blocks, with linked widgets and writeback actions.
- Object Tables expose selected object sets to downstream widgets.
- Map interfaces separate layer/find/histogram context panels from a right-side selection panel and a temporal series/timeline area.
- Vertex graph exploration supports time scrubbing, histogram filtering, and relationship exploration.
- Gotham/Foundry cross-application interactions transport stable object identifiers between views.

### Visual analytics research

- Shneiderman's information-seeking mantra supports overview → zoom/filter → details-on-demand.
- Coordinated multiple views / brushing and linking support iterative exploration across views.
- Research comparing node-link and matrix graph representations shows that matrices often become more readable for larger/dense graphs, while node-link remains strong for path finding.
- Analytic provenance research argues that preserving analysis history supports sensemaking, collaboration, audit and accountability.
- Event-sourcing observability research supports tracking requests and their relationship to events in an event log to improve debugging and root-cause analysis.

---

## 25. Control Plane Invariants

1. Every important visual entity is a Swarm Object.
2. Every object has a canonical ID.
3. Every relationship is explicit.
4. Every state-changing command emits an event.
5. Every event has trace/correlation/causation metadata.
6. Every major view shares selection, filter and time context.
7. Detail appears in a persistent inspector, not a modal maze.
8. Dense graph data automatically offers alternate representations.
9. LIVE and REPLAY are first-class modes.
10. Alerts are durable objects.
11. Saved investigations preserve analyst context.
12. The dashboard never becomes a wall of disconnected KPI cards.
13. Realtime updates are batched and query-scoped.
14. The global graph is never blindly rendered in the browser.
15. Any post should be traceable all the way back to discovery and forward to learning.
