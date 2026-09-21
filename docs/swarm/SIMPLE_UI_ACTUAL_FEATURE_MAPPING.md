# DaSwarm Simple UI → Real Capability Architecture

Status: implementation design  
Date: 2026-09-21  
Product rule: **one UI, novice-first, progressively configurable. No separate “advanced mode.”**

## 1. UX research translated into DaSwarm rules

The UI follows established usability guidance:

- **Progressive disclosure:** show the small set of frequent actions first; reveal specialized options only when requested (Nielsen Norman Group; GitHub Primer; GOV.UK Details).
- **Do not hide commonly needed information:** disclosure is for secondary information, not the core task (GOV.UK).
- **Good defaults:** a new user should be able to begin without configuring the system first; settings should be minimized (Apple HIG Settings).
- **Task-specific settings stay beside the task:** source choice and discovery breadth belong beside Start Discovery; retry leases and graph limits do not (Apple HIG Settings).
- **Visibility of system status:** always show what the system is doing and whether the user must act (NN/g usability heuristics).
- **Recognition over recall:** display source names, presets, stage names and available actions rather than requiring knowledge of queue names or object states (NN/g).
- **Plain language:** use real-world terms such as “Find videos”, “Analyze”, “Build clip”, “Review”; keep internal terms like DEDUPLICATE, gpu_media and lease_seconds out of the default surface (NN/g match-to-real-world heuristic).
- **Long-running work must remain visibly active:** show named stages and indeterminate activity when percentage is unknown; do not invent percentages (Atlassian progress guidance; GitHub loading guidance).
- **User control and recovery:** Start, Pause, Resume, Cancel and Retry should map to durable backend commands and be reversible where possible.
- **One disclosure layer:** avoid nested accordion mazes. Use clear page sections plus one Settings surface with grouped sections.

Research references:
- Nielsen Norman Group, “Progressive Disclosure” and “10 Usability Heuristics for User Interface Design”
- Apple Human Interface Guidelines, “Settings” and “Disclosure controls”
- GOV.UK Design System, “Details”, “Accordion”, “Tabs”
- GitHub Primer, “Progressive disclosure”, “Loading”, “Forms”
- Atlassian Design System, “Progress bar”

## 2. Primary product experience

The default screen answers four questions:

1. **Is DaSwarm ready?**
2. **What can I start?**
3. **What is it doing right now?**
4. **What needs me next?**

The page should be organized as:

```text
DaSwarm                                      Ready ●     Settings

DISCOVERY
[ Start discovery ]   [ Pause ]
Sources: YouTube · TikTok · Creator Watchlist        [ Configure sources ]
Strategy: Balanced ▼        Budget: 500 / cycle

CURRENT WORK
Find        Understand        Build        Review
 ● 128         ● 23            ● 4          ! 2

Needs you
[ Composition 12 ] Ready to review              [ Review ]
[ Candidate 91 ]   Provenance needs review      [ Review ]

Recent finds
thumbnail | title | source | why found | stage

Outputs
preview | account | status | action

Activity details ▸
```

No queue names, object UUIDs, lease values, event cursors, JSON or internal resource classes are visible by default.

## 3. Progressive configuration

There is one Settings surface, not a second UI.

### Sources
Frequent and task-specific. Also accessible next to Start Discovery.

- enabled sources
- source search/query
- creator watchlists
- source cadence
- per-source item budget

Backed by durable `Source` objects.

### Discovery
- strategy preset: Focused / Balanced / Explore
- exploration fraction
- cycle budget
- concurrency target (only when runtime supports live resizing)

Backed by swarm config plus discovery scheduler configuration.

### Analysis
- media duration/size limits
- provider selection where an installed adapter exists
- analysis depth preset

Backed by existing `max_media_bytes`, `max_duration_seconds`, `max_resolution`, provider registry.

### Routing
- semantic fit
- novelty
- quality

Backed directly by existing `routing_weights`.

### Creation
- automatic composition on/off
- render defaults
- human review required

Backed by synthesis feature flags/config and Composition state machine.

### Publishing
- publishing enabled
- auto-publish enabled
- account-level pause/resume

Backed by feature flags, `Account` state, and PUBLISH queue.

### Reliability
Collapsed and explicitly technical:
- max attempts
- queue pause controls
- lease timeout
- dead-letter tasks
- worker diagnostics

Backed by existing retry/queue/task framework.

### Data & diagnostics
Collapsed:
- event trace
- graph neighborhood
- replay
- raw object metadata
- worker identities

These are existing capabilities, but they are diagnostic/data tools rather than the primary operating workflow.

## 4. Existing UI controls that already map to real backend features

