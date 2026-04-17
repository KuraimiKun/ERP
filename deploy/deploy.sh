#!/usr/bin/env bash
###############################################################################
# ERP Django – One-Script VPS Deployment
#
# Tested on: Ubuntu 22.04 / 24.04 LTS
#
# Usage:
#   1. scp this entire repo to your VPS
#   2. Edit deploy/.env.production with your real values
#   3. Run:  sudo bash deploy/deploy.sh
#
# What it does:
#   - Installs system packages (Python 3.12, PostgreSQL 15, Nginx, Certbot, Docker, Redis)
#   - Creates a dedicated 'erp' system user
#   - Sets up the project under /opt/erpdjango
#   - Creates a Python virtualenv + installs deps
#   - Creates the main PostgreSQL database + user
#   - Runs Django migrations, collectstatic, createsuperuser
#   - Configures Gunicorn as a systemd service
#   - Configures Celery worker and beat scheduler as systemd services
#   - Configures Nginx with SSL (Let's Encrypt) or self-signed
#   - Configures UFW firewall
#   - Sets up automatic certificate renewal
#   - Sets up log rotation
###############################################################################

set -euo pipefail

# ─── Fix Windows CRLF line endings ─────────────────────────────────────────
fix_crlf() { sed -i 's/\r$//' "$1" 2>/dev/null || true; }
fix_crlf "${BASH_SOURCE[0]}"

# ─── Color helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Must be root ──────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && err "This script must be run as root (use sudo)."

# ─── Resolve script & project paths ────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# ─── Load config ───────────────────────────────────────────────────────────
ENV_FILE="${SCRIPT_DIR}/.env.production"
if [[ ! -f "$ENV_FILE" ]]; then
    err "Missing ${ENV_FILE}. Copy deploy/.env.production.example and fill in your values."
fi
# Strip CRLF from env file before sourcing
fix_crlf "$ENV_FILE"
source "$ENV_FILE"

# Defaults
APP_USER="${APP_USER:-erp}"
APP_DIR="${APP_DIR:-/opt/erpdjango}"
DOMAIN="${DOMAIN:?DOMAIN must be set in .env.production}"
DB_NAME="${DB_NAME:-erp_main}"
DB_USER="${DB_USER:-erp_user}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD must be set in .env.production}"
SECRET_KEY="${SECRET_KEY:?SECRET_KEY must be set in .env.production}"
ENABLE_SSL="${ENABLE_SSL:-true}"
SSL_EMAIL="${SSL_EMAIL:-}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"
TIMEZONE="${TIMEZONE:-UTC}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
PG_VERSION="${PG_VERSION:-15}"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ERP Django — VPS Deployment"
echo "═══════════════════════════════════════════════════════════════"
echo "  Domain      : ${DOMAIN}"
echo "  App Dir     : ${APP_DIR}"
echo "  DB          : ${DB_NAME} (user: ${DB_USER})"
echo "  SSL         : ${ENABLE_SSL}"
echo "  Workers     : ${GUNICORN_WORKERS}"
echo "  Celery conc : ${CELERY_CONCURRENCY}"
echo "═══════════════════════════════════════════════════════════════"
echo ""

###############################################################################
# 1. System Packages
###############################################################################
info "Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# NOTE: We deliberately do NOT run 'apt-get upgrade' here.
# A full system upgrade can silently promote postgresql-15 → 18 (or similar),
# breaking the version-pinned install below and causing gpg pipe errors on
# subsequent runs.  Security updates are handled by unattended-upgrades.

info "Installing base dependencies..."
apt-get install -yqq \
    build-essential \
    curl \
    git \
    software-properties-common \
    pkg-config \
    cmake \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    libcairo2-dev \
    libgirepository1.0-dev \
    libpango1.0-dev \
    ufw \
    logrotate \
    gettext \
    acl

# ─── Python ────────────────────────────────────────────────────────────────
info "Installing Python ${PYTHON_VERSION}..."
add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
apt-get update -qq
apt-get install -yqq \
    "python${PYTHON_VERSION}" \
    "python${PYTHON_VERSION}-venv" \
    "python${PYTHON_VERSION}-dev"
ok "Python $(python${PYTHON_VERSION} --version 2>&1)"

