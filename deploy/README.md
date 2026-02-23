# ERP Django — VPS Deployment Guide

## Prerequisites

- A fresh **Ubuntu 22.04 or 24.04 LTS** VPS
- Root/sudo SSH access
- A domain name pointing to the VPS IP (A record)

## Quick Start

### 1. Upload the project to your VPS

```bash
# From your local machine
scp -r . root@your-vps-ip:/tmp/erpdjango
```

### 2. Configure your environment

```bash
ssh root@your-vps-ip
cd /tmp/erpdjango
cp deploy/.env.production.example deploy/.env.production
nano deploy/.env.production   # Fill in your real values
```

**Required settings to change:**
| Variable | Description |
|---|---|
| `DOMAIN` | Your domain name (e.g., `erp.mycompany.com`) |
| `SECRET_KEY` | Django secret key — generate with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DB_PASSWORD` | Strong PostgreSQL password |
| `SSL_EMAIL` | Email for Let's Encrypt SSL certificate |
| `SUPERUSER_EMAIL` | Admin login email |
| `SUPERUSER_PASSWORD` | Admin login password |

### 3. Run the deployment

```bash
sudo bash deploy/deploy.sh
```

This single script handles **everything**:
- System packages (Python 3.12, PostgreSQL 15, Nginx, Docker, Certbot)
- Creates `erp` system user
- Python virtualenv + all dependencies
- PostgreSQL database + user
- Django migrations + collectstatic
- Gunicorn systemd service (socket-activated)
- Nginx reverse proxy with SSL
- UFW firewall (SSH + HTTP/HTTPS only)
- Log rotation
- Cron jobs (SSL renewal, session cleanup, daily DB backup)

### 4. Access your ERP

Open `https://your-domain.com` and log in with the superuser credentials.

---

## Subsequent Updates

After pushing code changes, upload and run:

```bash
# Upload new code
scp -r . root@your-vps-ip:/tmp/erpdjango

# Then on the VPS
sudo bash /tmp/erpdjango/deploy/update.sh
```

This handles: sync files → install deps → migrate → collectstatic → restart services.

---

## Backups

### Manual backup

```bash
sudo bash deploy/backup.sh
```

Backs up the main database, all tenant databases, and media files to `/opt/backups/erp/`.

### Automatic backups

Included in the cron job — runs daily at 2 AM. Old backups (>30 days) are auto-removed.

### Restore from backup

```bash
# Main database
gunzip < /opt/backups/erp/erp_main_20260223.sql.gz | psql -U erp_user erp_main

# Tenant database
gunzip < /opt/backups/erp/tenant_abc_20260223.sql.gz | psql -U postgres tenant_abc

# Media files
tar xzf /opt/backups/erp/media_20260223.tar.gz -C /opt/erpdjango/
```

---

## Service Management

```bash
# App status
systemctl status erp-gunicorn

# Restart app
systemctl restart erp-gunicorn

# View live logs
journalctl -u erp-gunicorn -f

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# App logs
tail -f /opt/erpdjango/logs/gunicorn-access.log
tail -f /opt/erpdjango/logs/erp.log

# Run Django management commands
sudo -u erp /opt/erpdjango/venv/bin/python /opt/erpdjango/manage.py <command>
```

---

## Architecture

```
Internet
    │
    ▼
┌─────────┐    ┌──────────────────┐    ┌───────────────────┐
│  Nginx   │───▶│  Gunicorn (sock) │───▶│  Django / WSGI    │
│  :443    │    │  3 workers       │    │  erpproject.wsgi   │
└─────────┘    └──────────────────┘    └───────┬───────────┘
                                                │
                                    ┌───────────┼───────────┐
                                    ▼           ▼           ▼
                              ┌──────────┐ ┌─────────┐ ┌────────┐
                              │ PG Main  │ │ Docker  │ │ Static │
                              │ erp_main │ │ Tenant  │ │ Files  │
                              │ (users,  │ │ DBs     │ │ /nginx │
                              │ tenants) │ │         │ │        │
                              └──────────┘ └─────────┘ └────────┘
```

---

## File Structure

```
deploy/
├── deploy.sh                  # Full initial deployment
├── update.sh                  # Quick update (code + restart)
├── backup.sh                  # Full backup (DBs + media)
├── .env.production.example    # Template — copy to .env.production
└── README.md                  # This file
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| 502 Bad Gateway | `systemctl restart erp-gunicorn` — check `journalctl -u erp-gunicorn` |
| Static files not loading | `sudo -u erp /opt/erpdjango/venv/bin/python manage.py collectstatic` |
| Database connection refused | `systemctl status postgresql` — check pg_hba.conf |
| Permission denied on socket | `ls -la /opt/erpdjango/run/gunicorn.sock` — should be `erp:www-data 0660` |
| SSL cert expired | `sudo certbot renew --force-renewal && systemctl reload nginx` |
| Docker containers not starting | `systemctl status docker` — check `docker ps -a` |
