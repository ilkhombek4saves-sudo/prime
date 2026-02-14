#!/usr/bin/env bash
# Prime Local Installer
# Запускает Prime из текущей директории (без скачивания)
# Usage: ./install.sh

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
    echo -e "${BOLD}${BLU}║${RST}        ${BOLD}PRIME LOCAL INSTALLER${RST}            ${BLU}║${RST}"
    echo -e "${BOLD}${BLU}╚════════════════════════════════════════════╝${RST}"
    echo
}

# Проверяем что мы в директории проекта
check_project() {
    if [[ ! -f "docker-compose.yml" ]]; then
        error "Не найден docker-compose.yml"
        echo "Запусти install.sh из директории проекта Prime"
        exit 1
    fi
    ok "Проект найден: $(pwd)"
}

check_docker() {
    log "Проверка Docker..."
    
    if ! command -v docker &>/dev/null; then
        error "Docker не установлен"
        echo "Установи: curl -fsSL https://get.docker.com | sh"
        exit 1
    fi
    
    if ! docker info &>/dev/null; then
        error "Docker daemon не запущен"
        exit 1
    fi
    
    if ! docker compose version &>/dev/null; then
        error "Docker Compose v2 не найден"
        exit 1
    fi
    
    ok "Docker OK"
}

setup_env() {
    if [[ -f ".env" ]]; then
        warn ".env уже существует"
        read -p "Пересоздать? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            ok "Используем существующий .env"
            return
        fi
    fi
    
    log "Создание конфигурации..."
    
    # Генерируем секреты
    SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')
    JWT=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')
    DBPASS=$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-32)
    
    # Собираем API ключи
    echo
    echo -e "${BLU}═══════════════════════════════════════════════════${RST}"
    echo -e "${BOLD}       НАСТРОЙКА API КЛЮЧЕЙ (опционально)${RST}"
    echo -e "${BLU}═══════════════════════════════════════════════════${RST}"
    echo "Нажми Enter чтобы пропустить, или введи ключ"
    echo
    
    # OpenAI
    read -p "OpenAI API Key [sk-...]: " OPENAI_KEY
    echo
    
    # Anthropic
    read -p "Anthropic API Key [sk-ant-...]: " ANTHROPIC_KEY
    echo
    
    # Telegram
    read -p "Telegram Bot Token [...]: " TELEGRAM_TOKEN
    echo
    
    # Discord
    read -p "Discord Bot Token [...]: " DISCORD_TOKEN
    echo
    
    # Дополнительные настройки
    echo -e "${BLU}═══════════════════════════════════════════════════${RST}"
    echo -e "${BOLD}       ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ${RST}"
    echo -e "${BLU}═══════════════════════════════════════════════════${RST}"
    
    read -p "Лимит токенов на запрос [4000]: " TOKEN_LIMIT
    TOKEN_LIMIT=${TOKEN_LIMIT:-4000}
    
    read -p "Уровень логирования [info]: " LOG_LEVEL_INPUT
    LOG_LEVEL_INPUT=${LOG_LEVEL_INPUT:-info}
    
    # Формируем .env
    cat > .env << EOF
# Prime Configuration
SECRET_KEY=$SECRET
JWT_SECRET=$JWT
DB_USER=prime
DB_PASSWORD=$DBPASS
DOMAIN=localhost
EMAIL=admin@localhost
WORKERS=4
LOG_LEVEL=$LOG_LEVEL_INPUT
METRICS_ENABLED=true
TOKEN_LIMIT=$TOKEN_LIMIT

# AI Provider API Keys
$(if [[ -n "$OPENAI_KEY" ]]; then echo "OPENAI_API_KEY=$OPENAI_KEY"; else echo "# OPENAI_API_KEY=sk-..."; fi)
$(if [[ -n "$ANTHROPIC_KEY" ]]; then echo "ANTHROPIC_API_KEY=$ANTHROPIC_KEY"; else echo "# ANTHROPIC_API_KEY=sk-ant-..."; fi)

# Messaging Channels
$(if [[ -n "$TELEGRAM_TOKEN" ]]; then echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN"; else echo "# TELEGRAM_BOT_TOKEN=..."; fi)
$(if [[ -n "$DISCORD_TOKEN" ]]; then echo "DISCORD_BOT_TOKEN=$DISCORD_TOKEN"; else echo "# DISCORD_BOT_TOKEN=..."; fi)
EOF
    
    chmod 600 .env
    ok "Создан .env с секретами"
    
    # Показываем что настроено
    echo
    echo -e "${GRN}Настроено провайдеров:${RST}"
    [[ -n "$OPENAI_KEY" ]] && echo "  ✓ OpenAI"
    [[ -n "$ANTHROPIC_KEY" ]] && echo "  ✓ Anthropic"
    [[ -n "$TELEGRAM_TOKEN" ]] && echo "  ✓ Telegram"
    [[ -n "$DISCORD_TOKEN" ]] && echo "  ✓ Discord"
    [[ -z "$OPENAI_KEY$ANTHROPIC_KEY$TELEGRAM_TOKEN$DISCORD_TOKEN" ]] && echo "  (нет, можно добавить позже в .env)"
    echo
}

create_cli() {
    BIN_DIR="${HOME}/.local/bin"
    mkdir -p "$BIN_DIR"
    
    PRIME_DIR="$(pwd)"
    
    cat > "$BIN_DIR/prime" << EOF
#!/bin/bash
# Prime CLI
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
    doctor)
        curl -s http://localhost:8000/api/doctor | python3 -m json.tool 2>/dev/null || echo "Prime is offline"
        ;;
    *)
        docker compose "\$@"
        ;;
