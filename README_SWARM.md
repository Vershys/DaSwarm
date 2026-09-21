# DaSwarm / Manu-Swarm-Test

Object-centric control plane extending **AI-Manus at `496547ce6a5f599333138342ec126a7ea8ec9646`**.
Upstream chat, agent, browser, VNC, MongoDB and Redis features remain in the repository.

## Start on Windows

Open **DaSwarm-Launcher.cmd** (or the Windows CI-built **DaSwarm.exe**). Docker Desktop must be installed and running. Click **Start / Build**. The launcher extracts the complete editable project to `%LOCALAPPDATA%\DaSwarm\project`, generates local credentials, builds the containers, and opens `http://localhost:5173/swarm`.

The first build downloads dependencies and compiles MinIO; allow roughly 10–20 minutes. **Stop Services** preserves storage. Closing the launcher does not stop workers. **Configuration** edits worker concurrency and service settings; **Project / Plugins** opens all source files. Relaunching does not overwrite your modified project.

The single launcher is an entry point to a Docker-backed system, not a claim that PostgreSQL, browsers and media workers can run without a runtime. Only the web frontend is exposed, bound to loopback. Do not expose it on a public interface with `AUTH_PROVIDER=none`.

## Start from source

```sh
cp .env.example .env
# Set API_KEY=simulation-placeholder, AUTH_PROVIDER=none for local simulated use.
docker compose up -d --build
```

Open `/swarm` for the command center; `/chat` for upstream AI-Manus. No real publishing integration is implemented or enabled. The simulated fixture uses a generated test-pattern video, clearly labeled placeholder transcript/embedding results, and deterministic fake platform metrics.

## Operate the lifecycle

1. Click **Discover test video**. Workers normalize, deduplicate, analyze, atomize, cluster and score it against separate account profiles.
2. Select the Candidate. Inspect its metadata, relationships and trace. UNKNOWN provenance remains available and enters review.
3. Click **Build storyboard**, select atoms in order, then **Render storyboard**.
4. Open Synthesis. Select the rendered Composition, preview it, and **Approve composition**.
5. **Publish simulated post**. A durable execution intent guards the fake platform action. Metrics and an AudienceGenome update follow.
6. Open **Audit & Replay**. Selecting an event switches the shared view to a read-only historical snapshot; **Go live** returns to current state.

## Modify it

- **Settings**: audited, version-checked scoring weights, retry/lease policy, queue pauses and media limits.
- **Accounts**: create/edit durable profiles; pause/resume independently of workers.
- `backend/app/swarm/domain/contracts.py`: contracts and policies.
- `backend/swarm_contracts/`: state machine, relationship and queue definitions.
- `backend/app/swarm/application/`: commands, scheduling and deterministic stage handlers.
- `backend/app/swarm/infrastructure/media.py`: vendor-neutral transcription/embedding interfaces, fixture adapter and FFmpeg renderer.
- `backend/app/swarm/infrastructure/dispatch.py`: Celery delivery and Redis Streams outbox relay.
- `frontend/src/swarm/`: Vue/Pinia command center.
- `backend/swarm_migrations/`: Alembic migrations. Never edit deployed tables by hand.

The current discovery adapter is simulated. Real web/platform discovery, real semantic models, generative media and platform publishing need explicit adapters. Configuration rejects provider names whose adapters are not installed.

## Verification and limits

See [acceptance evidence](docs/swarm/ACCEPTANCE_STATUS.md). Component tests are not substitutes for Docker, PostgreSQL, browser or Windows validation.

```sh
PYTHONPATH=backend .venv/bin/python -m pytest tests/swarm -q
cd frontend && npm run test && npm run type-check && npm run lint && npm run build
```

The full-stack acceptance runner requires the running Docker stack. It does not mark missing services as passed.

## Data and recovery

Docker named volumes persist PostgreSQL, MinIO, Redis and shared render files. Back up PostgreSQL with `pg_dump` and MinIO/media volumes together. Avoid `docker compose down -v` unless you intend to delete local state. Jobs are at-least-once with durable leases and fencing. Events are append-only on PostgreSQL; projections and outbox writes commit with domain changes. Broker outages leave work in the outbox.

## Upstream

[AI-Manus upstream](https://github.com/Simpleyyt/ai-manus). Original documentation and license remain intact. Additional architecture decisions are in `docs/swarm/IMPLEMENTATION_ADRS.md`.
