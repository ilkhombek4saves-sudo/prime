#!/usr/bin/env bash
# Prime Installer - Fully Automated
# Запускает Prime полностью автоматически
# Usage: curl -fsSL .../install.sh | bash

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
step() { echo; echo -e "${BLU}═══════════════════════════════════════════════════${RST}"; echo -e "${BOLD}  $1${RST}"; echo -e "${BLU}═══════════════════════════════════════════════════${RST}"; }

banner() {
    echo
    echo -e "${BOLD}${BLU}╔════════════════════════════════════════════╗${RST}"
    echo -e "${BOLD}${BLU}║${RST}        ${BOLD}PRIME INSTALLER${RST}                  ${BLU}║${RST}"
    echo -e "${BOLD}${BLU}║${RST}     Полностью автоматическая установка    ${BLU}║${RST}"
    echo -e "${BOLD}${BLU}╚════════════════════════════════════════════╝${RST}"
    echo
}

# ═══════════════════════════════════════════════════
# 1. СИСТЕМНЫЕ ПРОВЕРКИ И УСТАНОВКА
# ═══════════════════════════════════════════════════

check_system() {
    step "1/6 Проверка системы"
    
    # Проверка архитектуры
    ARCH=$(uname -m)
    if [[ "$ARCH" != "x86_64" && "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
        error "Неподдерживаемая архитектура: $ARCH"
        exit 1
    fi
    ok "Архитектура: $ARCH"
    
    # Проверка свободного места (минимум 5GB)
    FREE_GB=$(df -BG . 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G' || echo "0")
    if [[ "$FREE_GB" -lt 5 ]]; then
        error "Недостаточно места на диске. Требуется минимум 5GB, доступно: ${FREE_GB}GB"
        exit 1
    fi
    ok "Диск: ${FREE_GB}GB доступно"
    
    # Проверка RAM (минимум 2GB)
    TOTAL_RAM=$(free -m 2>/dev/null | awk 'NR==2{print $2}' || echo "0")
    if [[ "$TOTAL_RAM" -lt 2048 ]]; then
        warn "Мало RAM: ${TOTAL_RAM}MB. Рекомендуется минимум 2GB"
    else
        ok "RAM: ${TOTAL_RAM}MB"
    fi
}

install_docker() {
    step "2/6 Установка Docker"
    
    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
        ok "Docker уже установлен"
        return 0
    fi
    
    log "Устанавливаем Docker..."
    
    # Установка Docker
    curl -fsSL https://get.docker.com | sh
    
    # Запуск сервиса
    if command -v systemctl &>/dev/null; then
        systemctl enable docker
        systemctl start docker
    fi
    
    # Добавляем пользователя в группу docker
    if [[ -n "${SUDO_USER:-}" ]]; then
        usermod -aG docker "$SUDO_USER" 2>/dev/null || true
    fi
    
    ok "Docker установлен"
}

verify_docker() {
    log "Проверка Docker daemon..."
    
    local attempts=0
    while ! docker info &>/dev/null; do
        attempts=$((attempts + 1))
        if [[ $attempts -gt 30 ]]; then
            error "Docker daemon не запустился"
            exit 1
        fi
        echo -n "."
        sleep 1
    done
    echo
    
    ok "Docker daemon работает"
}

# ═══════════════════════════════════════════════════
# 2. ЗАГРУЗКА ПРОЕКТА
# ═══════════════════════════════════════════════════

download_prime() {
    step "3/6 Загрузка Prime"
    
    # Если мы уже в директории проекта
    if [[ -f "docker-compose.yml" ]] && [[ -d "backend" ]]; then
        ok "Используем текущую директорию: $(pwd)"
        return 0
    fi
    
    # Ищем существующую установку
    if [[ -d "${HOME}/prime" ]] && [[ -f "${HOME}/prime/docker-compose.yml" ]]; then
        cd "${HOME}/prime"
        ok "Найдена существующая установка: ${HOME}/prime"
        return 0
    fi
    
    # Клонируем репозиторий
    log "Клонирование репозитория..."
    cd "${HOME}"
    
    if [[ -d "prime" ]]; then
        rm -rf prime.bak
        mv prime prime.bak
    fi
    
    git clone --depth 1 https://github.com/ilkhombek4saves-sudo/prime.git 2>/dev/null || {
        error "Не удалось клонировать репозиторий"
        exit 1
    }
    
    cd prime
    ok "Prime загружен в: $(pwd)"
}

# ═══════════════════════════════════════════════════
# 3. КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════

collect_user_input() {
    step "4/6 Настройка"
    
    # Генерируем секреты автоматически
    SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')
    JWT=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')
    DBPASS=$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-32)
    
    echo -e "${BLU}┌─────────────────────────────────────────────────┐${RST}"
    echo -e "${BLU}│${RST}  ${BOLD}ВВЕДИ API КЛЮЧИ (Enter = пропустить)${RST}        ${BLU}│${RST}"
    echo -e "${BLU}└─────────────────────────────────────────────────┘${RST}"
    echo
    
    # AI провайдеры
    read -p "OpenAI (GPT-4/3.5)      [sk-...]          : " OPENAI_KEY
    read -p "Google Gemini           [AI...]           : " GEMINI_KEY
    read -p "Mistral                 [...]             : " MISTRAL_KEY
    read -p "DeepSeek                [...]             : " DEEPSEEK_KEY
    read -p "Qwen (Alibaba)          [...]             : " QWEN_KEY
    read -p "Kimi (Moonshot)         [...]             : " KIMI_KEY
    read -p "ZAI                     [...]             : " ZAI_KEY
    
    echo
    echo -e "${BLU}┌─────────────────────────────────────────────────┐${RST}"
    echo -e "${BLU}│${RST}  ${BOLD}КАНАЛЫ СВЯЗИ${RST}                                  ${BLU}│${RST}"
    echo -e "${BLU}└─────────────────────────────────────────────────┘${RST}"
    
    read -p "Telegram Bot            [...]             : " TELEGRAM_TOKEN
    read -p "Discord Bot             [...]             : " DISCORD_TOKEN
    
    echo
    echo -e "${BLU}┌─────────────────────────────────────────────────┐${RST}"
    echo -e "${BLU}│${RST}  ${BOLD}АДМИНИСТРАТОР${RST}                                ${BLU}│${RST}"
    echo -e "${BLU}└─────────────────────────────────────────────────┘${RST}"
    
    read -p "Username                [admin]           : " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}
    
    AUTO_PASSWORD=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | cut -c1-16)
    read -p "Password                [авто: $AUTO_PASSWORD] : " ADMIN_PASS
    ADMIN_PASS=${ADMIN_PASS:-$AUTO_PASSWORD}
    
    # Создаём .env
    log "Создание конфигурации..."
    
    cat > .env << EOF
