# Prime Product Flow (OpenClaw-Parity Target)

Date: 2026-02-13

## One-Paragraph Summary
Prime is a Telegram‑first, OpenClaw‑style multi‑bot platform with a unified CLI. The system provisions itself, enforces pairing/DM policy, routes messages to agent bindings, executes plugin tasks asynchronously, streams results back to Telegram, and provides a live admin panel for ops, costs, and diagnostics.

## MVP (Current)
1. Operator runs `prime onboard` (manual .env today).
2. Docker services start (db, backend, frontend).
3. Telegram gateway polls updates and routes via bindings.
4. Agent runner executes provider call (streaming supported).
5. Replies stream back in Telegram.
6. Admin CRUD pages exist (scaffold).

## Target Behavior (OpenClaw‑Like)
1. `prime onboard --prod` generates secrets, validates config, starts Docker, health‑checks.
2. Admin configures providers, plugins, bots, agents, bindings in UI.
3. User messages Telegram bot.
4. Gateway resolves binding (channel/account/peer) → DM policy → session.
5. Task created and processed asynchronously; streaming begins immediately.
6. Task results, metrics, and artifacts are persisted; errors are actionable.
7. Admin sees live status, costs, and logs; CLI provides `doctor` + `security audit`.

## UX Parity Checklist (Telegram)
- `/start`: pairing / onboarding summary
- `/help`: commands + current agent
- `/new`: reset session
- `/settings`: show agent/provider status + DM policy
- `/status`: health summary + current routing
- `/whoami`: user + pairing status
- `/pair`: device/pairing workflow

## UX Parity Checklist (CLI)
- `prime onboard` (autogen .env + docker up + health)
- `prime status`
- `prime logs`
- `prime gateway status|health|url`
- `prime auth login|status|whoami`
- `prime channels list|doctor|connect|verify`
- `prime doctor` (migrations + config + connectivity)
- `prime security audit` (hardening checks)

## Admin UX Parity Checklist
- Live sessions/tasks with streaming status
- Provider health, latency, error rate
- Config editor with schema validation + apply/patch
- Pairing approvals, device list
- Cost metrics per agent/provider

## Non‑Goals (Short Term)
- Multi‑channel beyond Telegram
- Full node execution approval workflow
- Formal verification artifacts
