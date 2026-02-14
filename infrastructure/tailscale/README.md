# Tailscale Setup for Prime

Tailscale enables secure public HTTPS tunnels for Prime — useful for receiving
webhooks from GitHub, Stripe, Telegram, and other services.

## One-time setup

### 1. Register a Tailscale account
https://login.tailscale.com/admin

### 2. Generate an auth key
Admin console → Settings → Keys → **Generate auth key**
- Type: **Reusable** (for servers)
- Copy the key: `tskey-auth-xxxxx`

### 3. Connect Prime to Tailscale

**Option A — Docker sidecar (recommended):**
```bash
# Add to .env:
TAILSCALE_AUTH_KEY=tskey-auth-xxxxx

# Start with tailscale profile:
docker compose --profile tailscale up -d
```

**Option B — Via Prime API:**
```bash
curl -X POST http://localhost:8000/api/tailscale/connect \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"auth_key": "tskey-auth-xxxxx"}'
```

**Option C — CLI (if tailscale installed on host):**
```bash
tailscale up --authkey=tskey-auth-xxxxx
```

### 4. Enable public HTTPS funnel

```bash
# Expose Prime backend publicly:
curl -X POST http://localhost:8000/api/tailscale/funnel \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"port": 8000}'

# Or via CLI:
tailscale funnel --bg 8000
```

### 5. Check your public URL

```bash
curl http://localhost:8000/api/tailscale/status \
  -H "Authorization: Bearer $TOKEN"
# → {"funnel_url": "https://your-hostname.ts.net", ...}
```

### 6. Register a webhook using the funnel URL

```bash
curl -X POST http://localhost:8000/api/webhooks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github-deploy",
    "path": "/github",
    "message_template": "New deploy event: {{payload.action}} on {{payload.repository.full_name}}"
  }'
```

Webhook will be reachable at: `https://your-hostname.ts.net/hooks/github`

## Teardown

```bash
# Stop funnel:
curl -X DELETE http://localhost:8000/api/tailscale/funnel \
  -H "Authorization: Bearer $TOKEN"

# Stop sidecar:
docker compose --profile tailscale down
```