# Prime Configuration
SECRET_KEY=$SECRET
JWT_SECRET=$JWT
DB_USER=prime
DB_PASSWORD=$DBPASS
DOMAIN=localhost
EMAIL=admin@localhost
WORKERS=4
LOG_LEVEL=info
METRICS_ENABLED=true
TOKEN_LIMIT=4000

# AI Provider API Keys
$(if [[ -n "$OPENAI_KEY" ]]; then echo "OPENAI_API_KEY=$OPENAI_KEY"; else echo "# OPENAI_API_KEY=sk-..."; fi)
$(if [[ -n "$GEMINI_KEY" ]]; then echo "GEMINI_API_KEY=$GEMINI_KEY"; else echo "# GEMINI_API_KEY=AI..."; fi)
$(if [[ -n "$MISTRAL_KEY" ]]; then echo "MISTRAL_API_KEY=$MISTRAL_KEY"; else echo "# MISTRAL_API_KEY=..."; fi)
$(if [[ -n "$DEEPSEEK_KEY" ]]; then echo "DEEPSEEK_API_KEY=$DEEPSEEK_KEY"; else echo "# DEEPSEEK_API_KEY=..."; fi)
$(if [[ -n "$QWEN_KEY" ]]; then echo "QWEN_API_KEY=$QWEN_KEY"; else echo "# QWEN_API_KEY=..."; fi)
$(if [[ -n "$KIMI_KEY" ]]; then echo "KIMI_API_KEY=$KIMI_KEY"; else echo "# KIMI_API_KEY=..."; fi)
$(if [[ -n "$ZAI_KEY" ]]; then echo "ZAI_API_KEY=$ZAI_KEY"; else echo "# ZAI_API_KEY=..."; fi)

