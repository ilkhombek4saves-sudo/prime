#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Prime AI Agent - Security Audit Script
# Проверка конфигурации безопасности
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

# ═══════════════════════════════════════════════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════════════════════

print_header() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
}

print_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# ═══════════════════════════════════════════════════════════════════════════════
# ПРОВЕРКИ
# ═══════════════════════════════════════════════════════════════════════════════

check_root() {
    print_header "Проверка привилегий"
    if [ "$EUID" -eq 0 ]; then
        print_warn "Скрипт запущен от root. Некоторые проверки могут не работать корректно."
    else
        print_ok "Скрипт запущен от непривилегированного пользователя"
    fi
}

check_files() {
    print_header "Проверка файлов конфигурации"
    
    # .env файл
    if [ -f ".env" ]; then
        PERMS=$(stat -c %a .env 2>/dev/null || stat -f %Lp .env)
        if [ "$PERMS" == "600" ]; then
            print_ok ".env файл имеет правильные права (600)"
        else
            print_error ".env файл имеет права $PERMS, должно быть 600"
        fi
        
        # Проверка на дефолтные ключи
        if grep -q "change-me" .env; then
            print_warn "В .env файле остались дефолтные значения SECRET_KEY/JWT_SECRET"
        fi
        
        # Проверка API ключей
        if grep -q "^OPENAI_API_KEY=$" .env 2>/dev/null || grep -q "^OPENAI_API_KEY=sk-$" .env 2>/dev/null; then
            print_warn "OPENAI_API_KEY не установлен"
        fi
    else
        print_error ".env файл не найден"
    fi
    
    # docker-compose.secure.yml
    if [ -f "docker-compose.secure.yml" ]; then
        print_ok "docker-compose.secure.yml найден"
    else
        print_error "docker-compose.secure.yml не найден"
    fi
    
    # tinyproxy whitelist
    if [ -f "infrastructure/egress/whitelist.txt" ]; then
        COUNT=$(wc -l < infrastructure/egress/whitelist.txt)
        print_ok "whitelist.txt найден ($COUNT строк)"
    else
        print_error "whitelist.txt не найден"
    fi
}

check_docker() {
    print_header "Проверка Docker"
    
    # Docker daemon
    if command -v docker &> /dev/null; then
        print_ok "Docker установлен"
        
        # Проверка версии
        VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
        print_info "Docker версия: $VERSION"
        
        # Проверка запуска
        if docker ps &> /dev/null; then
            print_ok "Docker daemon работает"
        else
            print_error "Docker daemon не доступен"
        fi
    else
        print_error "Docker не установлен"
    fi
    
    # Docker Compose
    if docker compose version &> /dev/null; then
        print_ok "Docker Compose v2 установлен"
    elif docker-compose --version &> /dev/null; then
        print_warn "Docker Compose v1 устарел"
    else
        print_error "Docker Compose не установлен"
    fi
    
    # Docker daemon.json
    if [ -f "/etc/docker/daemon.json" ]; then
        print_ok "/etc/docker/daemon.json существует"
        
        if grep -q '"no-new-privileges": true' /etc/docker/daemon.json 2>/dev/null; then
            print_ok "no-new-privileges включен в daemon.json"
        else
            print_warn "no-new-privileges не настроен в daemon.json"
        fi
    else
        print_warn "/etc/docker/daemon.json не найден"
    fi
}

check_containers() {
    print_header "Проверка контейнеров"
    
    # Проверка запущенных контейнеров
    RUNNING=$(docker ps --format "{{.Names}}" 2>/dev/null || true)
    
    if echo "$RUNNING" | grep -q "prime-"; then
        print_ok "Prime контейнеры запущены"
        echo "$RUNNING" | grep "prime-" | while read container; do
            print_info "  - $container"
        done
    else
        print_warn "Prime контейнеры не запущены"
    fi
    
    # Проверка сетей
    NETWORKS=$(docker network ls --format "{{.Name}}" 2>/dev/null || true)
    
    if echo "$NETWORKS" | grep -q "prime_"; then
        print_ok "Prime сети созданы"
    else
        print_warn "Prime сети не найдены"
    fi
}

check_firewall() {
    print_header "Проверка Firewall"
    
    # UFW
    if command -v ufw &> /dev/null; then
        UFW_STATUS=$(ufw status 2>/dev/null | head -1)
        if echo "$UFW_STATUS" | grep -q "Status: active"; then
            print_ok "UFW активен"
        else
            print_warn "UFW не активен: $UFW_STATUS"
        fi
        
        # Проверка правил
        ufw status numbered 2>/dev/null | tail -n +4 | while read line; do
            print_info "  $line"
        done
    else
        print_warn "UFW не установлен"
    fi
    
    # iptables
    if command -v iptables &> /dev/null; then
        print_ok "iptables установлен"
        
        # Проверка правил OUTPUT
        if iptables -L OUTPUT -n | grep -q "PRIME"; then
            print_ok "Prime iptables правила найдены"
        else
            print_warn "Prime iptables правила не найдены"
        fi
    else
        print_warn "iptables не установлен"
    fi
}