| Human control | Existing backend mapping | Status |
|---|---|---|
| Run local demo | `command(action="discover")` | Working now; fixture only |
| Pause processing type | `configure(paused_queues=[...])` or pause_queue | Working now |
| Resume processing | same | Working now |
| Search current objects | `POST /objects/query` | Working now |
| See current work counts | `GET /operations/summary` | Working now |
| See queue counts | `GET /queues` | Working now |
| Select a video | Candidate object + selection store | Working now |
| See extracted moments | `GET /candidates/{id}/atoms` | Working now |
| Build clip | `command(action="synthesize", atom_ids=[...])` | Working now |
| Render | COMPOSE schedules RENDER | Working now |
| Approve/reject | `command("approve"|"reject")` | Working now |
| Publish test post | `command("publish")` | Working now; simulated |
| Pause/resume account | `command("pause_account"|"resume_account")` | Working now |
| Cancel a task | `command("cancel_task")` | Working now |
| Edit routing weights | `command("configure", routing_weights=...)` | Working now |
| Edit retry policy | `command("configure", max_attempts/lease_seconds)` | Working now |
| Edit media limits | `command("configure", max_media_*)` | Working now |
| Live activity | `/api/v1/ws/swarm` | Working now |
| Historical detail | timeline/trace/replay endpoints | Working now |
| Relationship detail | graph endpoints | Working now |

## 5. Controls that look simple but need one missing backend layer

### Start Discovery

The UI should call one human-level command:

```json
{
  "action": "start_discovery",
  "payload": {
    "source_ids": ["..."],
    "mode": "balanced",
    "budget": 500
  }
}
```

The command should **not** scrape anything itself. It should:

1. create an `AgentRun` / DiscoveryRun object,
2. schedule bounded `DISCOVER` tasks for enabled Sources,
3. persist those tasks using the existing jobs/outbox transaction,
4. let the dispatcher send them to `swarm.browser`,
5. let browser workers claim them through the existing lease/fencing mechanism.

This preserves DaSwarm's current durable orchestration model.

### Pause Discovery

No new worker mechanism is required. The human button can atomically add `DISCOVER` and optionally `FETCH_METADATA` to `paused_queues`.

### Stop Discovery

Pause prevents new claims but is not the same as stopping a run. Add:

```text
stop_discovery(run_id)
```

which marks the DiscoveryRun stopped and cancels its queued Task objects. Running tasks receive cancellation through the existing job cancellation field / lease checks.

### Configure Sources

Use existing `Source` objects. A Source should hold configuration, not code:

```json
{
  "object_type": "Source",
  "title": "YouTube Shorts · animals",
  "metadata": {
    "provider": "youtube",
    "strategy": "search",
    "query": "animal rescue",
    "cadence_seconds": 300,
    "item_budget": 100,
    "secret_ref": null
  }
}
```

Adapters are code; Sources are durable instances of adapter configuration.

## 6. Real Discovery connection to the existing worker framework

The queue contract already maps:

```text
DISCOVER -> browser
```

and Compose already runs:

```text
swarm_worker_browser
  queue = swarm.browser
```

Therefore do not create a second discovery execution system.

Implement a provider contract:

```python
class DiscoveryProvider(Protocol):
    name: str
    async def discover(self, source: SourceConfig, budget: int) -> list[DiscoveredItem]: ...
```

Then add `DISCOVER` handling to `Worker.prepare/apply`.

Flow:

```text
Start discovery
   ↓
Service.start_discovery
   ↓
Task(DISCOVER, Source A)
Task(DISCOVER, Source B)
Task(DISCOVER, Source C)
   ↓
transactional outbox
   ↓
Dispatcher
   ↓
Redis / Celery queue swarm.browser
   ↓
existing browser worker
   ↓
DiscoveryProvider
   ↓
structured DiscoveredItem[]
   ↓
Candidate objects + FOUND_BY / SOURCED_FROM edges
   ↓
NORMALIZE
   ↓
existing pipeline continues unchanged
```

The critical rule: **a discovery adapter ends at Candidate creation.** Everything after Candidate creation is already DaSwarm's pipeline.

## 7. Use AI-Manus without duplicating the agent runtime

AI-Manus already provides:

- planner,
- Manus agent loop,
- search toolkit,
- browser toolkit,
- sandbox,
- shell/file tools,
- persistent agent/session state.

Use that for *reasoning scouts*, not for deterministic platform plumbing.

Recommended split:

```text
Source adapter/API
    deterministic retrieval
            │
            ├─────────────┐
            ↓             ↓
      known source     ambiguous/exploratory task
            │             ↓
            │       AI-Manus Scout
            │       search/browser/planner
            │             ↓
            └──────► structured discoveries
                          ↓
                     Candidate intake
```

### AI-Manus Scout integration

Do not parse prose chat output.

Add a small swarm-specific reporting tool to an internal scout run:

```text
report_discovery({
  url,
  platform,
  platform_id,
  title,
  creator,
  published_at,
  metrics,
  discovery_reason,
  source_id
})
```

The Manus agent can browse/search using its existing tools and call `report_discovery` whenever it finds a candidate.

That tool writes through the same swarm Service transaction, producing Candidate objects and causal events.

This gives us:
- existing AI-Manus browser reasoning,
- existing planner/sandbox,
- structured swarm output,
- no fragile extraction of final chat text,
- full traceability.

