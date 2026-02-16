#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Prime AI Agent - Secure Installation Script
# Полная настройка безопасного сервера с контролируемым egress
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Конфигурация
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIME_USER="${PRIME_USER:-prime}"
INSTALL_DIR="${INSTALL_DIR:-/opt/prime}"
LOG_FILE="/var/log/prime-secure-install.log"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ═══════════════════════════════════════════════════════════════════════════════
# ЛОГИРОВАНИЕ
# ═══════════════════════════════════════════════════════════════════════════════

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${BLUE}${msg}${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}✗${NC} $1" | tee -a "$LOG_FILE"
}

log_section() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"
}

# ═══════════════════════════════════════════════════════════════════════════════
# ПРОВЕРКИ
# ═══════════════════════════════════════════════════════════════════════════════

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Этот скрипт должен быть запущен от root (sudo)"
        exit 1
    fi
    log_success "Запущен от root"
}

check_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        log_error "Не удалось определить ОС"
        exit 1
    fi
    
    case $OS in
        ubuntu|debian)
            log_success "ОС: $OS $VERSION"
            ;;
        centos|rhel|fedora)
            log_success "ОС: $OS $VERSION"
            ;;
        *)
            log_warn "Непроверенная ОС: $OS. Продолжаем на свой риск..."
            ;;
    esac
}

check_requirements() {
    log_section "Проверка требований"
    
    # Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен"
        log "Установите Docker: https://docs.docker.com/engine/install/"
        exit 1
    fi
    log_success "Docker установлен"
    
    # Docker Compose
    if ! docker compose version &> /dev/null && ! docker-compose --version &> /dev/null; then
        log_error "Docker Compose не установлен"
        exit 1
    fi
    log_success "Docker Compose установлен"
    
    # curl
    if ! command -v curl &> /dev/null; then
        log_error "curl не установлен"
        exit 1
    fi
    log_success "curl установлен"
    
    # iptables
    if ! command -v iptables &> /dev/null; then
        log_error "iptables не установлен"
        exit 1
    fi
    log_success "iptables установлен"
}

# ═══════════════════════════════════════════════════════════════════════════════
# УСТАНОВКА ЗАВИСИМОСТЕЙ
# ═══════════════════════════════════════════════════════════════════════════════

install_dependencies() {
    log_section "Установка зависимостей"
    
    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y \
                curl \
                wget \
                iptables \
                iptables-persistent \
                netfilter-persistent \
                ca-certificates \
                gnupg \
                lsb-release \
                ufw \
                fail2ban
            ;;
        centos|rhel|fedora)
            if command -v dnf &> /dev/null; then
                dnf install -y \
                    curl \
                    wget \
                    iptables \
                    iptables-services \
                    ca-certificates \
                    fail2ban
            else
                yum install -y \
                    curl \
                    wget \
                    iptables \
                    iptables-services \
                    ca-certificates \
                    fail2ban
            fi
            ;;
    esac
    
    log_success "Зависимости установлены"
}

# ═══════════════════════════════════════════════════════════════════════════════
# НАСТРОЙКА FIREWALL
# ═══════════════════════════════════════════════════════════════════════════════

setup_ufw() {
    log_section "Настройка UFW (Uncomplicated Firewall)"
    
    # Сбрасываем UFW
    ufw --force reset
    
    # Базовые правила
    ufw default deny incoming
    ufw default deny outgoing
    ufw default deny forward
    
    # Разрешаем loopback
    ufw allow in on lo
    ufw allow out on lo
    
    # Разрешаем SSH (чтобы не потерять доступ)
    ufw allow 22/tcp
    ufw allow out 22/tcp
    
    # Разрешаем HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow out 80/tcp
    ufw allow out 443/tcp
    
    # Разрешаем DNS
    ufw allow out 53/tcp
    ufw allow out 53/udp
    
    # Разрешаем NTP
    ufw allow out 123/udp
    
    # Разрешаем пинг
    ufw allow out icmp
    
    # Docker networks
    ufw allow in on docker0
    ufw allow out on docker0
    
    # Включаем UFW
    echo "y" | ufw enable
    
    log_success "UFW настроен"
}

setup_fail2ban() {
    log_section "Настройка Fail2Ban"
    
    # Создаем конфигурацию для SSH
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
backend = auto

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
EOF
    
    # Перезапускаем fail2ban
    systemctl restart fail2ban
    systemctl enable fail2ban
    
    log_success "Fail2Ban настроен"
}

# ═══════════════════════════════════════════════════════════════════════════════
# НАСТРОЙКА DOCKER
# ═══════════════════════════════════════════════════════════════════════════════