esac
EOF
    chmod +x "$BIN_DIR/prime"
    ok "CLI установлен: $BIN_DIR/prime"
    
    # Добавляем в PATH если нужно
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> ~/.bashrc
        export PATH="$BIN_DIR:$PATH"
        ok "Добавлено в PATH"
    fi
}

start_prime() {
    log "Запуск Prime..."
    
    # ВСЕГДА останавливаем и удаляем старые контейнеры prime
    if docker ps -a 2>/dev/null | grep -q "prime-"; then
        warn "Удаляем старые контейнеры..."
        docker compose down -v --remove-orphans 2>&1 | tail -2 || true
        docker rm -f $(docker ps -aq --filter name=prime-) 2>/dev/null || true
    fi
    
    # Принудительно освобождаем порт 5432
    if ss -tlnp 2>/dev/null | grep -q ':5432 '; then
        warn "Освобождаем порт 5432..."
        # Убиваем процесс на порту 5432
        kill $(ss -tlnp 2>/dev/null | grep ':5432 ' | grep -oP 'pid=\K[0-9]+') 2>/dev/null || true
        sleep 2
    fi
    
    # Запускаем
    docker compose up -d 2>&1 | tail -3
    
    # Ждём готовности (макс 60 секунд)
    log "Ожидание запуска (до 60 сек)..."
    for i in {1..60}; do
        if curl -sf http://localhost:8000/api/healthz &>/dev/null; then
            ok "Prime запущен!"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    echo
    warn "Prime запускается долго, проверь логи:"
    echo "  prime logs"
    return 1
}

run_onboard() {
    log "Настройка администратора..."
    
    # Ждём пока API будет доступен
    for i in {1..30}; do
        if curl -sf http://localhost:8000/api/onboard/status &>/dev/null; then
            break
        fi
        sleep 1
    done
    
    # Проверяем нужен ли onboard
    local status=$(curl -sf http://localhost:8000/api/onboard/status 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('onboard_required','false'))" 2>/dev/null || echo "false")
    
    if [[ "$status" == "True" || "$status" == "true" ]]; then
        echo
        echo -e "${BLU}═══════════════════════════════════════════════════${RST}"
        echo -e "${BOLD}       СОЗДАНИЕ АДМИНИСТРАТОРА${RST}"
        echo -e "${BLU}═══════════════════════════════════════════════════${RST}"
        echo
        
        # Спрашиваем логин/пароль
        read -p "Username [admin]: " ADMIN_USER
        ADMIN_USER=${ADMIN_USER:-admin}
        
        # Генерируем случайный пароль
        AUTO_PASSWORD=$(openssl rand -base64 16 | tr -d '=+/' | cut -c1-16)
        read -p "Password [авто: $AUTO_PASSWORD]: " ADMIN_PASS
        ADMIN_PASS=${ADMIN_PASS:-$AUTO_PASSWORD}
        
        log "Создаём администратора $ADMIN_USER..."
        
        local result=$(curl -sf -X POST http://localhost:8000/api/onboard \
            -H "Content-Type: application/json" \
            -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" 2>/dev/null)
        
        if [[ -n "$result" ]]; then
            ok "Администратор создан!"
            
            # Сохраняем credentials в файл
            cat > "$(pwd)/.admin_credentials" << EOF
# Prime Admin Credentials
# Смени пароль сразу после первого входа!

Username: $ADMIN_USER
Password: $ADMIN_PASS
EOF
            chmod 600 "$(pwd)/.admin_credentials"
            
            echo
            echo -e "${YLW}╔════════════════════════════════════════════╗${RST}"
            echo -e "${YLW}║${RST}         ${BOLD}ADMIN CREDENTIALS${RST}                ${YLW}║${RST}"
            echo -e "${YLW}╚════════════════════════════════════════════╝${RST}"
            echo
            echo "  Username: ${BOLD}$ADMIN_USER${RST}"
            echo "  Password: ${BOLD}$ADMIN_PASS${RST}"
            echo
            echo -e "${RED}⚠ СМЕНИ ПАРОЛЬ СРАЗУ ПОСЛЕ ПЕРВОГО ВХОДА!${RST}"
            echo
            echo "Сохранено в: $(pwd)/.admin_credentials"
        else
            error "Не удалось создать администратора"
        fi
    else
        ok "Onboard уже выполнен"
    fi
}

print_success() {
    echo
    echo -e "${BOLD}${GRN}╔════════════════════════════════════════════╗${RST}"
    echo -e "${BOLD}${GRN}║${RST}         ${GRN}✓ PRIME ГОТОВ${RST}                    ${GRN}║${RST}"
    echo -e "${BOLD}${GRN}╚════════════════════════════════════════════╝${RST}"
    echo
    echo "Команды:"
    echo "  prime status     # Проверить статус"
    echo "  prime up         # Запустить"
    echo "  prime down       # Остановить"
    echo "  prime logs       # Логи"
    echo "  prime doctor     # Диагностика"
    echo
    echo "API: http://localhost:8000/api"
    echo "Docs: http://localhost:8000/docs"
    echo
    echo "Настройка: $(pwd)/.env"
    echo
}

main() {
    banner
    check_project
    check_docker
    setup_env
    create_cli
    if start_prime; then
        run_onboard
    fi
    print_success
}

main "$@"
