#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Setup Firewall for Prime AI Agent - IPTables Edition
# Блокирует весь исходящий трафик кроме разрешенных AI API
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
PRIME_NETWORK="172.28.0.0/16"
DOCKER_INTERFACE="docker0"
LOG_FILE="/var/log/prime-firewall.log"

# Список разрешенных AI API (IP адреса будут резолвиться)
declare -A ALLOWED_DOMAAINS=(
    # OpenAI
    ["api.openai.com"]="443"
    ["openai.com"]="443"
    
    # Anthropic
    ["api.anthropic.com"]="443"
    
    # DeepSeek
    ["api.deepseek.com"]="443"
    
    # Google Gemini
    ["generativelanguage.googleapis.com"]="443"
    
    # Mistral
    ["api.mistral.ai"]="443"
    
    # Cohere
    ["api.cohere.ai"]="443"
    
    # Telegram
    ["api.telegram.org"]="443"
    
    # Discord
    ["discord.com"]="443"
    
    # DNS
    ["1.1.1.1"]="53"
    ["8.8.8.8"]="53"
)

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗${NC} $1" | tee -a "$LOG_FILE"
}

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    log_error "Запустите скрипт от root (sudo)"
    exit 1
fi

# Создаем backup текущих правил
backup_rules() {
    log "Создание backup текущих iptables правил..."
    iptables-save > "/tmp/iptables-backup-$(date +%Y%m%d-%H%M%S).txt"
    log_success "Backup сохранен"
}

# Очистка всех правил
flush_rules() {
    log "Очистка всех iptables правил..."
    
    # Flush всех цепочек
    iptables -F
    iptables -X
    iptables -t nat -F
    iptables -t nat -X
    iptables -t mangle -F
    iptables -t mangle -X
    
    # Сброс политик по умолчанию
    iptables -P INPUT ACCEPT
    iptables -P FORWARD ACCEPT
    iptables -P OUTPUT ACCEPT
    
    log_success "Все правила очищены"
}

# Настройка базовых правил
setup_base_rules() {
    log "Настройка базовых правил безопасности..."
    
    # Разрешаем loopback
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -o lo -j ACCEPT
    
    # Разрешаем established connections
    iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    
    # Разрешаем SSH (не заблокируем себя)
    iptables -A INPUT -p tcp --dport 22 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
    
    log_success "Базовые правила настроены"
}

# Разрешаем DNS
setup_dns_rules() {
    log "Настройка DNS правил..."
    
    # DNS UDP
    iptables -A OUTPUT -p udp --dport 53 -d 1.1.1.1 -j ACCEPT
    iptables -A OUTPUT -p udp --dport 53 -d 8.8.8.8 -j ACCEPT
    iptables -A OUTPUT -p udp --dport 53 -d 8.8.4.4 -j ACCEPT
    
    # DNS TCP (для больших запросов)
    iptables -A OUTPUT -p tcp --dport 53 -d 1.1.1.1 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -d 8.8.8.8 -j ACCEPT
    
    log_success "DNS правила настроены"
}

