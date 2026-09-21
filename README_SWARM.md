# DaSwarm / Manu-Swarm-Test

Object-centric control plane extending **AI-Manus at `496547ce6a5f599333138342ec126a7ea8ec9646`**.
Upstream chat, agent, browser, VNC, MongoDB and Redis features remain in the repository.

The operator-facing swarm is now **live-first**. Production discovery no longer injects the generated test video. Wikimedia Commons provides a credential-free live video path with real source files; the official YouTube Data API can provide live newest-video metadata when `YOUTUBE_API_KEY` is configured. The old deterministic fixture and fake publish/metric path are available only when the explicit `SWARM_TEST_SIMULATION=true` test flag is set.

## Start on Windows

Download the [Windows package](https://github.com/Vershys/DaSwarm/actions/runs/35563332256/artifacts/10622928193), extract it, and open **DaSwarm.exe**. The package also includes **DaSwarm-Launcher.cmd** as an alternative. Docker Desktop must be installed and running. Click **Start / Build**. The launcher extracts the complete editable project to `%LOCALAPPDATA%\DaSwarm\project`, generates local credentials, builds the containers, and opens `http://localhost:5173/swarm`.

The first build downloads dependencies and compiles MinIO; allow roughly 10–20 minutes. **Stop Services** preserves storage. Closing the launcher does not stop workers. **Configuration** edits worker concurrency and service settings; **Project / Plugins** opens all source files. Relaunching does not overwrite your modified project.

The single launcher is an entry point to a Docker-backed system, not a claim that PostgreSQL, browsers and media workers can run without a runtime. Only the web frontend is exposed, bound to loopback. Do not expose it on a public interface with `AUTH_PROVIDER=none`.

## Start from source

```sh
cp .env.example .env
# AUTH_PROVIDER=none is suitable only for a loopback-only local install.
# Wikimedia Commons live discovery requires no provider credential.
# Optional: add YOUTUBE_API_KEY=... for official YouTube metadata discovery.
docker compose up -d --build
```

Open `/swarm` for DaSwarm; `/chat` for upstream AI-Manus. The swarm does not fake unsupported integrations: real publishing is disabled until a live publisher is installed, and YouTube discovery remains metadata-only because the Data API is not used to download/cache YouTube audiovisual content.

## Operate the live lifecycle

1. In **Live Discovery**, choose a source, enter what to look for, choose the item budget, and click **Start Discovery**.
2. Wikimedia results with original media URLs enter the real pipeline automatically: download within policy limits → probe → fingerprint/deduplicate → structural analysis → atomize → cluster → route.
3. Select a Candidate when it reaches **Ready to build**, choose the extracted moments, and render them. FFmpeg renders from that Candidate's actual source media.
4. Preview the rendered Composition directly in DaSwarm and **Approve** or **Reject** it.
5. Approved output remains stored locally/MinIO. DaSwarm does not show a fake publish-success path; a real publishing adapter must be connected before publishing can be enabled.
6. Open **Settings** only when needed to change exploration, routing weights, media limits, retries, or human-level processing pause/resume controls.

For deterministic CI only, the acceptance environment sets `SWARM_TEST_SIMULATION=true`. That enables the generated fixture and simulated post/metrics so crash recovery, idempotency, event replay, and retry behavior can be tested without external services.

## Agent Ops live sensor

The main `/swarm` screen includes a live **Agent Ops** common operating picture. Each Celery execution process publishes an ephemeral Redis presence heartbeat once per second with a five-second TTL. The dashboard combines that presence with the durable task lease and event ledger to show:

- agent role and process identity;
- online, working, standing-by, stale and offline state;
- current task and target object;
- heartbeat age and lease time remaining;
- task runtime and retry attempt;
- queues/resources owned by the process;
- completed/retrying/dead-letter history;
- the most recent events in the active trace.

Agent presence is deliberately ephemeral so a killed process cannot remain falsely green. Durable worker/task/event history remains in PostgreSQL. Clicking an agent's target links the operator directly back to that Candidate or Composition in the normal workflow.

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

Live discovery providers are registered in `backend/app/swarm/infrastructure/providers.py`. Wikimedia Commons is installed for real media discovery. YouTube Data API discovery is installed when `YOUTUBE_API_KEY` is present and is intentionally metadata-only. Real semantic transcription/vision/embedding providers and real platform publishing still require explicit adapters; unsupported features are reported as unavailable rather than simulated.

To rebuild the single-file launcher after modifying source, commit your changes, then run `python scripts/package_launcher.py`. The packager uses committed Git bytes so Windows cannot alter Linux shell scripts.

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
