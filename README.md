<div align="center">

# Kuraimi ERP

**A full-stack, multi-tenant ERP platform built with Django and Flutter**

[![Django](https://img.shields.io/badge/Django-5.1-0C4B33?style=flat-square&logo=django&logoColor=white)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.14-A30000?style=flat-square&logo=django&logoColor=white)](https://www.django-rest-framework.org)
[![Flutter](https://img.shields.io/badge/Flutter-Mobile-02569B?style=flat-square&logo=flutter&logoColor=white)](https://flutter.dev)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![CI/CD](https://img.shields.io/github/actions/workflow/status/KuraimiKun/ERP/ci.yml?branch=main&style=flat-square&label=CI%2FCD&logo=github-actions&logoColor=white)](https://github.com/KuraimiKun/ERP/actions)

<br/>

Each business gets its own **isolated PostgreSQL database**. One platform, unlimited tenants — with a companion Flutter mobile app for employees.

[Live Demo](#) · [Download App](#download) · [API Docs](#api) · [Report Bug](https://github.com/KuraimiKun/ERP/issues)

</div>

---

## What's Inside

| Layer | Technology |
|---|---|
| **Backend** | Django 5.1 · Django REST Framework · Celery · Redis |
| **Database** | PostgreSQL (multi-tenant, per-org isolation) · Docker containers |
| **Frontend** | Server-rendered Django templates · HTMX-friendly |
| **Mobile** | Flutter (Android · iOS coming soon) |
| **Infrastructure** | Nginx · Gunicorn · GitHub Actions CI/CD · GCP Compute Engine |
| **AI / ML** | OpenAI integration · scikit-learn · plotly charts |
| **Auth** | Token auth (API) · Session auth (web) · Rate limiting · Account lockout |

---

## Modules

<table>
<tr>
<td width="50%">

### 💰 Finance
- Customer invoicing & payments
- Expense tracking
- Journal entries & ledger
- Financial reports (PDF export)
- Fixed assets management

### 👥 HR
- Employee profiles & documents
- Departments & org chart
- Attendance tracking (QR kiosk)
- Leave requests & approvals
- Payroll & payslips

### 🛒 POS
- Terminal & session management
- Product catalog with categories
- Customer management
- Multiple payment methods
- Receipt generation & order history

</td>
<td width="50%">

### 📦 Inventory
- Products & stock levels
- Warehouse management
- Purchase orders
- Stock movements

### 🤝 CRM
- Lead tracking & campaigns
- Customer interactions
- Pipeline management

### 🔧 Services
- Service catalog
- Quotes & work orders

### 🏢 Supplier Management
- Supplier profiles
- Purchase orders
- Supplier payments

</td>
</tr>
</table>

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      Internet                              │
└────────────────────────┬───────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │  Nginx  │  SSL termination · static files
                    └────┬────┘
                         │
              ┌──────────▼──────────┐
              │  Gunicorn Workers   │  WSGI · unix socket
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌─────▼─────┐   ┌────▼────┐
    │  Django  │    │  Celery   │   │   DRF   │
    │   Web   │    │  Workers  │   │  Mobile │
    └────┬────┘    └─────┬─────┘   │   API   │
         │               │         └────┬────┘
         └───────────────┴──────────────┘
                         │
              ┌──────────▼──────────┐
              │   Default DB        │  Users · tenants · servers
              │   (erp_main)        │
              └─────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
   │ tenant  │      │ tenant  │      │ tenant  │
   │  db_1   │      │  db_2   │      │  db_N   │
   │ (org A) │      │ (org B) │      │ (org N) │
   └─────────┘      └─────────┘      └─────────┘
```

Each tenant database is **completely isolated** — separate schema, separate credentials. A compromised tenant cannot read another tenant's data.

---

## Mobile App

The Flutter employee app connects to the same REST API:

- **Login** with company credentials
- **Dashboard** — attendance status, pending tasks, leave balance
- **Attendance** — QR scan check-in/out
- **Payslips** — view and download
- **Leave requests** — apply, track, cancel
- **Tasks** — view assigned tasks, update status, add comments
- **Notifications** — real-time push alerts
- **POS** — full point-of-sale terminal

<a id="download"></a>

> **Android APK** — available at `/accounts/download-app/` on your deployment.  
> **iOS** — coming soon.

---

## Platform Admin

A dedicated super-admin panel (`/accounts/platform-admin/`) for managing the entire platform:

| Section | Capability |
|---|---|
| **Tenants & Users** | Approve/reject signups, assign databases, manage roles |
| **Servers** | Add Docker or remote PostgreSQL servers |
| **Databases** | Create, clone, backup, restore tenant databases |
| **Monitoring** | Real-time server health, resource usage, alerts |
| **Docker** | Container management, logs, stats, terminal |
| **Logs** | Filterable system-wide audit log |
| **Analytics** | Tenant growth, usage trends, KPI charts |
| **Invites** | Generate employee self-registration links |
| **Announcements** | Broadcast messages to tenants |
| **Scheduled Tasks** | Manage Celery beat jobs |
| **Support Tickets** | Respond to tenant support requests |

---

## Quick Start (Development)

### Prerequisites

- Python 3.12
- PostgreSQL 15
- Redis
- Docker (optional — for tenant DB containers)

### 1. Clone & set up environment

```bash
git clone https://github.com/KuraimiKun/ERP.git
cd ERP
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 2. Configure `.env`

```bash
cp .env.example .env   # then edit with your values
```

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=erp_main
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/0
FIELD_ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

### 3. Create the database & run migrations

```bash
createdb erp_main
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run services

```bash
# Terminal 1 — Django
python manage.py runserver

# Terminal 2 — Celery worker
celery -A erpproject worker -l info

# Terminal 3 — Celery beat (scheduled tasks)
celery -A erpproject beat -l info
```

Visit **http://localhost:8000** · Admin at **http://localhost:8000/admin/**

---

## Production Deployment (CI/CD)

Deployment is fully automated via GitHub Actions. Every push to `main`:

1. **Runs tests** — pytest · ruff lint · mypy type-check · migration check
2. **Detects mode** — Bootstrap (fresh server) or Fast Deploy (existing server)
3. **Syncs code** — rsync to GCP Compute Engine over SSH
4. **Applies changes** — pip install · migrate · collectstatic
5. **Zero-downtime reload** — `systemctl reload` sends SIGHUP to gunicorn; old workers drain while new workers serve

### Required GitHub Secrets

| Secret | Description |
|---|---|
| `VPS_HOST` | Server IP or hostname |
| `VPS_USER` | SSH user |
| `VPS_SSH_KEY` | Private SSH key |
| `PROD_SECRET_KEY` | Django secret key |
| `PROD_DB_PASSWORD` | PostgreSQL password |
| `PROD_FIELD_ENCRYPTION_KEY` | Fernet encryption key |
| `PROD_SSL_EMAIL` | Let's Encrypt email |
| `PROD_SUPERUSER_EMAIL` | Initial admin email |
| `PROD_SUPERUSER_PASSWORD` | Initial admin password |

To force a full server bootstrap (fresh instance):
```
GitHub → Actions → Run workflow → ✅ Force bootstrap
```

---

## API

REST API served at `/api/` with OpenAPI schema at `/api/schema/` and Swagger UI at `/api/docs/`.

Mobile API served at `/api/mobile/` — uses token authentication with a per-request `X-Tenant-DB` header for tenant routing.

```http
POST   /api/mobile/auth/login/
POST   /api/mobile/auth/logout/
GET    /api/mobile/dashboard/
GET    /api/mobile/attendance/
POST   /api/mobile/attendance/scan/
GET    /api/mobile/leaves/
POST   /api/mobile/leaves/
GET    /api/mobile/payslips/
GET    /api/mobile/tasks/
GET    /api/mobile/notifications/
POST   /api/mobile/pos/sessions/open/
...
```

<a id="api"></a>

---

## Project Structure

```
erpdjango/
├── erp/                    # Core ERP app
│   ├── models/             # finance · hr · crm · inventory · pos · services
│   ├── views/              # Feature views per module
│   ├── api/                # DRF serializers, views, mobile API
│   ├── tasks/              # Celery async tasks
│   ├── ai/                 # OpenAI & ML integrations
│   └── templates/          # Django HTML templates
├── tenants/                # Multi-tenancy & platform management
│   ├── models.py           # TenantUser · TenantDatabase · DatabaseAssignment
│   ├── middleware.py       # Per-request DB routing
│   ├── routers.py          # Django multi-DB router
│   └── platform_admin/     # Super-admin panel
├── mobile/                 # Flutter mobile app
│   └── lib/
│       ├── screens/        # auth · dashboard · attendance · leaves · pos
│       ├── providers/      # State management
│       └── services/       # API client · storage
├── deploy/                 # deploy.sh · nginx patches · CI helpers
├── .github/workflows/      # CI/CD pipeline (ci.yml)
└── erpproject/             # Django settings · URL root · Celery config
```

---

## Tech Stack

<div align="center">

![Django](https://img.shields.io/badge/-Django-0C4B33?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/-PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/-Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/-Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![Flutter](https://img.shields.io/badge/-Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![Nginx](https://img.shields.io/badge/-Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white)
![Docker](https://img.shields.io/badge/-Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/-GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)
![GCP](https://img.shields.io/badge/-Google_Cloud-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)
![OpenAI](https://img.shields.io/badge/-OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)

</div>

---

## License

MIT — see [LICENSE](LICENSE) for details.
