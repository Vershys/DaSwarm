# Acceptance status

**All 28 P0 checks passed** in [GitHub run 35562081034](https://github.com/Vershys/DaSwarm/actions/runs/35562081034), source commit `0a4e5810fac8953e363a7f644a57c7bb4551189f`.

- Full Compose runtime started: upstream services, PostgreSQL/pgvector, Redis, MinIO, dispatcher and worker fleet.
- Live fault tests passed: Redis outage recovery, killed Celery worker recovery, and timeout after simulated platform acceptance without duplicate posts.
- Real FFmpeg rendering and MinIO storage passed; metrics, AudienceGenome updates and lifecycle reconstruction after restart passed.
- All 15 grouped acceptance tests passed on PostgreSQL.
- Real Chromium passed discovery, linked selection, replay and WebSocket gap recovery with a nonzero reconnect cursor.
- Frontend: 127 tests passed; TypeScript, lint and production build passed. Existing lint/build warnings remain.
- Windows: executable built, opened its WinForms control window, extracted its project, and generated local configuration. Docker lifecycle execution was tested on Linux; the Windows smoke test does not claim to validate Docker Desktop installation.
- Independent upstream baseline: 193 offline tests passed, two service-dependent skips, and all five behavioral evaluations passed.

[Machine-readable P0 matrix](evidence/P0_MATRIX.json) · [Recorded lifecycle IDs](evidence/ACCEPTANCE_RUN.json) · [Full trace, service logs, JUnit and browser screenshot](https://github.com/Vershys/DaSwarm/actions/runs/35562081034/artifacts/10622712456)

The gate fails unless every A01–A28 result passes. Missing evidence is BLOCKED. P1/P2 performance and advanced-workspace checks are not claimed as passed. Discovery, transcripts/embeddings and publishing retain their explicitly labeled simulation/placeholder limits.
