# Security, Reliability, and Operations Contract

## Secrets
- Never store credentials directly in Swarm Object metadata or event payloads.
- Domain objects hold `secret_ref`.
- Redact Authorization headers, cookies, API keys and access tokens from logs.
- Frontend never receives platform/LLM secret material.

## Media
- Treat downloaded media as untrusted input.
- Probe/decode in isolated worker/sandbox.
- Enforce configurable max bytes, duration and resolution.
- Normalize filenames and ignore embedded executable metadata.
- Generated previews are served through controlled object-storage URLs.

## Browser isolation
- Reuse upstream AI-Manus sandbox boundaries.
- Account session material belongs to the account/session store, not a worker.
- Workers acquire account sessions for the duration of an authorized task and release them afterward.

## Reliability
- PostgreSQL is the durable source of truth for swarm domain state.
- Redis is not authoritative for durable business state.
- WebSocket is transport, not persistence.
- Use transactional outbox for DB→queue/event handoff.
- Use optimistic concurrency via object `version`.
- All externally visible side effects use `ExecutionIntent`.

## Logging
Structured logs must include:
`timestamp`, `level`, `service`, `trace_id`, `correlation_id`, `request_id`,
`task_id`, `object_id`, `worker_id`, `event_type`.

## Backups
V1:
- PostgreSQL daily logical backup.
- MinIO persistent volume backup policy.
- MongoDB remains covered by upstream operating procedures.
- Redis persistence is useful but not the sole recovery mechanism.

## Development safety defaults
- `SWARM_PUBLISH_ENABLED=false`
- `SWARM_AUTOPUBLISH_ENABLED=false`
- simulated platform adapter is default.
- destructive commands require explicit confirmation in UI.
