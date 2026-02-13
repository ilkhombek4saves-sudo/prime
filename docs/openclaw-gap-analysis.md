# OpenClaw Gap Analysis for `openclaw.ai`

Date: 2026-02-12  
Baseline:
- Reference: OpenClaw docs + repo (`docs.openclaw.ai`, `github.com/openclaw/openclaw`)
- Current codebase: this repository scaffold (`backend/`, `frontend/`, `config/`)

## Goal

Define the exact gap between OpenClaw core capabilities and our current implementation, then map the work to delivery sprints for `openclaw.ai`.

## Executive Summary

Current status is a strong **service/API scaffold** (providers, plugins, tasks, admin pages), but not yet a full **OpenClaw-style Gateway runtime**.

Progress update (same date, latest local changes):
- Streaming in Telegram and WS event bus is wired (`stream.start/chunk/end`).
- Token optimization engine is integrated into Telegram path (model routing, history trim, cost metadata).
- Shell/HTTP providers are implemented and test-covered.
- Prime CLI now supports terminal auth flows (`prime auth ...`) with device-style login.
- Research engine now has cache/retry/proxy-pool rotation for robust web research.

Main missing blocks:
- Typed WebSocket control protocol (handshake, roles/scopes, pairing, idempotency).
- Multi-agent routing via bindings (`channel/accountId/peer`) with isolated agent state.
- Config lifecycle (strict schema boot checks, hot reload modes, config RPC apply/patch).
- Security operations layer (security audit, doctor/repair, gateway lock, reverse proxy hardening).
- Node capability runtime (`role: node`, caps/commands/permissions, approval flow).

## Capability Matrix

| Capability | OpenClaw baseline | Current repo status | Gap | Sprint |
|---|---|---|---|---|
| Long-lived Gateway control plane | Single long-lived gateway, WS control plane, one gateway per host | `backend/app/gateway/telegram.py` is stub; WS endpoint is minimal heartbeat (`backend/app/api/ws.py`) | Build real gateway runtime and session manager | S1 |
| Typed WS protocol (connect handshake) | `connect.challenge`, `connect`, typed req/res/event frames | Generic websocket echo/heartbeat only | Implement protocol envelopes + validator + versioning | S1 |
| Roles/scopes and node claims | `role: operator/node`, scopes, caps/commands/permissions | JWT role for REST only (`backend/app/auth/deps.py`) | Add WS authz model and node claim enforcement | S1-S4 |
| Idempotency for side effects | Idempotency keys + dedupe cache for side effects | No idempotency key/dedupe in ws/api task path | Add idempotency middleware + store | S1 |
| Device pairing/local trust | Device identity + pairing approval flow | No pairing store, no device token flow | Add pairing tables, approval workflow, TTL/pending caps | S2 |
| Multi-agent routing bindings | Deterministic bindings by channel/account/peer | No `agents`/`bindings` domain in DB | Add agent/binding schema, resolver, precedence rules | S2 |
| Per-agent isolation | Per-agent workspace, auth profiles, sessions | Shared sessions by bot/user/provider (`backend/app/persistence/models.py`) | Add per-agent workspace/auth/session partitioning | S2 |
| DM policy modes | Pairing/allowlist/open/disabled; mention gating | Bot-level `allowed_user_ids` only | Add per-channel DM/group policy layer | S2 |
| Strict config validation | Gateway refuses start on schema mismatch | YAML loader without strict schema gate (`backend/app/services/config_loader.py`) | Add strict schema validation + fail-fast boot policy | S3 |
| Config hot reload modes | `hybrid/hot/restart/off`, restart matrix | No file watcher/hot reload | Add config watcher and reload engine | S3 |
| Config RPC | `config.get/config.apply/config.patch` | Settings import endpoint only (`/api/settings/import-config`) | Add config hash, apply/patch RPC, optimistic concurrency | S3 |
| Doctor/repair tool | `openclaw doctor` migration/repair workflow | No repair CLI/tooling | Build `doctor` command and migration checks | S3 |
| Security audit command | `openclaw security audit` + fixes | No audit pass/fixer | Add automated hardening checks and remediation hints | S4 |
| Reverse proxy trust model | Trusted proxies + forwarded header hardening | No trusted proxy guardrails | Add proxy trust config and header verification | S4 |
| Gateway lock | Runtime lock / single instance guarantees | No distributed/runtime lock | Add lock table/file/port guard and conflict surface | S4 |
| Node execution approvals | Approval-required exec flows | No node runtime/invoke pipeline | Add approval queue + operator resolution | S4 |
| Formal security model support | Separate formal model repo and security claims | No formal model assets | Add lightweight TLA+/property checks for critical invariants | S4-S5 |
| Realtime control UI depth | Protocol-aware control UI tabs/workflows | Current React UI is CRUD scaffold (`frontend/src/pages/*`) | Add protocol-aware ops UI, config editor, pairing, approvals | S5 |
| End-to-end production tests | Rich runtime regression expected | Unit/integration/e2e scaffold exists | Add WS protocol tests, routing invariants, security regression suite | S5 |

## OpenClaw Convenience Features We Should Mirror