setup_docker_security() {
    log_section "Настройка безопасности Docker"
    
    # Создаем daemon.json с настройками безопасности
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "live-restore": true,
  "no-new-privileges": true,
  "seccomp-profile": "default",
  "userland-proxy": false,
  "iptables": false
}
EOF
    
    # Перезапускаем Docker
    systemctl restart docker
    
    log_success "Docker настроен безопасно"
}

# ═══════════════════════════════════════════════════════════════════════════════
# СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ
# ═══════════════════════════════════════════════════════════════════════════════

create_prime_user() {
    log_section "Создание пользователя Prime"
    
    if id "$PRIME_USER" &>/dev/null; then
        log_warn "Пользователь $PRIME_USER уже существует"
    else
        useradd -m -s /bin/bash -d "/home/$PRIME_USER" "$PRIME_USER"
        usermod -aG docker "$PRIME_USER"
        log_success "Пользователь $PRIME_USER создан"
    fi
    
    # Создаем директорию установки
    mkdir -p "$INSTALL_DIR"
    chown -R "$PRIME_USER:$PRIME_USER" "$INSTALL_DIR"
}

# ═══════════════════════════════════════════════════════════════════════════════
# КОПИРОВАНИЕ ФАЙЛОВ
# ═══════════════════════════════════════════════════════════════════════════════

copy_files() {
    log_section "Копирование файлов Prime"
    
    # Копируем файлы проекта
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    
    # Создаем необходимые директории
    mkdir -p "$INSTALL_DIR/backups"
    mkdir -p "$INSTALL_DIR/logs"
    mkdir -p "$INSTALL_DIR/config"
    
    # Права доступа
    chown -R "$PRIME_USER:$PRIME_USER" "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/install-secure.sh"
    chmod +x "$INSTALL_DIR/infrastructure/firewall/setup-iptables.sh"
    
    log_success "Файлы скопированы в $INSTALL_DIR"
}

# ═══════════════════════════════════════════════════════════════════════════════
# НАСТРОЙКА ОКРУЖЕНИЯ
# ═══════════════════════════════════════════════════════════════════════════════

setup_environment() {
    log_section "Настройка окружения"
    
    # Создаем .env файл если не существует
    if [ ! -f "$INSTALL_DIR/.env" ]; then
        cat > "$INSTALL_DIR/.env" << 'EOF'
# Prime AI Agent - Environment Configuration
# Безопасная конфигурация

# ═══════════════════════════════════════════════════════════════════════════════
# БЕЗОПАСНОСТЬ
# ═══════════════════════════════════════════════════════════════════════════════
SECRET_KEY=change-me-in-production-$(openssl rand -hex 32)
JWT_SECRET=change-me-in-production-$(openssl rand -hex 32)

# ═══════════════════════════════════════════════════════════════════════════════
# БАЗА ДАННЫХ
# ═══════════════════════════════════════════════════════════════════════════════
DB_USER=prime
DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
DB_NAME=prime

# ═══════════════════════════════════════════════════════════════════════════════
# API КЛЮЧИ (заполнить свои)
# ═══════════════════════════════════════════════════════════════════════════════
# OpenAI
OPENAI_API_KEY=

# Anthropic Claude
ANTHROPIC_AUTH_TOKEN=

# DeepSeek
DEEPSEEK_API_KEY=

# Google Gemini
GEMINI_API_KEY=

# Kimi/Moonshot
KIMI_API_KEY=

# Telegram Bot
TELEGRAM_BOT_TOKENS=

# ═══════════════════════════════════════════════════════════════════════════════
# НАСТРОЙКИ СЕРВЕРА
# ═══════════════════════════════════════════════════════════════════════════════
DOMAIN=localhost
EMAIL=admin@example.com
WORKERS=4

# ═══════════════════════════════════════════════════════════════════════════════
# ДОПОЛНИТЕЛЬНО
# ═══════════════════════════════════════════════════════════════════════════════
# Tailscale (опционально)
TAILSCALE_AUTH_KEY=
EOF
        
        # Генерируем случайные ключи
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" "$INSTALL_DIR/.env"
        sed -i "s/JWT_SECRET=.*/JWT_SECRET=$(openssl rand -hex 32)/" "$INSTALL_DIR/.env"
        sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)/" "$INSTALL_DIR/.env"
        
        chown "$PRIME_USER:$PRIME_USER" "$INSTALL_DIR/.env"
        chmod 600 "$INSTALL_DIR/.env"
        
        log_success "Создан .env файл"
        log_warn "ОБЯЗАТЕЛЬНО заполните API ключи в $INSTALL_DIR/.env"
    else
        log_warn ".env файл уже существует"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# СБОРКА И ЗАПУСК
# ═══════════════════════════════════════════════════════════════════════════════

