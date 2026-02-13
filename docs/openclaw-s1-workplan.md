# S1 Workplan for `openclaw.ai` (Gateway Protocol Foundation)

Date: 2026-02-12  
Source: `docs/openclaw-gap-analysis.md` (S1 section)

## Scope of Sprint S1

Deliver OpenClaw-like protocol foundation:
- Typed WebSocket protocol (`connect`, `req/res/event` envelopes).
- WS auth handshake with role/scope extraction.
- Idempotency for side-effecting methods.
- Internal command bus bridge (WS + REST share same execution path).
- Realtime event bus (`health`, `heartbeat`, `task`, `presence`).

## Assumptions

- Sprint length: 2 weeks.
- Team capacity: 2 backend + 1 frontend + 1 QA (partial).
- Existing REST API stays backward-compatible.

## Sprint Backlog (Jira-ready)

| ID | Task | Description | Output | Estimation | Dependency |
|---|---|---|---|---|---|
| S1-01 | WS Envelope Spec | Define protocol message schema: `connect.challenge`, `connect`, `req`, `res`, `event`, `error` | `docs/protocol/ws-v1.md` + JSON schemas | 1.5d (3 SP) | none |
| S1-02 | WS Protocol Module | Implement parser/validator/serializer for envelopes and protocol versioning | `backend/app/gateway/protocol.py` + tests | 2d (5 SP) | S1-01 |
| S1-03 | WS Auth Handshake | Add auth in `connect` phase (JWT validation, role/scope extraction, session bind) | `backend/app/gateway/auth_ws.py` + integration tests | 2d (5 SP) | S1-02 |
| S1-04 | WS Connection Manager | Track connections, subscriptions, keepalive, disconnect handling | `backend/app/gateway/connection_manager.py` | 1.5d (3 SP) | S1-02 |
| S1-05 | Event Bus Core | Add in-process bus and publishers for `health/heartbeat/task/presence` events | `backend/app/services/event_bus.py` + hooks in task lifecycle | 2d (5 SP) | S1-04 |
| S1-06 | Idempotency Store | Add idempotency table + middleware for side-effect WS methods | migration + `backend/app/middleware/idempotency.py` | 2d (5 SP) | S1-02 |
| S1-07 | Command Bus Bridge | Create unified command dispatcher used by WS methods and REST endpoints | `backend/app/services/command_bus.py` and adapters | 2.5d (5 SP) | S1-03 |
| S1-08 | WS API Refactor | Replace heartbeat stub in `backend/app/api/ws.py` with protocol handlers | updated `backend/app/api/ws.py` | 1.5d (3 SP) | S1-03,S1-04,S1-07 |
| S1-09 | REST Compatibility Layer | Route critical REST flows (`tasks retry/create`) through command bus | updates in `backend/app/api/tasks.py` | 1.5d (3 SP) | S1-07 |
| S1-10 | Observability for WS | Metrics/log fields: ws sessions, protocol errors, idempotency hits | metrics + structured logs | 1d (2 SP) | S1-08 |
| S1-11 | Frontend Realtime Client v1 | Add typed WS client and event handling baseline in admin UI | `frontend/src/services/ws.js` + basic event store | 1.5d (3 SP) | S1-08 |
| S1-12 | Protocol Test Suite | Unit + integration tests for handshake/envelopes/idempotency/reconnect | `backend/tests/protocol/*` | 2d (5 SP) | S1-08,S1-09 |
| S1-13 | E2E Smoke WS | Browser test: connect/auth/receive event/retry task via WS | `frontend/tests/e2e/ws-smoke.spec.js` | 1.5d (3 SP) | S1-11,S1-12 |
| S1-14 | Release Docs | Update API/protocol/runbook docs and migration notes | docs updates | 1d (2 SP) | all |

Total: **52 SP** (реалистично как 2-недельный спринт для 2+ инженерной команды).

## DB Changes (S1)

### New table: `idempotency_keys`

- `id UUID PK`
- `key VARCHAR(128) UNIQUE NOT NULL`
- `actor_id UUID NULL`
- `method VARCHAR(128) NOT NULL`
- `request_hash VARCHAR(128) NOT NULL`
- `status ENUM(in_progress, completed, failed) NOT NULL`
- `response JSONB NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `expires_at TIMESTAMPTZ NOT NULL`

Indexes:
- `(key)`
- `(actor_id, method, created_at desc)`
- `(expires_at)`

## Deliverables by Week

### Week 1

- S1-01..S1-05 done:
  - protocol spec
  - parser/validator
  - handshake auth
  - connection manager
  - event bus core

### Week 2

- S1-06..S1-14 done:
  - idempotency + command bus
  - ws endpoint refactor
  - rest bridge
  - tests/e2e/docs

## Definition of Done (S1)

1. WS protocol supports `connect`, `req`, `res`, `event`, `error` with schema validation.
2. Authenticated WS clients receive scoped access and rejected clients get typed protocol errors.
3. Side-effecting WS methods are idempotent by key.
4. REST `tasks` paths use same internal command bus used by WS.
5. Events `health/heartbeat/task/presence` are emitted and observable.
6. Test suite:
   - protocol unit tests pass
   - handshake integration tests pass
   - idempotency tests pass
   - ws e2e smoke pass
7. Docs and runbook updated.

## Risks and Mitigations

- Risk: protocol churn during implementation  
Mitigation: freeze `ws-v1` schema before coding S1-03+.

- Risk: regressions in existing REST behavior  
Mitigation: route via command bus behind compatibility adapter + regression tests.

- Risk: race conditions in idempotency  
Mitigation: DB unique key + transaction-level lock + replay tests.

## Next Step After Approval

Start with S1-01/S1-02 and create initial implementation PR slices:
1. `PR-1`: protocol schemas + parser + tests.
2. `PR-2`: ws auth + connection manager.
3. `PR-3`: command bus + idempotency + ws endpoint migration.
4. `PR-4`: frontend ws client + e2e + docs.