# ─── PostgreSQL ────────────────────────────────────────────────────────────
info "Installing PostgreSQL ${PG_VERSION}..."
if ! dpkg -l | grep -q "postgresql-${PG_VERSION}"; then
    # Add PGDG sources list only if not already present
    if [[ ! -f /etc/apt/sources.list.d/pgdg.list ]]; then
        sh -c "echo 'deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main' > /etc/apt/sources.list.d/pgdg.list"
    fi
    # Import GPG key only if not already present — gpg refuses to overwrite an
    # existing key file and the broken pipe causes curl to exit with code 23.
    if [[ ! -f /etc/apt/trusted.gpg.d/pgdg.gpg ]]; then
        curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/pgdg.gpg
    fi
    apt-get update -qq
fi
apt-get install -yqq "postgresql-${PG_VERSION}" "postgresql-contrib-${PG_VERSION}"
systemctl enable --now postgresql
ok "PostgreSQL ${PG_VERSION} installed"

# ─── Redis ─────────────────────────────────────────────────────────────────
info "Installing Redis (Celery broker/result backend)..."
apt-get install -yqq redis-server
# Bind to localhost only for security
sed -i 's/^bind .*/bind 127.0.0.1 ::1/' /etc/redis/redis.conf
# Persist to disk so beat schedule survives restarts
sed -i 's/^# save /save /' /etc/redis/redis.conf
systemctl enable --now redis-server
ok "Redis $(redis-server --version | awk '{print $3}') installed"

# ─── Nginx ─────────────────────────────────────────────────────────────────
info "Installing Nginx..."
apt-get install -yqq nginx
systemctl enable nginx
ok "Nginx installed"

# ─── Certbot ───────────────────────────────────────────────────────────────
if [[ "$ENABLE_SSL" == "true" ]]; then
    info "Installing Certbot..."
    apt-get install -yqq certbot python3-certbot-nginx
    ok "Certbot installed"
fi

# ─── Docker (for tenant DB containers) ─────────────────────────────────────
info "Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker
ok "Docker $(docker --version 2>&1 | awk '{print $3}')"

# ─── Set timezone ──────────────────────────────────────────────────────────
timedatectl set-timezone "$TIMEZONE"
ok "Timezone set to $TIMEZONE"

###############################################################################
# 2. System User
###############################################################################
info "Creating system user '${APP_USER}'..."
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home-dir "$APP_DIR" --create-home "$APP_USER"
fi
# Do NOT add APP_USER to the docker group.  Direct socket access would let a
# compromised web process escape to the host.  The app connects to the
# restricted socket proxy instead (see Section 10: Docker Socket Proxy).
ok "User '${APP_USER}' ready"

###############################################################################
# 3. Deploy Application Files
###############################################################################
info "Deploying application to ${APP_DIR}..."
# Copy everything except venv, .git, __pycache__, deploy/
rsync -a --delete \
    --exclude='venv/' \
    --exclude='.git/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='deploy/' \
    --exclude='logs/' \
    --exclude='media/' \
    --exclude='staticfiles/' \
    --exclude='run/' \
    --exclude='.env' \
    "${REPO_DIR}/" "${APP_DIR}/"

# Create directories
mkdir -p "${APP_DIR}/logs"
mkdir -p "${APP_DIR}/media"
mkdir -p "${APP_DIR}/staticfiles"
mkdir -p "${APP_DIR}/run"   # Gunicorn socket dir

ok "Application files deployed"

###############################################################################
# 4. Production .env
###############################################################################
info "Writing production .env..."
cat > "${APP_DIR}/.env" <<ENVEOF
# Auto-generated by deploy.sh — $(date -Iseconds)
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN}

DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=localhost
DB_PORT=5432

DOCKER_ENABLED=True
DOCKER_POSTGRES_IMAGE=postgres:${PG_VERSION}-alpine
DOCKER_NETWORK=erp_network

CORS_ALLOWED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}

EMAIL_BACKEND=${EMAIL_BACKEND:-django.core.mail.backends.smtp.EmailBackend}
EMAIL_HOST=${EMAIL_HOST:-smtp.gmail.com}
EMAIL_PORT=${EMAIL_PORT:-587}
EMAIL_USE_TLS=True
EMAIL_HOST_USER=${EMAIL_HOST_USER:-}
EMAIL_HOST_PASSWORD=${EMAIL_HOST_PASSWORD:-}
DEFAULT_FROM_EMAIL=${DEFAULT_FROM_EMAIL:-noreply@${DOMAIN}}

FIELD_ENCRYPTION_KEY=${FIELD_ENCRYPTION_KEY}

