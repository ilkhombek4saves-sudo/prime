#!/usr/bin/env bash
# Prime Lite — One-command installer
# Usage: curl -fsSL https://.../install.sh | bash

set -euo pipefail

PRIME_VERSION="0.1.0"
INSTALL_DIR="${PRIME_INSTALL_DIR:-$HOME/.prime}"
BIN_DIR="${PRIME_BIN_DIR:-$HOME/.local/bin}"
REPO_URL="https://github.com/yourusername/prime"

RED='\033[91m'
GRN='\033[92m'
YLW='\033[93m'
BLU='\033[94m'
DIM='\033[2m'
RST='\033[0m'
BOLD='\033[1m'

log() { echo -e "${BLU}→${RST} $1"; }
ok() { echo -e "${GRN}✓${RST} $1"; }
warn() { echo -e "${YLW}!${RST} $1"; }
error() { echo -e "${RED}✗${RST} $1" >&2; }

banner() {
    echo
    echo -e "${BOLD}${BLU} ██████╗ ██████╗ ██╗███╗   ███╗███████╗${RST}"
    echo -e "${BOLD}${BLU} ██╔══██╗██╔══██╗██║████╗ ████║██╔════╝${RST}"
    echo -e "${BOLD}${BLU} ██████╔╝██████╔╝██║██╔████╔██║█████╗  ${RST}"
    echo -e "${BOLD}${BLU} ██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══╝  ${RST}"
    echo -e "${BOLD}${BLU} ██║     ██║  ██║██║██║ ╚═╝ ██║███████╗${RST}"
    echo -e "${BOLD}${BLU} ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝${RST}"
    echo -e "${DIM}    Lite Mode — Personal AI Agent${RST}"
    echo
}

detect_platform() {
    local os arch
    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    arch=$(uname -m)
    
    case "$arch" in
        x86_64) arch="amd64" ;;
        aarch64|arm64) arch="arm64" ;;
        *) error "Unsupported architecture: $arch"; exit 1 ;;
    esac
    
    echo "${os}_${arch}"
}

check_deps() {
    log "Checking dependencies..."
    
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
        if [[ "$(printf '%s\n' "3.10" "$PYTHON_VERSION" | sort -V | head -n1)" == "3.10" ]]; then
            ok "Python $PYTHON_VERSION"
        else
            error "Python 3.10+ required (found $PYTHON_VERSION)"
            exit 1
        fi
    else
        error "Python 3.10+ not found"
        exit 1
    fi
    
    if command -v ollama &>/dev/null; then
        ok "Ollama found"
    else
        warn "Ollama not found. Install: curl -fsSL https://ollama.com/install.sh | bash"
    fi
}