## 8. Provider/capability registry: the UI must know what is actually installed

Currently provider configuration is hard-coded to placeholders and the UI can overstate capability.

Add a registry:

```python
CAPABILITIES = {
  "discovery": {
    "fixture": {"installed": True, "real": False},
    "youtube": {"installed": False, "real": True},
    "tiktok": {"installed": False, "real": True},
    "manus_scout": {"installed": False, "real": True}
  },
  "transcription": {...},
  "embedding": {...},
  "vision": {...},
  "publishing": {
    "simulated": {"installed": True, "real": False}
  }
}
```

Expose:

```text
GET /api/v1/swarm/capabilities
```

The frontend must render from this instead of hard-coded promises.

Examples:
- if no real discovery adapter is installed: show `Run Demo`, and `Internet discovery — configure provider`.
- after YouTube is installed: enable YouTube in Sources.
- if real publishing is unavailable: never display a live `Publish` action as if it were real.

## 9. Human stage model over the existing state machines

The default UI should translate technical states into five recognizable stages.

### Find
- Source active
- DISCOVER / FETCH_METADATA
- Candidate.DISCOVERED

### Understand
- NORMALIZE
- DEDUPLICATE
- ANALYZE_TEXT / ANALYZE_VIDEO
- TRANSCRIBE / EMBED
- ATOMIZE
- CLUSTER
- Candidate through ANALYZED

### Match
- ROUTE
- Candidate ROUTED / REVIEW_PENDING / HELD

### Build
- COMPOSE
- RENDER
- Composition DRAFT / RENDER_QUEUED / RENDERING

### Review & release
- Composition REVIEW / APPROVED
- PUBLISH
- COLLECT_METRICS
- UPDATE_MODEL

This is a **presentation projection**, not a new state machine. Keep the canonical states unchanged.

## 10. Progress rule

Do not manufacture a percentage from queue states.

Use:
- named stage,
- completed stage checkmarks,
- an indeterminate activity indicator for the active stage,
- exact counts where known (`23 analyzing`, `4 rendering`),
- a final success state.

A real percentage is allowed only when the underlying task reports measurable work units.

## 11. “Needs you” projection

The single most useful novice-facing panel is a derived action queue.

It can be computed from existing objects:

- Candidate `REVIEW_PENDING` -> “Review candidate”
- Composition `REVIEW` -> “Review clip”
- Task `DEAD_LETTER` -> “Job needs attention”
- Alert `OPEN` -> “System needs attention”
- Account `PAUSED/DEGRADED` -> “Account paused/problem”
- source missing required credential -> “Connect source”

No new primary domain object is required for this panel.

## 12. Settings mapping

### Visible beside Discovery
- enabled Source objects
- source strategy/query
- discovery budget
- exploration preset

### Settings → Content decisions
- routing weights
- account settings
- synthesis/review policy

### Settings → Limits
- max duration
- max media bytes
- max resolution

### Settings → Reliability
- retries
- queue pauses
- lease seconds

### Settings → Diagnostics
- graph limit
- trace/replay
- raw object/event data

Worker process concurrency currently comes from launcher/.env and Docker Compose. Do **not** show it as a live web setting until there is a real runtime-management endpoint; otherwise the UI would lie about applying it.

## 13. Minimal backend work required for real turnkey discovery

1. Add `DiscoveryProvider` contract and provider registry.
2. Add capabilities endpoint.
3. Add real `DISCOVER` worker handler.
4. Add `start_discovery` and `stop_discovery` commands.
5. Add DiscoveryRun/AgentRun lifecycle metadata and source-run relationships.
6. Add scheduler/repeat policy for continuous source polling.
7. Add candidate intake helper shared by deterministic adapters and Manus scouts.
8. Add one real provider.
9. Add the Manus `report_discovery` tool for exploratory scouts.
10. Add acceptance tests proving: Start button -> browser worker -> real provider fixture/server -> Candidate -> existing analysis pipeline.

Everything after Candidate intake should reuse the current pipeline rather than be redesigned.

## 14. Frontend implementation rule

The frontend should never call low-level queue or object operations directly from a prominent user action if the action represents a higher-level intention.

Bad:

```text
Pause ANALYZE_VIDEO queue
Pause EMBED queue
Pause TRANSCRIBE queue
```

Default UI:

```text
Analysis     [Pause]
```

The UI adapter translates that into the current configuration command with the appropriate queue names.

Likewise:

```text
Start discovery
```

maps to one orchestration command, even if it creates fifty Tasks.

This keeps the UI simple without making the backend simplistic.

## 15. Acceptance test for the “14–15 year old” rule

Give a new user only this goal:

> “Turn this on, find videos, and get a clip ready to review.”

Pass if the user can do it without:
- knowing what Celery, Redis, MinIO, Candidate, ContentAtom, queue lease, resource class, event cursor or pgvector means;
- editing JSON;
- opening developer documentation;
- entering a settings screen before starting;
- guessing whether the system is currently working.

They may open configuration if they *want* to change behavior, not because basic operation requires it.