check_network() {
    print_header "Проверка сетевой безопасности"
    
    # Открытые порты
    print_info "Открытые порты:"
    ss -tlnp 2>/dev/null | grep LISTEN | while read line; do
        print_info "  $line"
    done
    
    # Docker proxy порт
    if ss -tlnp | grep -q ":8888"; then
        print_ok "Egress proxy (port 8888) доступен"
    else
        print_warn "Egress proxy (port 8888) не доступен"
    fi
}

check_egress() {
    print_header "Проверка Egress Control"
    
    # Проверка proxy доступности
    if curl -s --max-time 5 http://localhost:8888 &> /dev/null; then
        print_warn "Egress proxy доступен без аутентификации"
    else
        print_ok "Egress proxy требует доступ через Docker network"
    fi
    
    # Тест whitelist (если контейнеры запущены)
    if docker ps | grep -q "prime-backend"; then
        print_info "Тестирование whitelist..."
        
        # Должен работать
        if docker compose -f docker-compose.secure.yml exec -T backend \
            curl -s --max-time 10 -o /dev/null -w "%{http_code}" \
            -x http://egress-proxy:8888 https://api.openai.com 2>/dev/null | grep -q "401\|200"; then
            print_ok "api.openai.com доступен через proxy"
        else
            print_warn "api.openai.com не доступен (может быть проблема с whitelist)"
        fi
        
        # Не должен работать (тестовый домен)
        if docker compose -f docker-compose.secure.yml exec -T backend \
            curl -s --max-time 5 -x http://egress-proxy:8888 \
            https://evil-example-12345.com 2>/dev/null; then
            print_error "Незарегистрированный домен доступен (whitelist не работает!)"
        else
            print_ok "Незарегистрированные домены блокируются"
        fi
    else
        print_warn "Контейнеры не запущены, пропускаем тест egress"
    fi
}

check_fail2ban() {
    print_header "Проверка Fail2Ban"
    
    if command -v fail2ban-client &> /dev/null; then
        STATUS=$(fail2ban-client status 2>/dev/null | head -1)
        print_ok "Fail2Ban установлен"
        print_info "$STATUS"
        
        # Список jail
        JAILS=$(fail2ban-client status | grep "Jail list:" | cut -d: -f2)
        print_info "Активные jail:$JAILS"
    else
        print_warn "Fail2Ban не установлен"
    fi
}

check_permissions() {
    print_header "Проверка прав доступа"
    
    # Критические файлы
    CRITICAL_FILES=(
        ".env"
        "docker-compose.secure.yml"
        "infrastructure/egress/tinyproxy.conf"
        "infrastructure/egress/whitelist.txt"
    )
    
    for file in "${CRITICAL_FILES[@]}"; do
        if [ -f "$file" ]; then
            PERMS=$(stat -c %a "$file" 2>/dev/null || stat -f %Lp "$file")
            OWNER=$(stat -c %U "$file" 2>/dev/null || stat -f %Su "$file")
            
            if [ "$PERMS" == "600" ] || [ "$PERMS" == "644" ]; then
                print_ok "$file: $OWNER:$PERMS"
            else
                print_warn "$file: $OWNER:$PERMS (рекомендуется 600)"
            fi
        fi
    done
}

check_updates() {
    print_header "Проверка обновлений"
    
    if command -v apt &> /dev/null; then
        UPDATES=$(apt list --upgradable 2>/dev/null | wc -l)
        if [ "$UPDATES" -gt 1 ]; then
            print_warn "Доступно $((UPDATES-1)) обновлений пакетов"
        else
            print_ok "Все пакеты обновлены"
        fi
    fi
    
    # Docker images
    if command -v docker &> /dev/null; then
        print_info "Проверка Docker images..."
        docker images --format "{{.Repository}}:{{.Tag}}" | while read image; do
            print_info "  $image"
        done
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# ОТЧЕТ
# ═══════════════════════════════════════════════════════════════════════════════

print_report() {
    print_header "Итоговый Отчет"
    
    if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
        echo -e "\n${GREEN}✓ Все проверки пройдены успешно!${NC}"
    elif [ $ERRORS -eq 0 ]; then
        echo -e "\n${YELLOW}⚠ Проверка завершена с предупреждениями ($WARNINGS)${NC}"
    else
        echo -e "\n${RED}✗ Проверка завершена с ошибками ($ERRORS) и предупреждениями ($WARNINGS)${NC}"
    fi
    
    echo -e "\n${BLUE}Рекомендации:${NC}"
    
    if [ $ERRORS -gt 0 ] || [ $WARNINGS -gt 0 ]; then
        echo "  1. Исправьте ошибки перед запуском в production"
        echo "  2. Рассмотрите предупреждения для повышения безопасности"
        echo "  3. Запустите этот скрипт регулярно для аудита"
    else
        echo "  1. Продолжайте регулярно обновлять систему"
        echo "  2. Мониторьте логи на предмет подозрительной активности"
        echo "  3. Делайте резервные копии конфигурации"
    fi
    
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"
    
    return $ERRORS
}

# ═══════════════════════════════════════════════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║      Prime AI Agent - Security Audit                           ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    cd "$(dirname "$0")/../.." || exit 1
    
    check_root
    check_files
    check_docker
    check_containers
    check_firewall
    check_network
    check_egress
    check_fail2ban
    check_permissions
    check_updates
    
    print_report
}

main "$@"