# Разрешаем HTTPS к AI API
setup_ai_api_rules() {
    log "Настройка правил для AI API..."
    
    # Получаем IP адреса доменов и разрешаем
    for domain in "${!ALLOWED_DOMAAINS[@]}"; do
        port="${ALLOWED_DOMAAINS[$domain]}"
        
        # Пропускаем IP адреса (они уже IP)
        if [[ $domain =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            iptables -A OUTPUT -p tcp -d "$domain" --dport "$port" -j ACCEPT
            log "  Разрешен $domain:$port"
        else
            # Резолвим домен
            ips=$(getent hosts "$domain" | awk '{ print $1 }' 2>/dev/null || true)
            if [ -n "$ips" ]; then
                for ip in $ips; do
                    iptables -A OUTPUT -p tcp -d "$ip" --dport "$port" -j ACCEPT
                    log "  Разрешен $domain ($ip):$port"
                done
            else
                log_warn "  Не удалось резолвить $domain"
            fi
        fi
    done
    
    log_success "AI API правила настроены"
}

# Разрешаем Docker сети
setup_docker_rules() {
    log "Настройка правил для Docker..."
    
    # Разрешаем весь трафик внутри Docker сетей
    iptables -A INPUT -s "$PRIME_NETWORK" -d "$PRIME_NETWORK" -j ACCEPT
    iptables -A OUTPUT -s "$PRIME_NETWORK" -d "$PRIME_NETWORK" -j ACCEPT
    iptables -A FORWARD -s "$PRIME_NETWORK" -d "$PRIME_NETWORK" -j ACCEPT
    
    # Разрешаем Docker интерфейс
    iptables -A INPUT -i "$DOCKER_INTERFACE" -j ACCEPT
    iptables -A OUTPUT -o "$DOCKER_INTERFACE" -j ACCEPT
    iptables -A FORWARD -i "$DOCKER_INTERFACE" -j ACCEPT
    iptables -A FORWARD -o "$DOCKER_INTERFACE" -j ACCEPT
    
    # Разрешаем публичные порты
    iptables -A INPUT -p tcp --dport 80 -j ACCEPT    # HTTP
    iptables -A INPUT -p tcp --dport 443 -j ACCEPT   # HTTPS
    
    log_success "Docker правила настроены"
}

# Разрешаем NTP (time sync)
setup_ntp_rules() {
    log "Настройка NTP правил..."
    iptables -A OUTPUT -p udp --dport 123 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 123 -j ACCEPT
    log_success "NTP правила настроены"
}

# Блокировка всего исходящего
setup_egress_blocking() {
    log "Настройка блокировки исходящего трафика..."
    
    # Блокируем все остальные исходящие соединения
    iptables -A OUTPUT -p tcp --dport 80 -j LOG --log-prefix "PRIME-HTTP-BLOCKED: " --log-level 4
    iptables -A OUTPUT -p tcp --dport 80 -j DROP
    
    iptables -A OUTPUT -p tcp --dport 443 -j LOG --log-prefix "PRIME-HTTPS-BLOCKED: " --log-level 4
    iptables -A OUTPUT -p tcp --dport 443 -j DROP
    
    # Блокируем все остальные исходящие
    iptables -A OUTPUT -j LOG --log-prefix "PRIME-EGRESS-BLOCKED: " --log-level 4
    iptables -A OUTPUT -j DROP
    
    log_success "Egress блокировка настроена"
}

# Защита от атак
setup_attack_protection() {
    log "Настройка защиты от атак..."
    
    # Защита от SYN flood
    iptables -A INPUT -p tcp --syn -m limit --limit 1/second --limit-burst 3 -j ACCEPT
    iptables -A INPUT -p tcp --syn -j DROP
    
    # Защита от ping flood
    iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 1/second --limit-burst 2 -j ACCEPT
    iptables -A INPUT -p icmp --icmp-type echo-request -j DROP
    
    # Защита от UDP flood
    iptables -A INPUT -p udp -m limit --limit 10/second --limit-burst 20 -j ACCEPT
    
    # Блокировка фрагментированных пакетов
    iptables -A INPUT -f -j DROP
    
    # Блокировка NULL пакетов
    iptables -A INPUT -p tcp --tcp-flags ALL NONE -j DROP
    
    # Блокировка XMAS пакетов
    iptables -A INPUT -p tcp --tcp-flags ALL ALL -j DROP
    
    # Блокировка RST flood
    iptables -A INPUT -p tcp --tcp-flags RST RST -m limit --limit 2/second --limit-burst 2 -j ACCEPT
    iptables -A INPUT -p tcp --tcp-flags RST RST -j DROP
    
    log_success "Защита от атак настроена"
}

# Сохранение правил
save_rules() {
    log "Сохранение iptables правил..."
    
    # Для Ubuntu/Debian
    if command -v netfilter-persistent &> /dev/null; then
        netfilter-persistent save
    # Для CentOS/RHEL
    elif command -v iptables-save &> /dev/null; then
        mkdir -p /etc/iptables
        iptables-save > /etc/iptables/rules.v4
    fi
    
    log_success "Правила сохранены"
}

# Показать статус
show_status() {
    echo -e "\n${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Firewall Status${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}\n"
    
    echo -e "${BLUE}INPUT Chain:${NC}"
    iptables -L INPUT -n --line-numbers | head -20
    
    echo -e "\n${BLUE}OUTPUT Chain:${NC}"
    iptables -L OUTPUT -n --line-numbers | head -20
    
    echo -e "\n${BLUE}FORWARD Chain:${NC}"
    iptables -L FORWARD -n --line-numbers | head -10
    
    echo -e "\n${GREEN}═══════════════════════════════════════════════════════════════${NC}"
}

# Главная функция
main() {
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Prime AI Agent - Firewall Setup${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}\n"
    
    # Парсинг аргументов
    case "${1:-setup}" in
        "backup")
            backup_rules
            ;;
        "restore")
            if [ -f "$2" ]; then
                iptables-restore < "$2"
                log_success "Правила восстановлены из $2"
            else
                log_error "Укажите файл для восстановления"
                exit 1
            fi
            ;;
        "flush")
            read -p "Вы уверены что хотите удалить все правила? (yes/no): " confirm
            if [ "$confirm" == "yes" ]; then
                flush_rules
            fi
            ;;
        "status")
            show_status
            ;;
        "setup"|*)
            backup_rules
            flush_rules
            setup_base_rules
            setup_dns_rules
            setup_docker_rules
            setup_ntp_rules
            setup_ai_api_rules
            setup_attack_protection
            # setup_egress_blocking  # Раскомментировать для строгой блокировки
            save_rules
            show_status
            log_success "Firewall настроен!"
            ;;
    esac
}

main "$@"