# Messaging Channels
$(if [[ -n "$TELEGRAM_TOKEN" ]]; then echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN"; else echo "# TELEGRAM_BOT_TOKEN=..."; fi)
$(if [[ -n "$DISCORD_TOKEN" ]]; then echo "DISCORD_BOT_TOKEN=$DISCORD_TOKEN"; else echo "# DISCORD_BOT_TOKEN=..."; fi)
EOF
    
    chmod 600 .env
    
    # Сохраняем admin credentials
    cat > .admin_credentials << EOF
# Prime Admin Credentials
# Смени пароль сразу после первого входа!

Username: $ADMIN_USER
Password: $ADMIN_PASS
EOF
    chmod 600 .admin_credentials
    
    ok "Конфигурация создана"
}

# ═══════════════════════════════════════════════════
# 4. ЗАПУСК
# ═══════════════════════════════════════════════════

cleanup_existing() {
    log "Очистка старых контейнеров..."
    
    # Останавливаем и удаляем
    docker compose down -v --remove-orphans 2>/dev/null || true
    docker rm -f $(docker ps -aq --filter name=prime 2>/dev/null) 2>/dev/null || true
    
    # Освобождаем порт 5432
    local pid=$(ss -tlnp 2>/dev/null | grep ':5432 ' | grep -oP 'pid=\K[0-9]+' || true)
    if [[ -n "$pid" ]]; then
        kill $pid 2>/dev/null || true
        sleep 2
    fi
    
    ok "Очищено"
}

start_prime() {
    step "5/6 Запуск Prime"
    
    cleanup_existing
    
    log "Сборка и запуск контейнеров..."
    docker compose up -d --build 2>&1 | tail -5
    
    # Ждём готовности
    log "Ожидание запуска..."
    local attempts=0
    while ! curl -sf http://localhost:8000/api/healthz &>/dev/null; do
        attempts=$((attempts + 1))
        if [[ $attempts -gt 60 ]]; then
            error "Prime не запустился за 60 секунд"
            echo "Проверь логи: docker compose logs"
            exit 1
        fi
        echo -n "."
        sleep 1
    done
    echo
    
    ok "Prime запущен!"
}

# ═══════════════════════════════════════════════════
# 5. НАСТРОЙКА (ONBOARD)
# ═══════════════════════════════════════════════════

