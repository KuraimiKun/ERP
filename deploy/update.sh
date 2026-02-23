#!/usr/bin/env bash
###############################################################################
# ERP Django – Quick Update Script
#
# Use this for subsequent deploys after the initial deploy.sh has been run.
# It pulls code, installs deps, migrates, and restarts services.
#
# Usage:  sudo bash deploy/update.sh
###############################################################################

set -euo pipefail

# Fix Windows CRLF line endings
fix_crlf() { sed -i 's/\r$//' "$1" 2>/dev/null || true; }
fix_crlf "${BASH_SOURCE[0]}"

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

[[ $EUID -ne 0 ]] && err "Run as root (sudo)."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fix_crlf "${SCRIPT_DIR}/.env.production"
source "${SCRIPT_DIR}/.env.production"

APP_DIR="${APP_DIR:-/opt/erpdjango}"
APP_USER="${APP_USER:-erp}"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "═══════════════════════════════════════════════"
echo "  ERP Django — Quick Update"
echo "═══════════════════════════════════════════════"
echo ""

# 1. Sync code
info "Syncing application files..."
rsync -a --delete \
    --exclude='venv/' \
    --exclude='.git/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='deploy/' \
    --exclude='logs/' \
    --exclude='media/' \
    --exclude='staticfiles/' \
    --exclude='.env' \
    "${REPO_DIR}/" "${APP_DIR}/"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
ok "Files synced"

# 2. Install dependencies
info "Installing Python dependencies..."
source "${APP_DIR}/venv/bin/activate"
pip install -r "${APP_DIR}/requirements.txt" -q
pip install xhtml2pdf gunicorn -q
ok "Dependencies updated"

# 3. Migrate
info "Running migrations..."
cd "${APP_DIR}"
python manage.py migrate --noinput
ok "Migrations complete"

# 4. Migrate tenant databases
info "Migrating tenant databases..."
python manage.py migrate_tenants || true
ok "Tenant migrations complete"

# 5. Collect static
info "Collecting static files..."
python manage.py collectstatic --noinput --clear -v 0
ok "Static files collected"

# 6. Compile translations
info "Compiling translations..."
python manage.py compilemessages
ok "Translations compiled"

# 7. System check
info "Running system check..."
python manage.py check --deploy
ok "System check passed"

# 7. Restart services
info "Restarting services..."
systemctl restart erp-gunicorn
systemctl reload nginx
ok "Services restarted"

echo ""
echo -e "  ${GREEN}Update complete!${NC} Site: https://${DOMAIN}"
echo ""