# ── Celery / Redis ───────────────────────────────────────────────────────────
REDIS_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

# ── Docker Socket Proxy ───────────────────────────────────────────────────────
# The app connects to the restricted proxy, NOT the raw /var/run/docker.sock.
DOCKER_HOST=tcp://127.0.0.1:2375
ENVEOF
chmod 600 "${APP_DIR}/.env"
ok ".env written"

###############################################################################
# 5. Python Virtual Environment + Dependencies
###############################################################################
info "Creating Python virtual environment..."
"python${PYTHON_VERSION}" -m venv "${APP_DIR}/venv"
source "${APP_DIR}/venv/bin/activate"

info "Installing web dependencies (requirements-prod.txt)..."
pip install --upgrade pip setuptools wheel -q
# requirements-prod.txt = requirements.txt + psycopg2 (compiled against system libpq).
# libpq-dev and build-essential were installed in Section 1.
pip install -r "${APP_DIR}/requirements-prod.txt" -q
ok "Web dependencies installed"

info "Installing ML worker dependencies (requirements-ml.txt)..."
# Installed into the same venv; never imported by Gunicorn workers because
# all erp.ai.services imports are inside Celery task function bodies (lazy).
# In Docker the web and ML images are fully separate — this shared-venv
# approach is a pragmatic simplification for single-VPS deployments.
pip install -r "${APP_DIR}/requirements-ml.txt" -q
ok "ML dependencies installed"

###############################################################################
# 6. PostgreSQL – Create Database & User
###############################################################################
info "Setting up PostgreSQL database..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}' CREATEDB;"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

# Grant privileges
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};"
ok "PostgreSQL database '${DB_NAME}' ready"

###############################################################################
# 7. Django Setup
###############################################################################
info "Running Django migrations..."
cd "${APP_DIR}"
python manage.py migrate --noinput
ok "Migrations complete"

info "Collecting static files..."
python manage.py collectstatic --noinput --clear -v 0
ok "Static files collected"

info "Compiling translations..."
python manage.py compilemessages
ok "Translations compiled"

info "Running system check..."
python manage.py check --deploy
ok "System check passed"

# Create superuser if it doesn't exist
if [[ -n "${SUPERUSER_EMAIL:-}" ]]; then
    info "Creating superuser..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='${SUPERUSER_EMAIL}').exists():
    User.objects.create_superuser(
        email='${SUPERUSER_EMAIL}',
        password='${SUPERUSER_PASSWORD:-changeme123}',
        first_name='${SUPERUSER_FIRST:-Admin}',
        last_name='${SUPERUSER_LAST:-User}',
    )
    print('Superuser created.')
else:
    print('Superuser already exists.')
" 2>/dev/null
    ok "Superuser ready"
fi

# Docker network for tenant containers
info "Creating Docker network..."
docker network inspect erp_network &>/dev/null || docker network create erp_network
ok "Docker network ready"

###############################################################################
# 8. File Ownership & Permissions
###############################################################################
info "Setting ownership and permissions..."
# Add www-data to app group so Nginx can read static/media and access socket
usermod -aG "${APP_USER}" www-data

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
chmod -R 750 "${APP_DIR}"

# Securing .env (only owner can read)
chmod 600 "${APP_DIR}/.env"

# Gunicorn socket dir — owned by erp:www-data so Nginx can connect
chown "${APP_USER}:www-data" "${APP_DIR}/run"
chmod 770 "${APP_DIR}/run"
# Media dir writeable
chmod 775 "${APP_DIR}/media"
ok "Permissions set"

###############################################################################
# 9. Gunicorn systemd Service
###############################################################################
info "Configuring Gunicorn service..."
cat > /etc/systemd/system/erp-gunicorn.service <<SVCEOF
[Unit]
Description=ERP Django Gunicorn Daemon
Requires=erp-gunicorn.socket
After=network.target postgresql.service redis-server.service docker.service

[Service]
User=${APP_USER}
Group=www-data
UMask=0007
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn erpproject.wsgi:application \\
    --workers ${GUNICORN_WORKERS} \\
    --bind unix:${APP_DIR}/run/gunicorn.sock \\
    --timeout 120 \\
    --max-requests 1000 \\
    --max-requests-jitter 100 \\
    --access-logfile ${APP_DIR}/logs/gunicorn-access.log \\
    --error-logfile ${APP_DIR}/logs/gunicorn-error.log \\
    --log-level info
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=5
KillMode=mixed