build_and_start() {
    log_section "Сборка и запуск Prime"
    
    cd "$INSTALL_DIR"
    
    # Сборка образов
    log "Сборка Docker образов..."
    docker compose -f docker-compose.secure.yml build --no-cache
    
    log_success "Образы собраны"
    
    # Проверяем, нужно ли запускать
    read -p "Запустить Prime сейчас? (yes/no): " start_now
    if [ "$start_now" == "yes" ]; then
        log "Запуск Prime..."
        docker compose -f docker-compose.secure.yml up -d
        
        # Ждем запуска
        log "Ожидание запуска сервисов..."
        sleep 10
        
        # Проверяем статус
        docker compose -f docker-compose.secure.yml ps
        
        log_success "Prime запущен!"
        log "Проверьте статус: docker compose -f docker-compose.secure.yml logs -f"
    else
        log "Для запуска выполните:"
        log "  cd $INSTALL_DIR"
        log "  docker compose -f docker-compose.secure.yml up -d"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEMD SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

create_systemd_service() {
    log_section "Создание Systemd сервиса"
    
    cat > /etc/systemd/system/prime-secure.service << EOF
[Unit]
Description=Prime AI Agent (Secure Mode)
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/docker compose -f docker-compose.secure.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.secure.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable prime-secure.service
    
    log_success "Systemd сервис создан и включен"
}

# ═══════════════════════════════════════════════════════════════════════════════
# ФИНАЛЬНЫЕ ПРОВЕРКИ
# ═══════════════════════════════════════════════════════════════════════════════

final_checks() {
    log_section "Финальные проверки"
    
    # Проверка портов
    log "Проверка открытых портов..."
    ss -tlnp | grep -E ':(22|80|443|8000|5432)' || true
    
    # Проверка Docker
    log "Проверка Docker..."
    docker ps
    
    # Проверка firewall
    log "Проверка firewall..."
    ufw status verbose | head -20
    
    log_success "Установка завершена!"
}

print_summary() {
    echo -e "\n${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Установка Prime AI Agent (Secure) завершена!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}\n"
    
    echo -e "${CYAN}📁 Директория установки:${NC} $INSTALL_DIR"
    echo -e "${CYAN}👤 Пользователь:${NC} $PRIME_USER"
    echo -e "${CYAN}🌐 Доступ:${NC}"
    echo -e "   - HTTP:  http://$(hostname -I | awk '{print $1}')"
    echo -e "   - HTTPS: https://$(hostname -I | awk '{print $1}')"
    echo -e ""
    echo -e "${CYAN}📋 Полезные команды:${NC}"
    echo -e "   cd $INSTALL_DIR"
    echo -e "   docker compose -f docker-compose.secure.yml logs -f"
    echo -e "   docker compose -f docker-compose.secure.yml ps"
    echo -e "   sudo systemctl status prime-secure"
    echo -e ""
    echo -e "${CYAN}🔧 Настройка:${NC}"
    echo -e "   1. Отредактируйте API ключи: nano $INSTALL_DIR/.env"
    echo -e "   2. Перезапустите: docker compose -f docker-compose.secure.yml restart"
    echo -e ""
    echo -e "${YELLOW}⚠️  Важно:${NC}"
    echo -e "   - Заполните API ключи в .env файле"
    echo -e "   - Настройте DNS запись для вашего домена"
    echo -e "   - Регулярно обновляйте систему: apt update && apt upgrade"
    echo -e ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}\n"
}

# ═══════════════════════════════════════════════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    # Парсинг аргументов
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-firewall)
                SKIP_FIREWALL=true
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --help)
                echo "Использование: $0 [опции]"
                echo ""
                echo "Опции:"
                echo "  --skip-firewall    Пропустить настройку firewall"
                echo "  --skip-docker      Пропустить настройку Docker"
                echo "  --help             Показать эту справку"
                exit 0
                ;;
            *)
                log_error "Неизвестная опция: $1"
                exit 1
                ;;
        esac
    done
    
    # Заголовок
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║      Prime AI Agent - Secure Installation                      ║"
    echo "║      Контролируемый egress, изолированные контейнеры          ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
    
    # Выполнение шагов
    check_root
    check_os
    check_requirements
    
    install_dependencies
    
    if [ "${SKIP_FIREWALL:-false}" != true ]; then
        setup_ufw
        setup_fail2ban
    fi
    
    if [ "${SKIP_DOCKER:-false}" != true ]; then
        setup_docker_security
    fi
    
    create_prime_user
    copy_files
    setup_environment
    create_systemd_service
    
    # Спрашиваем про сборку
    read -p "Собрать и запустить Prime сейчас? (yes/no): " build_now
    if [ "$build_now" == "yes" ]; then
        build_and_start
        final_checks
    fi
    
    print_summary
}

# Запуск
main "$@"
