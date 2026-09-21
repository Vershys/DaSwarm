# Manu-Swarm Turnkey Acceptance Matrix

Astra must not declare the implementation complete until every P0 test passes.

| ID | Priority | Test | Pass condition |
|---|---|---|---|
| A01 | P0 | Boot | `docker compose up` starts upstream + PostgreSQL + Redis + MinIO + swarm services |
| A02 | P0 | Migration | Fresh database migrates with no manual SQL |
| A03 | P0 | Object CRUD | Candidate can be created, fetched, updated with optimistic version |
| A04 | P0 | Event durability | Candidate creation emits durable event with trace/correlation IDs |
| A05 | P0 | Outbox | Derived task survives broker outage and is eventually queued |
| A06 | P0 | Realtime | Browser receives candidate event over swarm WebSocket |
| A07 | P0 | Reconnect | Dropped WebSocket reconnects using `last_sequence` and fills gap |
| A08 | P0 | Idempotency | Duplicate task delivery produces one logical result |
| A09 | P0 | Worker crash | Kill worker mid-task; lease expires; another worker completes it |
| A10 | P0 | Discovery | Simulated source produces Candidate object visible in Content Universe |
| A11 | P0 | Analysis | Test video produces metadata, transcript/placeholder, embeddings/placeholder and atoms |
| A12 | P0 | Dedupe | Duplicate/near-duplicate test asset is linked rather than treated as unrelated |
| A13 | P0 | Trend | Multiple related candidates form/attach to a TrendCluster |
| A14 | P0 | Routing | Candidate receives reproducible account route score + explanation |
| A15 | P0 | Account separation | Same worker can execute tasks for two accounts without merging account state |
| A16 | P0 | Synthesis | Atom storyboard yields an FFmpeg-rendered Composition variant |
| A17 | P0 | Approval | Review/approve command changes state and emits audited event |
| A18 | P0 | Simulated publish | Publishing disabled or simulated adapter creates one fake Post with ExecutionIntent |
| A19 | P0 | Publish retry | Simulated timeout/retry does not create duplicate Post |
| A20 | P0 | Metrics | Fake metrics create MetricSnapshot linked to Post |
| A21 | P0 | Learning | MetricSnapshot triggers AudienceGenome projection/model update event |
| A22 | P0 | Graph | Explore Around Candidate returns bounded linked neighborhood |
| A23 | P0 | Linked UI | Selecting Candidate updates graph, inspector and TimeRail |
| A24 | P0 | Replay | Replay at prior timestamp reconstructs object lifecycle without mutating live data |
| A25 | P0 | Trace | Post can be traced backward to Candidate and forward to MetricSnapshot/model update |
| A26 | P0 | Unknown provenance | UNKNOWN candidate remains analyzable/routable and enters review rather than disappearing |
| A27 | P0 | Secrets | API responses/events/logs contain no configured secret values |
| A28 | P0 | Dense graph | Oversized graph request returns aggregation/truncation metadata, not browser overload |
| A29 | P1 | Saved investigation | Filters/time/graph state persist and reload |
| A30 | P1 | Alert lifecycle | Alert open→acknowledged→resolved works and is traceable |
| A31 | P1 | Queue controls | Pause/resume queue is audited and takes effect |
| A32 | P1 | Account controls | Pause/resume account is audited and enforced |
| A33 | P1 | Variant compare | Synthesis shows >=2 variants and side-by-side prediction metadata |
| A34 | P1 | Load smoke | 10k objects + 100k events remain interactively queryable |
| A35 | P2 | 1M-event test | Event ledger/replay remains functionally correct at 1M events |

## Required end-to-end demo

Run one deterministic fixture from discovery through fake metrics and replay. Record:
- created object IDs,
- trace ID,
- task IDs,
- composition ID,
- fake post ID,
- metric snapshot ID,
- model/audience update event.

The demo is considered valid only if the same lifecycle can be reconstructed from the event ledger after services restart.
