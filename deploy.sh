#!/usr/bin/env bash
# deploy.sh — one-command production deployment for MultiBot
# Usage: bash deploy.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${CYAN}──────────────────────────────────────────${NC}"; echo -e "${CYAN}  $*${NC}"; echo -e "${CYAN}──────────────────────────────────────────${NC}"; }

# ─── 1. Check prerequisites ────────────────────────────────────────────────────
step "Checking prerequisites"

command -v docker >/dev/null 2>&1 \
  || error "Docker not found. Install: https://docs.docker.com/engine/install/"

docker compose version >/dev/null 2>&1 \
  || error "Docker Compose V2 not found. Update Docker or install docker-compose-plugin."

info "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"
info "Docker Compose $(docker compose version --short)"

# ─── 2. .env file ─────────────────────────────────────────────────────────────
step "Checking .env configuration"

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    warn ".env was missing — copied from .env.example"
    echo ""
    echo "  Please edit .env now and set the required values:"
    echo "    DOMAIN       — your domain or VPS IP (e.g. 203.0.113.10 or bot.example.com)"
    echo "    DB_PASSWORD  — strong database password"
    echo "    SECRET_KEY   — run: openssl rand -hex 32"
    echo "    JWT_SECRET   — run: openssl rand -hex 32"
    echo ""
    error "Edit .env and re-run this script."
  else
    error ".env is missing and no .env.example found."
  fi
fi

# Source .env (ignore lines starting with # and empty lines)
set -a
# shellcheck disable=SC1090
source <(grep -v '^#' .env | grep -v '^$')
set +a

# ─── 3. Validate required variables ───────────────────────────────────────────
MISSING=()
for VAR in DOMAIN DB_PASSWORD SECRET_KEY JWT_SECRET; do
  [[ -z "${!VAR:-}" ]] && MISSING+=("$VAR")
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  error "Missing required variables in .env: ${MISSING[*]}"
fi

# Warn if secrets look like placeholders
for VAR in SECRET_KEY JWT_SECRET DB_PASSWORD; do
  VALUE="${!VAR}"
  if [[ "$VALUE" == *"replace_me"* ]] || [[ "$VALUE" == *"CHANGE_ME"* ]] || [[ "$VALUE" == *"replace"* ]]; then
    error "$VAR looks like a placeholder. Generate a real value:\n  openssl rand -hex 32"
  fi
done

info "DOMAIN = ${DOMAIN}"
info "DB_PASSWORD is set"
info "SECRET_KEY is set"
info "JWT_SECRET is set"

# ─── 4. Check prime binary ────────────────────────────────────────────────────
step "Checking files"

if [[ ! -f prime ]]; then
  warn "prime binary not found — the CLI install script will be broken."
  warn "Build the prime CLI and copy it to: $REPO_DIR/prime"
else
  info "prime binary found"
fi

if [[ ! -f install.sh ]]; then
  warn "install.sh not found — /install.sh endpoint will 404"
else
  info "install.sh found"
fi

# ─── 5. Build images ──────────────────────────────────────────────────────────
step "Building production Docker images"
docker compose -f docker-compose.prod.yml build --pull

# ─── 6. Start services ────────────────────────────────────────────────────────
step "Starting services"
docker compose -f docker-compose.prod.yml up -d

# Give DB a moment if it was freshly created
sleep 3

# ─── 7. Verify health ─────────────────────────────────────────────────────────
step "Verifying deployment"

# Check all containers are running
FAILED=()
for SERVICE in db backend frontend landing caddy; do
  STATUS=$(docker compose -f docker-compose.prod.yml ps --format json "$SERVICE" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('State','?'))" 2>/dev/null || echo "unknown")
  if [[ "$STATUS" == "running" ]]; then
    info "$SERVICE — running"
  else
    warn "$SERVICE — status: $STATUS"
    FAILED+=("$SERVICE")
  fi
done

if [[ ${#FAILED[@]} -gt 0 ]]; then
  warn "Some services may not be healthy. Check logs with:"
  warn "  docker compose -f docker-compose.prod.yml logs ${FAILED[*]}"
fi

# ─── 8. Done ──────────────────────────────────────────────────────────────────
step "Deployment complete"

SCHEME="https"
# If DOMAIN looks like an IP address, TLS won't work — use http
if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SCHEME="http"
  warn "DOMAIN is an IP address — Caddy cannot get a TLS certificate for it."
  warn "Use a real domain name, or access via http for testing."
fi

echo ""
echo -e "  Landing page:    ${CYAN}${SCHEME}://${DOMAIN}${NC}"
echo -e "  Admin dashboard: ${CYAN}${SCHEME}://${DOMAIN}/dashboard${NC}"
echo -e "  API docs:        ${CYAN}${SCHEME}://${DOMAIN}/api/docs${NC}"
echo ""
echo "Useful commands:"
echo "  docker compose -f docker-compose.prod.yml logs -f          # stream all logs"
echo "  docker compose -f docker-compose.prod.yml logs -f backend  # backend logs only"
echo "  docker compose -f docker-compose.prod.yml down             # stop everything"
echo "  docker compose -f docker-compose.prod.yml pull && bash deploy.sh  # update"