[Install]
WantedBy=multi-user.target
SVCEOF

cat > /etc/systemd/system/erp-gunicorn.socket <<SOCKEOF
[Unit]
Description=ERP Django Gunicorn Socket

[Socket]
ListenStream=${APP_DIR}/run/gunicorn.sock
SocketUser=${APP_USER}
SocketGroup=www-data
SocketMode=0660

[Install]
WantedBy=sockets.target
SOCKEOF

systemctl daemon-reload
systemctl enable --now erp-gunicorn.socket
systemctl enable erp-gunicorn.service
systemctl restart erp-gunicorn.service
ok "Gunicorn service active"

###############################################################################
# 10. Docker Socket Proxy
###############################################################################
# Runs tecnativa/docker-socket-proxy as a long-lived container.
# The app connects to tcp://127.0.0.1:2375 (this proxy) instead of the raw
# /var/run/docker.sock.  The proxy allows only the Docker API scopes the app
# actually needs; swarm, secrets, build, and everything else is blocked.
###############################################################################
info "Starting Docker Socket Proxy..."

# Pull the proxy image (root needs docker access for this step only)
docker pull tecnativa/docker-socket-proxy:latest 2>/dev/null || true

# Remove stale container if it exists
docker rm -f erp_docker_proxy 2>/dev/null || true

docker run -d \
    --name erp_docker_proxy \
    --restart unless-stopped \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    -p 127.0.0.1:2375:2375 \
    -e CONTAINERS=1 \
    -e IMAGES=1 \
    -e NETWORKS=1 \
    -e VOLUMES=1 \
    -e INFO=1 \
    -e VERSION=1 \
    -e PING=1 \
    -e POST=1 \
    -e EXEC=1 \
    tecnativa/docker-socket-proxy:latest

ok "Docker Socket Proxy running on 127.0.0.1:2375 (raw socket is NOT exposed to app)"

###############################################################################
# 11. Celery Worker & Beat Scheduler systemd Services
###############################################################################
info "Configuring Celery worker service (queues: celery, default)..."
cat > /etc/systemd/system/erp-celery-worker.service <<CELWEOF
[Unit]
Description=ERP Django Celery Worker (web queues)
After=network.target postgresql.service redis-server.service

[Service]
Type=forking
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
PIDFile=${APP_DIR}/run/celery-worker.pid
# --queues excludes 'ml' — this worker never imports sklearn/numpy/prophet,
# keeping its RSS footprint the same as the Gunicorn web workers.
ExecStart=${APP_DIR}/venv/bin/celery \\
    -A erpproject worker \\
    --queues=celery,default \\
    --concurrency=${CELERY_CONCURRENCY} \\
    --loglevel=info \\
    --logfile=${APP_DIR}/logs/celery-worker.log \\
    --pidfile=${APP_DIR}/run/celery-worker.pid \\
    --detach
ExecStop=${APP_DIR}/venv/bin/celery multi stopwait worker \\
    --pidfile=${APP_DIR}/run/celery-worker.pid \\
    --logfile=${APP_DIR}/logs/celery-worker.log
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
CELWEOF

info "Configuring Celery ML worker service (queue: ml)..."
cat > /etc/systemd/system/erp-celery-ml-worker.service <<CELMLEOF
[Unit]
Description=ERP Django Celery ML Worker (ml queue — scikit-learn, prophet, numpy)
After=network.target postgresql.service redis-server.service

[Service]
Type=forking
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
PIDFile=${APP_DIR}/run/celery-ml-worker.pid
# Lower concurrency: each task is CPU-bound (model training / inference).
# Adjust ML_CELERY_CONCURRENCY in .env to match available CPU cores.
ExecStart=${APP_DIR}/venv/bin/celery \\
    -A erpproject worker \\
    --queues=ml \\
    --concurrency=${ML_CELERY_CONCURRENCY:-2} \\
    --loglevel=info \\
    --logfile=${APP_DIR}/logs/celery-ml-worker.log \\
    --pidfile=${APP_DIR}/run/celery-ml-worker.pid \\
    --detach
ExecStop=${APP_DIR}/venv/bin/celery multi stopwait worker \\
    --pidfile=${APP_DIR}/run/celery-ml-worker.pid \\
    --logfile=${APP_DIR}/logs/celery-ml-worker.log
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
CELMLEOF

