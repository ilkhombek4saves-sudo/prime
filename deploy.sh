#!/usr/bin/env bash
# Prime Production Deployment Script
# Usage: ./deploy.sh [domain] [email]

set -euo pipefail

RED='\033[91m'
GRN='\033[92m'
YLW='\033[93m'
BLU='\033[94m'
RST='\033[0m'
BOLD='\033[1m'

log() { echo -e "${BLU}→${RST} $1"; }
ok() { echo -e "${GRN}✓${RST} $1"; }
warn() { echo -e "${YLW}!${RST} $1"; }
error() { echo -e "${RED}✗${RST} $1" >&2; }

banner() {
    echo
    echo -e "${BOLD}${BLU}╔════════════════════════════════════════════╗${RST}"
    echo -e "${BOLD}${BLU}║${RST}    ${BOLD}PRIME PRODUCTION DEPLOYMENT${RST}          ${BLU}║${RST}"
    echo -e "${BOLD}${BLU}╚════════════════════════════════════════════╝${RST}"
    echo
}

# Default values
DOMAIN="${1:-}"
EMAIL="${2:-}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check prerequisites
check_prereqs() {
    log "Checking prerequisites..."
    
    if ! command -v docker &>/dev/null; then
        error "Docker not found"
        echo "Install: curl -fsSL https://get.docker.com | sh"
        exit 1
    fi
    
    if ! docker compose version &>/dev/null; then
        error "Docker Compose v2 not found"
        exit 1
    fi
    
    if [[ "$EUID" -ne 0 ]] && ! groups | grep -q docker; then
        error "Need docker access. Run as root or add user to docker group"
        exit 1
    fi
    
    ok "Prerequisites OK"
}

# Generate secure secrets
generate_secrets() {
    log "Generating secrets..."
    
    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            cp .env.example .env
        fi
    fi
    
    # Generate secrets if not set
    if ! grep -q "SECRET_KEY=change-me" .env 2>/dev/null; then
        ok "Secrets already configured"
        return
    fi
    
    SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')
    JWT=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')
    DB_PASS=$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-32)
    
    # Update .env
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET/" .env
    sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT/" .env
    sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=$DB_PASS/" .env
    
    if [[ -n "$DOMAIN" ]]; then
        sed -i "s/DOMAIN=.*/DOMAIN=$DOMAIN/" .env
    fi
    
    if [[ -n "$EMAIL" ]]; then
        sed -i "s/EMAIL=.*/EMAIL=$EMAIL/" .env
    fi
    
    chmod 600 .env
    ok "Secrets generated"
}

# Deploy application
deploy() {
    log "Deploying Prime..."
    
    # Pull latest images
    docker compose -f docker-compose.prod.yml pull 2>/dev/null || true
    
    # Build backend
    docker compose -f docker-compose.prod.yml build backend
    
    # Stop existing
    docker compose -f docker-compose.prod.yml down --remove-orphans
    
    # Start services
    docker compose -f docker-compose.prod.yml up -d
    
    # Wait for health
    log "Waiting for services..."
    sleep 10
    
    # Health check
    if curl -sf http://localhost/api/healthz &>/dev/null; then
        ok "Prime is healthy!"
    else
        warn "Health check pending, checking logs..."
        docker compose -f docker-compose.prod.yml logs --tail 20 backend
    fi
}

# Setup auto-updates
setup_watchtower() {
    log "Setting up auto-updates..."
    
    docker run -d \
        --name watchtower \
        --restart always \
        -v /var/run/docker.sock:/var/run/docker.sock \
        containrrr/watchtower \
        --cleanup \
        --interval 3600 \
        prime-backend-1 prime-browser-bridge-1 2>/dev/null || warn "Watchtower already running"
    
    ok "Auto-updates configured"
}

# Setup log rotation
setup_logs() {
    log "Setting up log rotation..."
    
    if [[ -d /etc/logrotate.d ]]; then
        cat > /etc/logrotate.d/prime << 'EOF'
/var/lib/docker/containers/*/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF
        ok "Log rotation configured"
    fi
}

# Print final info
print_info() {
    echo
    echo -e "${BOLD}${GRN}╔════════════════════════════════════════════╗${RST}"
    echo -e "${BOLD}${GRN}║${RST}      ${GRN}✓ DEPLOYMENT COMPLETE${RST}               ${GRN}║${RST}"
    echo -e "${BOLD}${GRN}╚════════════════════════════════════════════╝${RST}"
    echo
    echo "Access your Prime instance:"
    
    if [[ -n "$DOMAIN" ]] && [[ "$DOMAIN" != "localhost" ]]; then
        echo "  🌐 https://$DOMAIN/api"
        echo "  📖 https://$DOMAIN/docs"
    else
        echo "  🌐 http://localhost/api"
        echo "  📖 http://localhost/docs"
    fi
    
    echo
    echo "Useful commands:"
    echo "  ./deploy.sh              # Redeploy"
    echo "  docker compose -f docker-compose.prod.yml logs -f"
    echo "  docker compose -f docker-compose.prod.yml ps"
    echo
    echo "Backup database:"
    echo "  docker compose -f docker-compose.prod.yml exec db pg_dump -U prime prime > backup.sql"
    echo
}

# Main
main() {
    banner
    
    check_prereqs
    generate_secrets
    deploy
    setup_watchtower
    setup_logs
    
    print_info
}

main "$@"
