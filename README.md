# MultiBot Aggregator

Multi-channel bot aggregator with provider/plugin orchestration and admin SPA.

## Stack
- Backend: FastAPI, SQLAlchemy, PostgreSQL
- Frontend: React + MUI + React Router
- Infra: Docker Compose, GitHub Actions

## Quick start
1. Copy `.env.example` to `.env` and fill secrets.
2. Run:
   ```bash
   docker compose up --build
   ```
3. Backend: `http://localhost:8000/api/healthz`
4. Frontend: `http://localhost:5173`
5. DB migrations run automatically at backend startup (`alembic upgrade head`).

## Prime CLI
From project root you can run:
```bash
./prime status
./prime onboard
./prime start
./prime logs
```

Install global command (`prime`) via:
```bash
make install-cli
```

Then use:
```bash
prime status
prime onboard
prime shell
prime gateway status
prime gateway status --watch
prime gateway logs
prime channels list
prime dashboard --open
prime auth login
prime auth status
prime auth whoami
```

One-line installer (same pattern as OpenClaw):
```bash
curl -fsSL https://wgrbojeweoginrb234.duckdns.org/install.sh | bash
```

Temporary local endpoint (for now):
```bash
make installer-up
curl -fsSL http://localhost:8081/install.sh | PRIME_INSTALL_BASE_URL=http://localhost:8081 bash
```

Public HTTPS endpoint on VPS:
```bash
make installer-public-up
```

DuckDNS update (run on VPS, token in env):
```bash
export DUCKDNS_TOKEN=<your_token>
curl "https://www.duckdns.org/update?domains=wgrbojeweoginrb234&token=${DUCKDNS_TOKEN}&ip="
```

Then share a single command:
```bash
curl -fsSL https://wgrbojeweoginrb234.duckdns.org/install.sh | bash
```

For your own domain:
1. Publish `install.sh` and `prime` as static HTTPS files.
2. Make sure these URLs are reachable:
   - `https://<your-domain>/install.sh`
   - `https://<your-domain>/prime`
3. Then users install with:
   ```bash
   curl -fsSL https://<your-domain>/install.sh | bash
   ```

Installer supports overrides:
```bash
PRIME_INSTALL_BASE_URL=https://<your-domain> bash install.sh
PRIME_BIN_URL=https://<your-domain>/prime bash install.sh
```

CLI auth commands:
```bash
prime auth login              # OAuth-like device flow in terminal
prime auth login-password     # legacy username/password flow
prime auth refresh
prime auth status
prime auth whoami
prime auth logout
```

Gateway control commands (OpenClaw-like flow):
```bash
prime gateway status
prime gateway health
prime gateway status --watch
prime gateway start
prime gateway restart backend
prime gateway logs backend
prime gateway url
prime dashboard --open
```

Telegram channel diagnostics:
```bash
prime channels list
prime channels doctor
prime channels doctor --verify-api
prime channels connect --token <TELEGRAM_TOKEN> --verify
prime channels verify
```

## Environment variables
- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_SECRET`
- `ACCESS_TOKEN_TTL_MINUTES`
- `REFRESH_TOKEN_TTL_MINUTES`
- `DEVICE_AUTH_TTL_SECONDS`
- `DEVICE_AUTH_POLL_INTERVAL_SECONDS`
- `APP_PUBLIC_URL`
- `TELEGRAM_BOT_TOKENS`
- Provider keys: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `QWEN_API_KEY`, `KIMI_API_KEY`, `ZAI_API_KEY`
- Optional S3/R2: `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`

## Config files
- `config/bots.yaml`
- `config/providers.yaml`
- `config/plugins.yaml`

Provider token optimization (optional, per provider in `config/providers.yaml`):
- `token_optimization.auto_route_enabled`: route simple prompts to cheaper models.
- `token_optimization.route_by_complexity`: explicit simple/complex model mapping.
- `token_optimization.input_budget_tokens`: hard budget for system + history + user context.
- `token_optimization.max_message_tokens`: per-history-message cap before trimming.
- `token_optimization.max_output_tokens`: output cap passed to provider.
- `token_optimization.output_to_input_ratio`: dynamic output budget when no fixed cap is set.

Research engine settings (resilient web search):
- `RESEARCH_PROXY_POOL`: comma-separated HTTP(S) proxies for outbound failover.
- `RESEARCH_CACHE_TTL_SECONDS`: in-memory search cache TTL.
- `RESEARCH_HTTP_TIMEOUT_SECONDS`: page fetch timeout.
- `RESEARCH_MAX_RETRIES`: retries for search backend failures.
- `RESEARCH_PER_HOST_DELAY_MS`: polite delay between requests to same host.
- `RESEARCH_ENRICH_RESULTS`: number of search hits to fetch and summarize.

## Testing
Backend:
```bash
cd backend
python -m pytest
```

Run migrations manually:
```bash
cd backend
PYTHONPATH=. alembic -c alembic.ini upgrade head
```

Frontend e2e scaffold:
```bash
cd frontend
npm run test:e2e
```

## Monitoring
- Health: `/api/healthz`
- Metrics: `/api/metrics`

## Security notes
- Use Docker secrets or cloud secret manager in production.
- Keep shell provider allowlist strict.
- Rotate JWT secret and bot tokens.