info "Configuring Celery beat scheduler service..."
cat > /etc/systemd/system/erp-celery-beat.service <<CELBEOF
[Unit]
Description=ERP Django Celery Beat Scheduler
After=network.target postgresql.service redis-server.service erp-celery-worker.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
# --scheduler django_celery_beat.schedulers:DatabaseScheduler allows editing
# schedules via Django admin; falls back to the static beat_schedule in celery.py
ExecStart=${APP_DIR}/venv/bin/celery \\
    -A erpproject beat \\
    --loglevel=info \\
    --logfile=${APP_DIR}/logs/celery-beat.log \\
    --pidfile=${APP_DIR}/run/celery-beat.pid \\
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
CELBEOF

systemctl daemon-reload
systemctl enable --now erp-celery-worker.service
systemctl enable --now erp-celery-ml-worker.service
systemctl enable --now erp-celery-beat.service
ok "Celery worker, ML worker, and beat services active"

###############################################################################
# 11. Nginx Configuration
###############################################################################
info "Configuring Nginx..."

cat > /etc/nginx/sites-available/erp <<'NGINXEOF'
# ── Upstream ────────────────────────────────────────────────────────────────
upstream erp_backend {
    server unix:APP_DIR_PLACEHOLDER/run/gunicorn.sock fail_timeout=0;
}

# ── Redirect HTTP → HTTPS ──────────────────────────────────────────────────
server {
    listen 80;
    listen [::]:80;
    server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# ── HTTPS Server ───────────────────────────────────────────────────────────
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

    # SSL — will be replaced by Certbot or self-signed
    ssl_certificate     /etc/ssl/certs/erp-selfsigned.crt;
    ssl_certificate_key /etc/ssl/private/erp-selfsigned.key;

    # SSL hardening
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    client_max_body_size 20M;

    # ── Static files (WhiteNoise pre-compresses; Nginx serves gzip/br) ──
    location /static/ {
        alias APP_DIR_PLACEHOLDER/staticfiles/;
        expires max;
        add_header Cache-Control "public, max-age=315360000, immutable";
        gzip_static on;
    }

    # ── Media files ────────────────────────────────────────────────────────
    location /media/ {
        alias APP_DIR_PLACEHOLDER/media/;
        expires 7d;
    }

    # ── Favicon ────────────────────────────────────────────────────────────
    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }

    # ── Application ────────────────────────────────────────────────────────
    location / {
        proxy_pass http://erp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
        proxy_redirect off;
    }
}
NGINXEOF

# Replace placeholders
sed -i "s|APP_DIR_PLACEHOLDER|${APP_DIR}|g" /etc/nginx/sites-available/erp
sed -i "s|DOMAIN_PLACEHOLDER|${DOMAIN}|g" /etc/nginx/sites-available/erp

# Enable site, remove default
ln -sf /etc/nginx/sites-available/erp /etc/nginx/sites-enabled/erp
rm -f /etc/nginx/sites-enabled/default

# Generate self-signed cert as fallback
if [[ ! -f /etc/ssl/certs/erp-selfsigned.crt ]]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/ssl/private/erp-selfsigned.key \
        -out /etc/ssl/certs/erp-selfsigned.crt \
        -subj "/CN=${DOMAIN}" 2>/dev/null
fi

nginx -t
systemctl restart nginx
ok "Nginx configured"

###############################################################################
# 12. SSL Certificate (Let's Encrypt)
###############################################################################
if [[ "$ENABLE_SSL" == "true" && -n "$SSL_EMAIL" ]]; then
    info "Obtaining Let's Encrypt certificate..."
    mkdir -p /var/www/certbot
    certbot --nginx \
        -d "$DOMAIN" -d "www.${DOMAIN}" \
        --email "$SSL_EMAIL" \
        --agree-tos \
        --non-interactive \
        --redirect \
        || warn "Certbot failed — check DNS points to this server. Using self-signed cert."
    ok "SSL certificate installed"
fi

###############################################################################
# 13. Firewall (UFW)
###############################################################################
info "Configuring firewall..."
ufw --force reset >/dev/null 2>&1
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx Full'
# PostgreSQL and Redis only on localhost (no external access)
ufw --force enable
ok "Firewall enabled (SSH + HTTP/HTTPS)"

###############################################################################
# 14. Log Rotation
###############################################################################
info "Setting up log rotation..."
cat > /etc/logrotate.d/erpdjango <<LOGEOF
${APP_DIR}/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 ${APP_USER} ${APP_USER}
    postrotate
        systemctl reload erp-gunicorn 2>/dev/null || true
        systemctl kill -s HUP erp-celery-worker 2>/dev/null || true
        systemctl restart erp-celery-beat 2>/dev/null || true
    endscript
}
LOGEOF
ok "Log rotation configured"

