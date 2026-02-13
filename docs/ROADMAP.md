# Prime Roadmap to OpenClaw Parity

Date: 2026-02-13

## Scope
Deliver OpenClaw‑parity UX and runtime in phases, while keeping existing provider/plugin/task core intact.

## S1 — Telegram UX + Onboarding Reliability
Focus:
- Telegram command set (`/start`, `/help`, `/new`, `/settings`, `/status`, `/whoami`, `/pair`).
- CLI onboarding that generates `.env`, starts Docker, runs health check, seeds default org/bot/agent/provider.
- Hard failure → actionable error messages (no silent drop).

Definition of Done:
- Command behaviors match checklist in `docs/PRODUCT_FLOW.md`.
- `prime onboard` works from clean checkout in < 5 minutes.
- Health checks pass and initial message returns a streamed response.

## S2 — Routing + DM Policy Parity
Focus:
- Deterministic binding resolver across channel/account/peer.
- DM policy enforcement and mention gating in groups.
- Pairing approval and device state.

Definition of Done:
- Routing precedence is tested.
- Unauthorized senders are blocked before task creation.

## S3 — Config Lifecycle + Doctor
Focus:
- Strict schema validation on boot.
- Config apply/patch with hash.
- `prime doctor` repair and migration checks.

Definition of Done:
- Invalid config blocks startup with actionable diagnostics.
- Config changes are audited and versioned.

## S4 — Security + Locking + Node Exec
Focus:
- Trusted proxy policy and header hardening.
- Gateway lock (single‑instance).
- Node runtime approvals.
- `prime security audit`.

Definition of Done:
- Security audit catches misconfigurations.
- Node exec requires approval.

## S5 — Admin Ops Depth
Focus:
- Protocol‑aware ops UI.
- Pairing approvals and event inspector.
- Regression tests for WS protocol, routing, and security.

Definition of Done:
- Operators can manage runtime without manual DB edits.
- Full E2E path covered.
