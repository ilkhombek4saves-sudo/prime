#!/usr/bin/env bash
# Prime Installer
# Usage: git clone ... && cd prime && ./install.sh

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
    echo -e "${BOLD}${BLU}║${RST}        ${BOLD}PRIME AI AGENT PLATFORM${RST}          ${BLU}║${RST}"
    echo -e "${BOLD}${BLU}╚════════════════════════════════════════════╝${RST}"
    echo
}

check_docker() {
    log "Checking Docker..."
    
    if ! command -v docker &>/dev/null; then
        error "Docker not found"
        echo "Install: curl -fsSL https://get.docker.com | sh"
        exit 1
    fi
    
    if ! docker info &>/dev/null; then
        error "Docker daemon not running"
        exit 1
    fi
    
    if ! docker compose version &>/dev/null; then
        error "Docker Compose v2 not found"
        exit 1
    fi
    
    ok "Docker OK"
}

setup_env() {
    if [[ ! -f .env ]]; then
        log "Creating .env..."
        
        SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')
        JWT=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')
        DBPASS=$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-32)
        
        cat > .env << EOF
# Prime Configuration
SECRET_KEY=$SECRET
JWT_SECRET=$JWT
DB_USER=prime
DB_PASSWORD=$DBPASS
DOMAIN=localhost
EMAIL=admin@localhost
WORKERS=4
EOF
        chmod 600 .env
        ok "Created .env"
    else
        ok ".env already exists"
    fi
}

create_cli() {
    BIN_DIR="${HOME}/.local/bin"
    mkdir -p "$BIN_DIR"
    
    PRIME_DIR="$(pwd)"
    
    cat > "$BIN_DIR/prime" << EOF
#!/bin/bash
export PRIME_HOME="$PRIME_DIR"
cd "$PRIME_DIR"

case "\${1:-}" in
    status)
        curl -sf http://localhost:8000/api/healthz 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Prime is offline"
        ;;
    up|start)
        docker compose up -d
        echo "✓ Prime started"
        echo "API: http://localhost:8000"
        ;;
    down|stop)
        docker compose down
        echo "✓ Prime stopped"
        ;;
    logs)
        docker compose logs -f
        ;;
    *)
        docker compose "\$@"
        ;;
esac
EOF
    chmod +x "$BIN_DIR/prime"
    ok "CLI installed to $BIN_DIR/prime"
    
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> ~/.bashrc
        export PATH="$BIN_DIR:$PATH"
        ok "Added to PATH"
    fi
}

start_prime() {
    log "Starting Prime..."
    docker compose up -d --wait 2>&1 | tail -3
    ok "Prime is running!"
}

print_success() {
    echo
    echo -e "${BOLD}${GRN}╔════════════════════════════════════════════╗${RST}"
    echo -e "${BOLD}${GRN}║${RST}         ${GRN}✓ PRIME INSTALLED${RST}                ${GRN}║${RST}"
    echo -e "${BOLD}${GRN}╚════════════════════════════════════════════╝${RST}"
    echo
    echo "Commands:"
    echo "  prime status     # Check health"
    echo "  prime up         # Start services"  
    echo "  prime down       # Stop services"
    echo "  prime logs       # View logs"
    echo
    echo "API: http://localhost:8000/api"
    echo "Docs: http://localhost:8000/docs"
    echo
}

main() {
    banner
    check_docker
    setup_env
    create_cli
    start_prime
    print_success
}

main "$@"