###############################################################################
# 15. Maintenance Cron Jobs
###############################################################################
info "Setting up cron jobs..."
CRON_FILE="/etc/cron.d/erpdjango"
cat > "$CRON_FILE" <<CRONEOF
# ERP Django maintenance tasks
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Renew SSL certs daily at 3:30 AM
30 3 * * * root certbot renew --quiet --post-hook "systemctl reload nginx"

# Clear expired Django sessions weekly (Sunday 4 AM)
0 4 * * 0 ${APP_USER} cd ${APP_DIR} && ${APP_DIR}/venv/bin/python manage.py clearsessions

# Backup main database daily at 2 AM
0 2 * * * root pg_dump -U ${DB_USER} ${DB_NAME} | gzip > /opt/backups/erp_main_\$(date +\%Y\%m\%d).sql.gz 2>/dev/null
CRONEOF
chmod 644 "$CRON_FILE"

# Create backup directory
mkdir -p /opt/backups
chown root:root /opt/backups
ok "Cron jobs configured"

###############################################################################
# 16. Final Health Check
###############################################################################
info "Running final health check..."
sleep 2
if systemctl is-active --quiet erp-gunicorn; then
    ok "Gunicorn is running"
else
    warn "Gunicorn is not running — check: journalctl -u erp-gunicorn"
fi

if systemctl is-active --quiet erp-celery-worker; then
    ok "Celery worker is running (queues: celery, default)"
else
    warn "Celery worker is not running — check: journalctl -u erp-celery-worker"
fi

if systemctl is-active --quiet erp-celery-ml-worker; then
    ok "Celery ML worker is running (queue: ml)"
else
    warn "Celery ML worker is not running — check: journalctl -u erp-celery-ml-worker"
fi

if systemctl is-active --quiet erp-celery-beat; then
    ok "Celery beat is running"
else
    warn "Celery beat is not running — check: journalctl -u erp-celery-beat"
fi

if systemctl is-active --quiet nginx; then
    ok "Nginx is running"
else
    warn "Nginx is not running — check: journalctl -u nginx"
fi

if systemctl is-active --quiet postgresql; then
    ok "PostgreSQL is running"
else
    warn "PostgreSQL is not running"
fi

if systemctl is-active --quiet redis-server; then
    ok "Redis is running"
else
    warn "Redis is not running"
fi

if systemctl is-active --quiet docker; then
    ok "Docker is running"
else
    warn "Docker is not running"
fi

# Verify the socket proxy is up and the app can reach it
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q erp_docker_proxy; then
    ok "Docker Socket Proxy is running (app connects to tcp://127.0.0.1:2375)"
else
    warn "Docker Socket Proxy is not running — check: docker ps -a | grep erp_docker_proxy"
fi

###############################################################################
# Done!
###############################################################################
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}Deployment complete!${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  URL        : https://${DOMAIN}"
echo "  App Dir    : ${APP_DIR}"
echo "  Logs       : ${APP_DIR}/logs/"
echo "  .env       : ${APP_DIR}/.env"
echo ""
echo "  Useful commands:"
echo "    systemctl status  erp-gunicorn        # App status"
echo "    systemctl restart erp-gunicorn        # Restart app"
echo "    journalctl -u erp-gunicorn -f         # Live app logs"
echo ""
echo "    systemctl status  erp-celery-worker   # Celery worker status"
echo "    systemctl restart erp-celery-worker   # Restart worker"
echo "    journalctl -u erp-celery-worker -f    # Live worker logs"
echo "    tail -f ${APP_DIR}/logs/celery-worker.log"
echo ""
echo "    systemctl status  erp-celery-beat     # Beat scheduler status"
echo "    systemctl restart erp-celery-beat     # Restart beat"
echo "    journalctl -u erp-celery-beat -f      # Live beat logs"
echo "    tail -f ${APP_DIR}/logs/celery-beat.log"
echo ""
echo "    sudo -u ${APP_USER} ${APP_DIR}/venv/bin/python ${APP_DIR}/manage.py <cmd>"
echo ""
echo "  Re-deploy after code changes:"
echo "    sudo bash deploy/deploy.sh"
echo ""
echo "═══════════════════════════════════════════════════════════════"