install_prime() {
    log "Installing Prime Lite to $INSTALL_DIR..."
    
    mkdir -p "$INSTALL_DIR" "$BIN_DIR"
    
    # Check if running from repo
    if [[ -d "$(dirname "$0")/.git" ]]; then
        log "Installing from local repo..."
        cp -r "$(dirname "$0")"/* "$INSTALL_DIR/"
    else
        log "Downloading Prime Lite..."
        PLATFORM=$(detect_platform)
        # In real setup, download release
        # curl -fsSL "$REPO_URL/releases/download/v$PRIME_VERSION/prime-lite-$PLATFORM.tar.gz" | tar -xz -C "$INSTALL_DIR"
        warn "Download mode not implemented, clone repo manually"
        exit 1
    fi
    
    # Create virtual environment
    python3 -m venv "$INSTALL_DIR/.venv"
    source "$INSTALL_DIR/.venv/bin/activate"
    
    # Install dependencies
    pip install -q -e "$INSTALL_DIR/backend" 2>/dev/null || pip install -q -r "$INSTALL_DIR/backend/requirements.txt"
    
    # Create launcher script
    cat > "$BIN_DIR/prime" << 'EOF'
#!/bin/bash
export PRIME_HOME="${PRIME_HOME:-$HOME/.prime}"
export PRIME_LITE="1"
source "$PRIME_HOME/.venv/bin/activate"
exec python3 "$PRIME_HOME/lite/prime-lite.py" "$@"
EOF
    chmod +x "$BIN_DIR/prime"
    
    # Add to PATH if needed
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> ~/.bashrc
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> ~/.profile
        warn "Added $BIN_DIR to PATH. Run: export PATH=\"$BIN_DIR:\$PATH\""
    fi
    
    ok "Prime Lite installed!"
}

setup_config() {
    log "Setting up configuration..."
    
    mkdir -p "$HOME/.config/prime"
    
    if [[ ! -f "$HOME/.config/prime/config.yaml" ]]; then
        cat > "$HOME/.config/prime/config.yaml" << 'EOF'
version: 1
mode: lite

# Database: SQLite (lite mode)
database:
  type: sqlite
  path: ~/.config/prime/prime.db

# Local LLM (Ollama)
providers:
  ollama:
    type: Ollama
    api_base: http://localhost:11434/v1
    default_model: llama3.2
    models:
      llama3.2:
        max_tokens: 4096
        cost_per_1m_input: 0
        cost_per_1m_output: 0

# Bot configuration (telegram token from env)
bots:
  default:
    token_env: TELEGRAM_BOT_TOKEN
    provider: ollama
    channels: [telegram]
    active: true

# Security
dm_policy: pairing

# Server
server:
  host: 127.0.0.1
  port: 18789
EOF
        ok "Created default config"
    fi
    
    # Create .env if not exists
    if [[ ! -f "$HOME/.config/prime/.env" ]]; then
        cat > "$HOME/.config/prime/.env" << EOF
SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p)
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p)
APP_ENV=production
TELEGRAM_BOT_TOKEN=
EOF
        chmod 600 "$HOME/.config/prime/.env"
        ok "Created secure .env"
    fi
}

install_daemon() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log "Installing systemd service..."
        
        mkdir -p ~/.config/systemd/user
        
        cat > ~/.config/systemd/user/prime.service << EOF
[Unit]
Description=Prime Lite AI Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/.prime
Environment=PRIME_HOME=%h/.prime
Environment=PRIME_LITE=1
ExecStart=%h/.prime/.venv/bin/python3 %h/.prime/lite/prime-lite.py serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
        
        systemctl --user daemon-reload
        systemctl --user enable prime.service
        ok "Systemd service installed"
        log "Start with: systemctl --user start prime"
        
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        log "Installing launchd service..."
        
        mkdir -p ~/Library/LaunchAgents
        
        cat > ~/Library/LaunchAgents/com.prime.agent.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.prime.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/.prime/.venv/bin/python3</string>
        <string>$HOME/.prime/lite/prime-lite.py</string>
        <string>serve</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PRIME_HOME</key>
        <string>$HOME/.prime</string>
        <key>PRIME_LITE</key>
        <string>1</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF
        
        launchctl load ~/Library/LaunchAgents/com.prime.agent.plist
        ok "LaunchAgent installed"
    fi
}

main() {
    banner
    
    check_deps
    install_prime
    setup_config
    
    if [[ "${1:-}" == "--install-daemon" ]]; then
        install_daemon
    fi
    
    echo
    ok "Prime Lite installed successfully!"
    echo
    echo -e "${BOLD}Quick start:${RST}"
    echo "  1. Edit config:   nano ~/.config/prime/config.yaml"
    echo "  2. Set bot token: nano ~/.config/prime/.env"
    echo "  3. Start server:  prime serve"
    echo "  4. Open UI:       http://localhost:18789"
    echo
    echo -e "${BOLD}CLI commands:${RST}"
    echo "  prime status     # Check health"
    echo "  prime logs       # View logs"
    echo "  prime stop       # Stop daemon"
    echo "  prime doctor     # Run diagnostics"
    echo
}

main "$@"
