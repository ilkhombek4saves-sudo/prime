#!/usr/bin/env bash
# Prime Uninstaller - полное удаление со всеми данными
# Usage: ./uninstall.sh [--yes]

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
    echo -e "${BOLD}${RED}╔════════════════════════════════════════════╗${RST}"
    echo -e "${BOLD}${RED}║${RST}      ${BOLD}PRIME UNINSTALLER${RST}                  ${RED}║${RST}"
    echo -e "${BOLD}${RED}╚════════════════════════════════════════════╝${RST}"
    echo
}

PRIME_DIR=""

find_prime() {
    # Ищем prime в разных местах
    local dirs=(
        "$(pwd)"
        "${HOME}/prime"
        "${HOME}/.prime"
        "/opt/prime"
        "/root/prime"
    )
    
    for dir in "${dirs[@]}"; do
        if [[ -f "$dir/docker-compose.yml" ]] && [[ -d "$dir/backend" ]]; then
            PRIME_DIR="$dir"
            return 0
        fi
    done
    
    return 1
}

confirm() {
    if [[ "${1:-}" == "--yes" ]]; then
        return 0
    fi
    
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${RST}"
    echo -e "${RED}║${RST}  ${BOLD}ВНИМАНИЕ: Будут удалены ВСЕ данные Prime!${RST}                ${RED}║${RST}"
    echo -e "${RED}║${RST}                                                              ${RED}║${RST}"
    echo -e "${RED}║${RST}  Это удалит:                                                 ${RED}║${RST}"
    echo -e "${RED}║${RST}    • Все контейнеры Prime                                    ${RED}║${RST}"
    echo -e "${RED}║${RST}    • Все Docker тома (база данных, файлы)                   ${RED}║${RST}"
    echo -e "${RED}║${RST}    • Все конфигурации (.env, .admin_credentials)            ${RED}║${RST}"
    echo -e "${RED}║${RST}    • CLI команду 'prime'                                     ${RED}║${RST}"
    echo -e "${RED}║${RST}    • Логи и кэш                                              ${RED}║${RST}"
    echo -e "${RED}║${RST}                                                              ${RED}║${RST}"
    echo -e "${RED}║${RST}  ${BOLD}Данные НЕВОЗМОЖНО будет восстановить!${RST}                     ${RED}║${RST}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${RST}"
    echo
    
    read -p "Введи 'DELETE' для подтверждения удаления: " CONFIRM
    
    if [[ "$CONFIRM" != "DELETE" ]]; then
        echo "Удаление отменено."
        exit 1
    fi
}

stop_containers() {
    log "Остановка контейнеров..."
    
    if [[ -n "$PRIME_DIR" ]] && [[ -f "$PRIME_DIR/docker-compose.yml" ]]; then
        (cd "$PRIME_DIR" && docker compose down -v --remove-orphans 2>/dev/null) || true
    fi
    
    # Останавливаем все prime-контейнеры принудительно
    local containers=$(docker ps -aq --filter name=prime 2>/dev/null || true)
    if [[ -n "$containers" ]]; then
        docker stop $containers 2>/dev/null || true
        docker rm -f $containers 2>/dev/null || true
        ok "Контейнеры удалены"
    else
        ok "Контейнеров не найдено"
    fi
}

remove_volumes() {
    log "Удаление Docker томов..."
    
    # Удаляем именованные тома prime
    local volumes=$(docker volume ls -q --filter name=prime 2>/dev/null || true)
    if [[ -n "$volumes" ]]; then
        docker volume rm $volumes 2>/dev/null || true
        ok "Тома Prime удалены"
    fi
    
    # Ищем и удаляем висячие тома PostgreSQL
    local pg_volumes=$(docker volume ls -q 2>/dev/null | grep -E "pg_|postgres" || true)
    if [[ -n "$pg_volumes" ]]; then
        docker volume rm $pg_volumes 2>/dev/null || true
        ok "PostgreSQL тома удалены"
    fi
    
    # Очищаем неиспользуемые тома
    docker volume prune -f 2>/dev/null || true
    ok "Неиспользуемые тома очищены"
}

