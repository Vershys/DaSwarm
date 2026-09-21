# Acceptance status

**Completion is not declared.** The handoff requires every P0 gate to pass on the complete runtime.

Local evidence:

- 15 grouped swarm component tests passed against isolated SQLite, including an actual worker-process kill/reclaim, durable restart reconstruction, timeout-after-platform-acceptance recovery, bounded graph queries, secret rejection, real FFmpeg encode/probe, and WebSocket reconnect protocol.
- Frontend: 127 tests across 26 files passed, including linked selection, historical state isolation, duplicate event handling and reconnect cursor tests.
- TypeScript check passed. ESLint: 0 errors; 28 upstream warnings. Production Vite build passed.
- Independent upstream baseline: 193 tests passed, 2 service-dependent skips; all 5 behavioral evaluations passed.
- Full Docker startup, PostgreSQL/pgvector, Redis/MinIO integration, actual-browser P0 checks and Windows launcher execution are not validated by those local results.

| Gate | Local evidence | Full gate |
|---|---|---|
| A01 | Compose definition created | Requires Docker runner |
| A02 | Alembic repeatability on test database | Requires PostgreSQL runner |
| A03–A05 | CRUD, concurrency, durability, outbox fault injection | PostgreSQL and actual Redis outage runner |
| A06–A07 | WebSocket transport and reconnect tests | Real-browser runner |
| A08–A09 | Duplicate delivery and real subprocess kill/reclaim | PostgreSQL/Celery runner |
| A10–A15 | Simulated discovery, media metadata, atoms, dedupe, clustering, routing, account separation | Full-stack and PostgreSQL runner |
| A16–A21 | FFmpeg montage, human approval, publish retry, metrics, learning | Full-stack and object-store runner |
| A22–A23 | Bounded graph and linked-store tests | PostgreSQL and browser runner |
| A24–A28 | Replay, trace, provenance routing, secret rejection, bounded dense graph | PostgreSQL/full-stack runner |

`scripts/summarize_acceptance.py` merges PostgreSQL test results, full-stack service evidence and actual-browser results into `test-evidence/P0_MATRIX.json`. Missing evidence is **BLOCKED**, not PASS. The workflow fails unless all 28 P0 gates pass.

The Windows `.cmd` launcher is packaged from the exact source tree. The `.exe` is built on a Windows runner. Neither artifact should be described as Windows-tested merely because packaging succeeds.