1. One-command operator lifecycle (`status`, `doctor`, `onboard`, `auth`, `logs`).
2. Protocol-first runtime: WS control plane as source of truth, REST as compatibility bridge.
3. Device-based trust and pairing for local/CLI agents.
4. Strong runtime diagnostics (`doctor`, auto-repair hints, config hash mismatch diagnostics).
5. Explicit capability boundaries for execution agents (`caps`, `allowlist`, approval flow).
6. Clear config lifecycle (strict boot validation + hot reload policy).

## Improvement Plan Beyond OpenClaw (for `openclaw.ai`)

1. Cost/perf router:
   - Extend token optimizer with latency SLO routing and per-provider health score.
2. Research reliability:
   - Add persistent cache (Redis) + domain circuit-breaker + safe browser fallback worker.
3. Resilience:
   - Move long-running tasks to worker queue (Celery/Arq) with retry DLQ.
4. Observability:
   - Add trace IDs across gateway/provider/plugin/task and per-step token economics.
5. Security:
   - Enforce per-agent secret scopes + immutable audit log for every config mutation.

## What We Already Have (Reusable Foundation)

- Provider abstraction + registry pattern (`backend/app/providers/base.py`, `backend/app/providers/registry.py`).
- Plugin abstraction with schema validation and permissions (`backend/app/plugins/base.py`).
- Task persistence model and lifecycle statuses (`backend/app/persistence/models.py`).
- REST admin surface + auth + metrics/health (`backend/app/api/*`, `/api/healthz`, `/api/metrics`).
- Frontend page skeleton for operations (`frontend/src/pages/*`).

These can remain as the **application layer**, while Gateway protocol/runtime becomes the **transport/control layer**.

## Sprint Plan

### S1: Gateway Protocol Foundation

Scope:
- Implement WS protocol server (`connect`, typed `req/res/event`, protocol version).
- Add auth token validation in WS handshake.
- Add idempotency key handling for side-effecting methods.
- Add event bus with `health`, `heartbeat`, `task`, `presence`.

DoD:
- Protocol conformance tests pass.
- Side-effect retries are deduped.
- Backward-compatible bridge for existing REST endpoints.

### S2: Multi-Agent Routing and DM Policy

Scope:
- Add DB entities: `agents`, `bindings`, `pairing_requests`, `paired_devices`.
- Deterministic binding resolver with precedence rules.
- DM policies (pairing/allowlist/open/disabled) + group mention gates.
- Per-agent workspace/auth/session partitioning.

DoD:
- Routing test matrix covers channel/account/peer precedence.
- DM unauthorized senders blocked before task creation.
- Session data isolation verified by tests.

### S3: Config Lifecycle and Operability

Scope:
- Strict typed config schema with fail-fast boot.
- Hot reload engine with `hybrid/hot/restart/off`.
- Config RPC: `get/apply/patch` with `baseHash` conflict checks.
- `doctor` repair/migration command.

DoD:
- Invalid config blocks startup and returns actionable diagnostics.
- Hot-reload behavior matches restart matrix.
- Config apply/patch audited and versioned.

### S4: Security Hardening + Node Runtime

Scope:
- Pairing approvals and device token lifecycle.
- Node role (`caps/commands/permissions`) and approval workflow.
- Security audit command and hardening checks.
- Trusted proxy / forwarded header policy.
- Gateway lock and single-instance safety.

DoD:
- Security audit identifies and classifies misconfigurations.
- Node execution requires approved flow.
- Lock prevents dual-gateway collision.

### S5: Control UI + Regression Quality

Scope:
- Config form generated from schema + raw editor.
- Pairing approvals, node approvals, protocol event inspector.
- WS + routing + security regression test suites.
- Performance and chaos tests for reconnect/retry/idempotency.

DoD:
- Operators can fully manage runtime without manual DB edits.
- E2E covers full lifecycle: connect → route → execute → approve → audit.
- Release checklist green for staging.

## Key Risks

- Scope creep if we mix provider/plugin feature work with gateway-runtime rewrite in same sprint.
- Security complexity around pairing and node execution if done without threat-model tests.
- Migration risk from current REST-first flow to WS-control-first flow without compatibility shims.

## Recommended Build Strategy

1. Keep existing provider/plugin/task modules as application core.  
2. Build Gateway protocol runtime as a new boundary layer.  
3. Add compatibility bridge: REST endpoints call the same internal command bus as WS methods.  
4. Migrate UI incrementally to protocol-driven operations.

## Sources

- OpenClaw repo: https://github.com/openclaw/openclaw
- Gateway architecture: https://docs.openclaw.ai/concepts/architecture
- Multi-agent routing: https://docs.openclaw.ai/concepts/multi-agent
- Gateway configuration: https://docs.openclaw.ai/gateway/configuration
- Gateway protocol: https://docs.openclaw.ai/gateway/protocol
- Gateway security: https://docs.openclaw.ai/gateway/security
- Doctor: https://docs.openclaw.ai/gateway/doctor
- Gateway lock: https://docs.openclaw.ai/gateway/gateway-lock
- Formal verification page: https://docs.openclaw.ai/security/formal-verification
