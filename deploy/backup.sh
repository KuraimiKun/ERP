#!/usr/bin/env bash
###############################################################################
# ERP Django – Database Backup Script
#
# Backs up the main database and all tenant databases.
# Meant to be run via cron or manually.
#
# Usage:  sudo bash deploy/backup.sh
###############################################################################

set -euo pipefail

# Fix Windows CRLF line endings
fix_crlf() { sed -i 's/\r$//' "$1" 2>/dev/null || true; }
fix_crlf "${BASH_SOURCE[0]}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fix_crlf "${SCRIPT_DIR}/.env.production"
source "${SCRIPT_DIR}/.env.production"

BACKUP_DIR="/opt/backups/erp"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
DB_USER="${DB_USER:-erp_user}"
DB_NAME="${DB_NAME:-erp_main}"
APP_DIR="${APP_DIR:-/opt/erpdjango}"

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }

mkdir -p "${BACKUP_DIR}"

# ── Backup main database ──────────────────────────────────────────────────
info "Backing up main database: ${DB_NAME}..."
pg_dump -U "${DB_USER}" -h localhost "${DB_NAME}" | gzip > "${BACKUP_DIR}/${DB_NAME}_${DATE}.sql.gz"
ok "Main database backed up"

# ── Backup tenant databases ────────────────────────────────────────────────
info "Discovering tenant databases..."
TENANT_DBS=$(sudo -u postgres psql -t -c "SELECT datname FROM pg_database WHERE datname LIKE 'tenant_%' AND datistemplate = false;" 2>/dev/null | tr -d ' ')

for db in $TENANT_DBS; do
    if [[ -n "$db" ]]; then
        info "Backing up tenant database: ${db}..."
        pg_dump -U postgres -h localhost "${db}" | gzip > "${BACKUP_DIR}/${db}_${DATE}.sql.gz"
        ok "${db} backed up"
    fi
done

# ── Backup media files ────────────────────────────────────────────────────
info "Backing up media files..."
if [[ -d "${APP_DIR}/media" ]]; then
    tar czf "${BACKUP_DIR}/media_${DATE}.tar.gz" -C "${APP_DIR}" media/
    ok "Media files backed up"
fi

# ── Cleanup old backups ───────────────────────────────────────────────────
info "Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -name "*.tar.gz" -mtime +${RETENTION_DAYS} -delete
ok "Old backups cleaned"

# ── Summary ───────────────────────────────────────────────────────────────
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
echo ""
echo -e "${GREEN}Backup complete!${NC}"
echo "  Location  : ${BACKUP_DIR}"
echo "  Total size: ${TOTAL_SIZE}"
echo "  Files:"
ls -lh "${BACKUP_DIR}"/*_${DATE}.* 2>/dev/null | awk '{print "    " $NF " (" $5 ")"}'
echo ""
