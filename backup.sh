#!/bin/bash
# Prime Database Backup Script

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

# Backup
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

log "Creating backup..."

if docker compose -f docker-compose.prod.yml ps | grep -q db; then
    docker compose -f docker-compose.prod.yml exec -T db pg_dump \
        -U "${DB_USER:-prime}" \
        -d prime \
        | gzip > "$BACKUP_DIR/prime_$DATE.sql.gz"
else
    error "Database not running"
    exit 1
fi

# Cleanup old backups
find "$BACKUP_DIR" -name "prime_*.sql.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

log "Backup created: $BACKUP_DIR/prime_$DATE.sql.gz"
log "Total backups: $(ls -1 $BACKUP_DIR/*.sql.gz 2>/dev/null | wc -l)"