remove_networks() {
    log "Удаление сетей..."
    
    local networks=$(docker network ls -q --filter name=prime 2>/dev/null || true)
    if [[ -n "$networks" ]]; then
        docker network rm $networks 2>/dev/null || true
        ok "Сети удалены"
    fi
}

remove_images() {
    log "Удаление образов Prime..."
    
    # Удаляем образы с тегом prime
    local images=$(docker images -q prime 2>/dev/null || true)
    if [[ -n "$images" ]]; then
        docker rmi -f $images 2>/dev/null || true
        ok "Образы Prime удалены"
    fi
    
    # Удаляем dangling образы
    docker image prune -f 2>/dev/null || true
}

remove_project_files() {
    log "Удаление файлов проекта..."
    
    if [[ -n "$PRIME_DIR" ]] && [[ -d "$PRIME_DIR" ]]; then
        # Показываем что будем удалять
        echo "  Удаляется директория: $PRIME_DIR"
        rm -rf "$PRIME_DIR"
        ok "Директория проекта удалена"
    else
        warn "Директория проекта не найдена"
    fi
    
    # Удаляем другие возможные места
    local other_dirs=(
        "${HOME}/.prime"
        "/opt/prime"
    )
    
    for dir in "${other_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            rm -rf "$dir"
            ok "Удалена директория: $dir"
        fi
    done
}

remove_cli() {
    log "Удаление CLI команды..."
    
    local bin_paths=(
        "${HOME}/.local/bin/prime"
        "/usr/local/bin/prime"
        "/usr/bin/prime"
    )
    
    for path in "${bin_paths[@]}"; do
        if [[ -f "$path" ]]; then
            rm -f "$path"
            ok "Удалена команда: $path"
        fi
    done
}

remove_config_files() {
    log "Удаление конфигураций..."
    
    # Удаляем dotfiles в домашней директории
    local configs=(
        "${HOME}/.prime_config"
        "${HOME}/.prime_env"
        "${HOME}/.prime_credentials"
    )
    
    for config in "${configs[@]}"; do
        if [[ -f "$config" ]]; then
            rm -f "$config"
            ok "Удалён: $config"
        fi
    done
    
    # Удаляем из .bashrc
    if grep -q "prime" "${HOME}/.bashrc" 2>/dev/null; then
        # Удаляем строки с prime
        sed -i '/prime/d' "${HOME}/.bashrc" 2>/dev/null || true
        ok "Очищен .bashrc"
    fi
}

show_summary() {
    echo
    echo -e "${GRN}╔════════════════════════════════════════════╗${RST}"
    echo -e "${GRN}║${RST}    ${BOLD}✓ PRIME ПОЛНОСТЬЮ УДАЛЁН${RST}              ${GRN}║${RST}"
    echo -e "${GRN}╚════════════════════════════════════════════╝${RST}"
    echo
    echo "Удалено:"
    echo "  ✓ Все контейнеры"
    echo "  ✓ Все Docker тома (включая базу данных)"
    echo "  ✓ Все сети"
    echo "  ✓ Образы"
    echo "  ✓ Файлы проекта"
    echo "  ✓ Конфигурации"
    echo "  ✓ CLI команда"
    echo
    echo "Для переустановки:"
    echo "  curl -fsSL https://raw.githubusercontent.com/ilkhombek4saves-sudo/prime/main/install.sh | bash"
    echo
}

main() {
    banner
    
    # Находим директорию Prime
    if ! find_prime; then
        warn "Не найдена директория Prime"
        PRIME_DIR=""
    else
        ok "Найден Prime: $PRIME_DIR"
    fi
    
    # Подтверждение
    confirm "${1:-}"
    
    # Последовательное удаление
    stop_containers
    remove_volumes
    remove_networks
    remove_images
    remove_project_files
    remove_cli
    remove_config_files
    
    show_summary
}

main "$@"
