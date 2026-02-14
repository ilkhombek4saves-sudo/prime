#!/bin/bash
# Prime Production Setup Script
# Installs dependencies, creates symlinks, and sets up systemd services

set -euo pipefail

PRIME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[92m'; YELLOW='\033[93m'; RED='\033[91m'; RESET='\033[0m'; BOLD='\033[1m'

ok() { echo -e "  ${GREEN}✓${RESET} $1"; }
warn() { echo -e "  ${YELLOW}!${RESET} $1"; }
err() { echo -e "  ${RED}✗${RESET} $1"; }
header() { echo -e "\n${BOLD}${1}${RESET}"; }

header "Prime Production Install"
echo -e "  ${PRIME_DIR}\n"

# ── Python packages ──────────────────────────────────────────────────────────
header "Installing Python packages..."
pip install -q fastapi uvicorn[standard] aiohttp aiosqlite duckduckgo-search httpx pydantic pyyaml 2>/dev/null && ok "Packages installed" || warn "Some packages failed"

# ── Symlinks ─────────────────────────────────────────────────────────────────
header "Creating symlinks..."
SYMLINK_TARGET="/usr/local/bin/prime"
if [ -w /usr/local/bin ] || sudo -n true 2>/dev/null; then
    SUDO=""
    [ -w /usr/local/bin ] || SUDO="sudo"
    $SUDO ln -sf "${PRIME_DIR}/prime-cli" $SYMLINK_TARGET && ok "Symlink: prime -> ${PRIME_DIR}/prime-cli"
else
    warn "Cannot create /usr/local/bin/prime (no write access). Add to PATH manually:"
    echo "  export PATH=\"${PRIME_DIR}:\$PATH\""
    echo "  alias prime='python3 ${PRIME_DIR}/prime-cli'"
fi

# ── Config dir ───────────────────────────────────────────────────────────────
header "Setting up config..."
mkdir -p "$HOME/.config/prime" "$HOME/.prime/memory" "$HOME/.prime/skills" "$HOME/.cache/prime"
ok "Directories: ~/.config/prime, ~/.prime/memory, ~/.prime/skills"

if [ ! -f "$HOME/.config/prime/.env" ]; then
    cat > "$HOME/.config/prime/.env" << 'EOF'
# Prime API Keys — edit this file with your keys
# DEEPSEEK_API_KEY=sk-...
# KIMI_API_KEY=sk-...
# GEMINI_API_KEY=AIza...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
EOF
    chmod 600 "$HOME/.config/prime/.env"
    ok "Created ~/.config/prime/.env (edit with your API keys)"
fi

# ── Initialize DB ────────────────────────────────────────────────────────────
header "Initializing database..."
cd "${PRIME_DIR}"
python3 -c "from prime.core.memory import get_db; get_db(); print('  ✓ Database initialized')" 2>/dev/null || warn "DB init will happen on first run"

# ── Systemd services ──────────────────────────────────────────────────────────
if command -v systemctl &>/dev/null && [ -d "$HOME/.config/systemd/user" ] || mkdir -p "$HOME/.config/systemd/user" 2>/dev/null; then
    header "Installing systemd services..."

    cat > "$HOME/.config/systemd/user/prime-gateway.service" << EOF
[Unit]
Description=Prime Gateway Server
After=network.target

[Service]
Type=simple
WorkingDirectory=${PRIME_DIR}
ExecStart=${PRIME_DIR}/prime-gateway-server
Restart=always
RestartSec=5
Environment=PYTHONPATH=${PRIME_DIR}

[Install]
WantedBy=default.target
EOF
    ok "Created prime-gateway.service"

    cat > "$HOME/.config/systemd/user/prime-bot.service" << EOF
[Unit]
Description=Prime Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=${PRIME_DIR}
ExecStart=${PRIME_DIR}/prime-bot
Restart=always
RestartSec=5
Environment=PYTHONPATH=${PRIME_DIR}

[Install]
WantedBy=default.target
EOF
    ok "Created prime-bot.service"

    systemctl --user daemon-reload 2>/dev/null && ok "systemd reloaded" || warn "systemd reload failed (non-critical)"

    echo ""
    echo -e "  ${BOLD}To start services:${RESET}"
    echo "    systemctl --user enable prime-gateway prime-bot"
    echo "    systemctl --user start prime-gateway prime-bot"
    echo "    systemctl --user status prime-gateway"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✅ Installation complete!${RESET}"
echo ""
echo -e "${BOLD}Quick start:${RESET}"
echo "  prime status           # Check system"
echo "  prime gateway          # Start web dashboard + API (port ${PRIME_GATEWAY_PORT:-9000})"
echo "  prime telegram         # Start Telegram bot"
echo "  prime \"hello world\"   # Quick query"
echo ""
echo -e "${BOLD}Dashboard:${RESET} http://localhost:${PRIME_GATEWAY_PORT:-9000}/"
echo -e "${BOLD}WebChat:${RESET}   http://localhost:${PRIME_GATEWAY_PORT:-9000}/chat"
echo ""
