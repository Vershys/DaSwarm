# Implementation decisions

## ADR-013: Serialized commit-ordered event writes

All swarm mutation transactions lock the singleton configuration row on PostgreSQL. This establishes a commit-ordered event cursor and eliminates the common BIGSERIAL/reconnect race where a later sequence commits before an earlier transaction. Read queries remain concurrent. Relax this lock only after measured load justifies a separate ordering mechanism.

## ADR-014: Synchronous SQL adapter, async network transport

SQLAlchemy Core + psycopg implement the source-of-truth repository. FastAPI synchronous endpoints execute in its thread pool; WebSocket queries run through `asyncio.to_thread`. Alembic is the only schema initialization route. JSONB holds versioned domain metadata. SQLite is used only for isolated component tests and cannot satisfy PostgreSQL acceptance by itself.

## ADR-015: Deterministic local demonstration and explicit provider limits

The first adapter generates a 42-second test-pattern fixture rather than claiming to discover a real wildlife video. FFmpeg produces a genuine encoded montage. Transcript and embedding providers explicitly identify themselves as placeholders. Route scoring is a configurable reproducible heuristic. Review and publication require operator commands. The only platform adapter is simulated, including a separate committed platform-acceptance ledger for timeout/retry tests.

## ADR-016: Replay snapshots and read bounds

Each object-changing event carries its immutable object snapshot. Transactional projections serve current queries. Replay reconstructs latest snapshots at a timestamp. Results cap at 200 objects; neighborhoods cap at configured limits with truncation metadata. The initial API does not provide unbounded global replay exports.

## ADR-017: Windows single-entry packaging

A single `.cmd` embeds the complete source ZIP and PowerShell WinForms launcher. A Windows GitHub runner can produce a single `.exe` using the same payload. Docker Desktop remains a prerequisite. Extraction preserves an existing editable installation rather than silently overwriting customizations. Runtime configuration, source, database and object storage remain separately modifiable.

## ADR-018: Registry portability

The pinned upstream npm lockfile referenced a package mirror that returned invalid archives in the build environment. Only resolved URLs were switched to npmjs.org; original integrity hashes were preserved. Node 22 is used for frontend builds to satisfy the pinned tooling's engine requirements. Python dependency locking remains in uv.lock.

## ADR-019: GitHub transport and upstream pin

The connected GitHub app permits direct repository writes, but this environment has no authenticated shell Git push credentials. Source files are therefore published directly through the connector as an exact snapshot of the local pinned checkout plus implementation. The remote commit descends from the repository initialization commit; it does not claim to import upstream Git history. `UPSTREAM_PIN` records the authoritative baseline, and the local checkout retains upstream ancestry. Verification workflows have read-only repository permissions. No workflow automatically writes commits to main.