run_onboard() {
    step "6/6 Создание администратора"
    
    # Читаем сохранённые credentials
    local ADMIN_USER=$(grep "Username:" .admin_credentials | cut -d' ' -f2)
    local ADMIN_PASS=$(grep "Password:" .admin_credentials | cut -d' ' -f2)
    
    # Ждём API
    sleep 2
    
    log "Создание администратора..."
    local result=$(curl -sf -X POST http://localhost:8000/api/onboard \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" 2>/dev/null || true)
    
    if [[ -n "$result" ]]; then
        ok "Администратор создан"
    else
        warn "Не удалось создать администратора через API"
    fi
}

# ═══════════════════════════════════════════════════
# 6. ФИНАЛ
# ═══════════════════════════════════════════════════

print_success() {
    # Читаем credentials
    local ADMIN_USER=$(grep "Username:" .admin_credentials 2>/dev/null | cut -d' ' -f2 || echo "admin")
    local ADMIN_PASS=$(grep "Password:" .admin_credentials 2>/dev/null | cut -d' ' -f2 || echo "unknown")
    
    echo
    echo -e "${GRN}╔════════════════════════════════════════════════════════════╗${RST}"
    echo -e "${GRN}║${RST}              ${BOLD}✓ PRIME УСТАНОВЛЕН${RST}                         ${GRN}║${RST}"
    echo -e "${GRN}╚════════════════════════════════════════════════════════════╝${RST}"
    echo
    echo -e "${BOLD}API:${RST} http://localhost:8000"
    echo -e "${BOLD}Docs:${RST} http://localhost:8000/docs"
    echo
    echo -e "${YLW}╔════════════════════════════════════════════════════════════╗${RST}"
    echo -e "${YLW}║${RST}  ${BOLD}ADMIN LOGIN${RST}                                              ${YLW}║${RST}"
    echo -e "${YLW}╚════════════════════════════════════════════════════════════╝${RST}"
    echo "  Username: ${BOLD}$ADMIN_USER${RST}"
    echo "  Password: ${BOLD}$ADMIN_PASS${RST}"
    echo
    echo -e "${RED}⚠ Смени пароль после первого входа!${RST}"
    echo
    echo -e "${BLU}Команды:${RST}"
    echo "  prime setup         # Запустить wizard настройки"
    echo "  prime doctor        # Проверка здоровья системы"
    echo "  prime status        # Статус Prime"
    echo "  prime logs          # Просмотр логов"
    echo "  prime agents list   # Список агентов"
    echo "  prime channels list # Список каналов"
    echo "  prime up/down       # Запуск/остановка"
    echo "  prime uninstall     # Удалить Prime"
    echo
}

create_cli() {
    local BIN_DIR="${HOME}/.local/bin"
    mkdir -p "$BIN_DIR"
    
    local PRIME_DIR="$(pwd)"
    
    # Install Python CLI
    log "Установка Prime CLI..."
    
    # Ensure Python requests library is available
    if ! python3 -c "import requests" 2>/dev/null; then
        log "Установка Python requests..."
        pip3 install requests -q 2>/dev/null || python3 -m pip install requests -q 2>/dev/null || true
    fi
    
    # Ensure cli/prime.py exists and is executable
    if [[ -f "$PRIME_DIR/cli/prime.py" ]]; then
        chmod +x "$PRIME_DIR/cli/prime.py"
    fi
    
    # Create wrapper script that calls Python CLI
    # Remove old prime if exists (to avoid permission issues)
    rm -f "$BIN_DIR/prime"
    
    # Create the wrapper script
    cat > "$BIN_DIR/prime" << 'EOF'
#!/bin/bash
export PRIME_HOME="PRIME_DIR_PLACEHOLDER"
export PYTHONPATH="PRIME_DIR_PLACEHOLDER/cli:${PYTHONPATH:-}"
exec python3 "PRIME_DIR_PLACEHOLDER/cli/prime.py" "$@"
EOF
    # Replace placeholder with actual path
    sed -i "s|PRIME_DIR_PLACEHOLDER|$PRIME_DIR|g" "$BIN_DIR/prime"
    chmod 755 "$BIN_DIR/prime"
    
    # Verify installation
    if [[ -x "$BIN_DIR/prime" ]]; then
        ok "CLI установлен: $BIN_DIR/prime"
    else
        error "Не удалось установить CLI"
    fi
    
    # Добавляем в PATH
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> ~/.bashrc
        export PATH="$BIN_DIR:$PATH"
    fi
}

# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════

main() {
    # Проверяем root для Docker установки
    if [[ $EUID -ne 0 ]]; then
        # Пробуем без root если Docker уже есть
        if ! command -v docker &>/dev/null; then
            error "Требуется root для установки Docker"
            echo "Запусти: curl -fsSL .../install.sh | sudo bash"
            exit 1
        fi
    fi
    
    banner
    
    check_system
    install_docker
    verify_docker
    download_prime
    collect_user_input
    create_cli
    start_prime
    run_onboard
    print_success
}

main "$@"
