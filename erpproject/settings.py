"""
Django settings for ERP Multi-Tenant Project.

This project supports multiple PostgreSQL databases with dynamic tenant assignment.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# DEBUG is resolved first so the secret-key checks below can gate on it.
# Defaults to False so a missing .env in production never accidentally
# enables the debug error page.
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# SECURITY WARNING: keep the secret key used in production secret!
_secret = os.getenv('SECRET_KEY', '')
if not _secret:
    if not DEBUG:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            'SECRET_KEY is not set. The application refuses to start in production '
            '(DEBUG=False) without it. Generate one with: '
            'python -c "from django.core.management.utils import get_random_secret_key; '
            'print(get_random_secret_key())"'
        )
    import warnings
    _secret = 'django-insecure-development-only-do-not-deploy!'
    warnings.warn(
        'SECRET_KEY is not set — using an insecure fallback. '
        'Add SECRET_KEY to your .env file.',
        stacklevel=1,
    )
SECRET_KEY = _secret

# ── Field-level encryption key (Fernet, base64url-encoded 32-byte key) ──
_enc_key = os.getenv('FIELD_ENCRYPTION_KEY', '')
if not _enc_key:
    if not DEBUG:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            'FIELD_ENCRYPTION_KEY is not set. The application refuses to start in '
            'production (DEBUG=False) without it. Generate one with: '
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    import warnings
    warnings.warn(
        'FIELD_ENCRYPTION_KEY is not set — encrypted model fields will fail. '
        'Add FIELD_ENCRYPTION_KEY to your .env file.',
        stacklevel=1,
    )
FIELD_ENCRYPTION_KEY = _enc_key

_allowed_hosts_raw = os.getenv('ALLOWED_HOSTS', '')
if not _allowed_hosts_raw:
    if not DEBUG:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            'ALLOWED_HOSTS is not set. The application refuses to start in production '
            '(DEBUG=False) without it. Set it to your domain, e.g.: '
            'ALLOWED_HOSTS=erp.example.com'
        )
    _allowed_hosts_raw = 'localhost,127.0.0.1,10.0.2.2'
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_raw.split(',') if h.strip()]

# ── Upload size limits ──────────────────────────────────────────────────────
# Max size of a POST body (covers form data + file uploads processed in memory)
DATA_UPLOAD_MAX_MEMORY_SIZE = 52_428_800       # 50 MB
# Uploads larger than this threshold spool to disk instead of memory
FILE_UPLOAD_MAX_MEMORY_SIZE = 5_242_880        # 5 MB

# ── Production security settings (active when DEBUG=False) ──────────────────
if not DEBUG:
    # Tell Django it's behind a trusted SSL-terminating proxy (Nginx)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # Enable SSL redirect as defence-in-depth; disable only if a
    # reverse-proxy (Nginx) already handles HTTP→HTTPS.
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 'yes')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = 'Strict'
    # 1 year HSTS; remove includeSubDomains if subdomains don't use HTTPS
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Prevent the Referer header from leaking the full URL to cross-origin
    # destinations (e.g. third-party analytics, CDN images).
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ── Session lifetime ────────────────────────────────────────────────────────
# ERP sessions expire after 8 hours of inactivity (or at browser close).
# The 2-week Django default is too long for a system with financial data.
SESSION_COOKIE_AGE = int(os.getenv('SESSION_COOKIE_AGE', str(8 * 3600)))  # 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third party apps
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap5',
    'drf_spectacular',

    # Local apps
    'tenants',  # Multi-tenant management app
    'erp',      # ERP application
    'erp.ai',   # AI & ML module
    
    # Task scheduling
    'django_celery_beat',

    # Cloud / local media storage (django-storages)
    'storages',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # CSP headers — only active when django-csp is installed and
    # CSP_ENABLED=true is set in the environment.  Install with:
    #   pip install django-csp
    # then set CSP_ENABLED=true and tune the directives below.
    *(['csp.middleware.CSPMiddleware'] if os.getenv('CSP_ENABLED', '').lower() in ('true', '1', 'yes') else []),
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # Added for i18n support
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tenants.middleware.TenantMiddleware',  # Custom tenant middleware
    'erp.middleware.ERPSetupMiddleware',  # ERP setup check middleware
    'erp.services.audit.AuditMiddleware',  # Audit logging context middleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'erpproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'tenants.context_processors.tenant_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'erpproject.wsgi.application'


# Database
# The 'default' database stores tenant/user management data
# Tenant databases are added dynamically

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'erp_main'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'CONN_MAX_AGE': int(os.getenv('CONN_MAX_AGE', '600')),
        'CONN_HEALTH_CHECKS': True,
        # Kill runaway queries after 30 s to prevent table locks and
        # connection starvation from slow AI aggregations or bad reports.
        'OPTIONS': {
            'options': f"-c statement_timeout={os.getenv('DB_STATEMENT_TIMEOUT_MS', '30000')}",
        },
    }
}

# Database router for multi-tenancy
DATABASE_ROUTERS = ['tenants.routers.TenantDatabaseRouter']


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Custom user model
AUTH_USER_MODEL = 'tenants.TenantUser'


# Internationalization
LANGUAGE_CODE = 'ar'  # Default language set to Arabic

# Supported Languages
from django.utils.translation import gettext_lazy as _

LANGUAGES = [
    ('ar', _('Arabic')),
    ('en', _('English')),
    ('id', _('Indonesian')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise: compressed static serving with content-hash cache-busting.
# In production collectstatic produces hashed filenames (style.abc123.css)
# and pre-compresses them with gzip + Brotli.  Browsers that send
# Accept-Encoding get the compressed version with zero runtime cost.

# ── Cloud / Local Media Storage ──────────────────────────────────────────────
# Set CLOUD_STORAGE_PROVIDER=s3|gcs|azure in .env to route all FileField /
# ImageField uploads to a cloud bucket.  Leave unset (or empty) to keep files
# on the local filesystem (fine for single-server deployments managed by
# deploy.sh, where /opt/erpdjango/media is on a persistent volume).
_CLOUD_STORAGE_PROVIDER = os.getenv('CLOUD_STORAGE_PROVIDER', '').lower()

if _CLOUD_STORAGE_PROVIDER == 's3':
    _DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
elif _CLOUD_STORAGE_PROVIDER == 'gcs':
    _DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
elif _CLOUD_STORAGE_PROVIDER == 'azure':
    _DEFAULT_FILE_STORAGE = 'storages.backends.azure_storage.AzureStorage'
else:
    _DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

STORAGES = {
    'default': {
        'BACKEND': _DEFAULT_FILE_STORAGE,
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Media files — local fallback (overridden per-provider below)
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── AWS S3 ────────────────────────────────────────────────────────────────────
if _CLOUD_STORAGE_PROVIDER == 's3':
    AWS_ACCESS_KEY_ID        = os.getenv('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY    = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    AWS_STORAGE_BUCKET_NAME  = os.getenv('AWS_STORAGE_BUCKET_NAME', '')
    AWS_S3_REGION_NAME       = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_FILE_OVERWRITE    = False   # keep original filename on collision
    AWS_DEFAULT_ACL          = None    # honour bucket policy; no per-object ACLs
    AWS_QUERYSTRING_AUTH     = False   # serve public (unsigned) URLs
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    MEDIA_URL = (
        f'https://{AWS_STORAGE_BUCKET_NAME}'
        f'.s3.{AWS_S3_REGION_NAME}.amazonaws.com/media/'
    )

# ── Google Cloud Storage ──────────────────────────────────────────────────────
elif _CLOUD_STORAGE_PROVIDER == 'gcs':
    GS_BUCKET_NAME    = os.getenv('GCS_BUCKET_NAME', '')
    GS_DEFAULT_ACL    = None
    GS_FILE_OVERWRITE = False
    MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'

# ── Azure Blob Storage ────────────────────────────────────────────────────────
elif _CLOUD_STORAGE_PROVIDER == 'azure':
    AZURE_ACCOUNT_NAME    = os.getenv('AZURE_ACCOUNT_NAME', '')
    AZURE_ACCOUNT_KEY     = os.getenv('AZURE_ACCOUNT_KEY', '')
    AZURE_CONTAINER       = os.getenv('AZURE_CONTAINER', 'media')
    AZURE_OVERWRITE_FILES = False
    MEDIA_URL = (
        f'https://{os.getenv("AZURE_ACCOUNT_NAME", "")}'
        f'.blob.core.windows.net/{os.getenv("AZURE_CONTAINER", "media")}/'
    )


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'


# ── Cache (used for rate-limiting and sessions) ────────────────────────────
_redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/1')

if not DEBUG:
    # Production: always connect to Redis.  Do NOT probe at startup and silently
    # fall back — a Redis micro-outage at Gunicorn restart time would cause the
    # entire fleet to degrade to LocMemCache, breaking:
    #   • rate limiters (each worker counts independently → trivially bypassable)
    #   • session state (logged-out users across workers)
    #   • any cross-process coordination that relies on shared cache
    # Let the error surface immediately so it is noticed and fixed.
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
            # Prefix all keys with a version tag so rolling deployments with
            # incompatible cache structures never serve stale data across restarts.
            'KEY_PREFIX': os.getenv('CACHE_KEY_PREFIX', 'erp_v1'),
        }
    }
else:
    # Development only: probe Redis and degrade gracefully when it is not running.
    # This lets developers work on non-caching features without Docker.
    def _redis_available(url):
        try:
            import redis as _r
            c = _r.Redis.from_url(url, socket_connect_timeout=1)
            c.ping()
            c.close()
            return True
        except Exception:
            return False

    if _redis_available(_redis_url):
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': _redis_url,
            }
        }
    else:
        import warnings
        warnings.warn(
            f'Redis not reachable at {_redis_url} – falling back to LocMemCache. '
            'Run "docker compose up -d redis" to start Redis.',
            stacklevel=1,
        )
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        }

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'erp.ratelimit.BurstRateThrottle',
        'erp.ratelimit.SustainedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'burst': '60/min',
        'sustained': '1000/day',
        'login': '3/min',
        # CPU/memory-intensive on-demand operations (AI triggers, ML training)
        'heavy': '10/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ── OpenAPI / Swagger documentation ─────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'Kuraimi ERP API',
    'DESCRIPTION': 'REST API for Kuraimi ERP — finance, HR, CRM, inventory, suppliers, services, reporting, and AI modules.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/api/',

    'TAGS': [
        # Core
        {'name': 'currencies', 'description': 'Currency management'},
        {'name': 'companies', 'description': 'Company settings'},
        {'name': 'departments', 'description': 'Department structure'},
        {'name': 'branches', 'description': 'Branch offices'},
        {'name': 'fiscal-years', 'description': 'Fiscal year configuration'},
        # HR
        {'name': 'employees', 'description': 'Employee management'},
        {'name': 'leave-types', 'description': 'Leave type configuration'},
        {'name': 'leave-requests', 'description': 'Leave request workflow'},
        {'name': 'attendance', 'description': 'Attendance tracking'},
        {'name': 'payroll', 'description': 'Payroll management'},
        # Finance
        {'name': 'accounts', 'description': 'Chart of accounts'},
        {'name': 'tax-rates', 'description': 'Tax rate configuration'},
        {'name': 'payment-methods', 'description': 'Payment method setup'},
        {'name': 'customers', 'description': 'Customer management'},
        {'name': 'invoices', 'description': 'Invoice management'},
        {'name': 'payments', 'description': 'Payment processing'},
        {'name': 'expense-categories', 'description': 'Expense categories'},
        {'name': 'expenses', 'description': 'Expense management'},
        # Suppliers
        {'name': 'suppliers', 'description': 'Supplier management'},
        {'name': 'supplier-contacts', 'description': 'Supplier contacts'},
        {'name': 'purchase-orders', 'description': 'Purchase order workflow'},
        # CRM
        {'name': 'leads', 'description': 'Lead management & scoring'},
        {'name': 'lead-activities', 'description': 'Lead activity tracking'},
        {'name': 'customer-interactions', 'description': 'Customer interaction log'},
        {'name': 'campaigns', 'description': 'Marketing campaigns'},
        {'name': 'tasks', 'description': 'Task management'},
        {'name': 'task-comments', 'description': 'Task comments'},
        # Services
        {'name': 'service-categories', 'description': 'Service categories'},
        {'name': 'service-pricing', 'description': 'Service pricing'},
        {'name': 'quotes', 'description': 'Quotation management'},
        # Reporting
        {'name': 'dashboards', 'description': 'Dashboard configuration'},
        {'name': 'dashboard-widgets', 'description': 'Dashboard widget setup'},
        {'name': 'kpis', 'description': 'KPI tracking'},
        {'name': 'report-templates', 'description': 'Report template builder'},
        {'name': 'generated-reports', 'description': 'Generated reports'},
        {'name': 'report-data-sources', 'description': 'Report data sources'},
        # Audit
        {'name': 'audit-logs', 'description': 'Audit trail'},
        {'name': 'notifications', 'description': 'User notifications'},
        # Inventory & Warehouse
        {'name': 'uom', 'description': 'Units of measure'},
        {'name': 'uom-conversions', 'description': 'UoM conversion factors'},
        {'name': 'warehouses', 'description': 'Warehouse management'},
        {'name': 'warehouse-zones', 'description': 'Warehouse zones'},
        {'name': 'warehouse-bins', 'description': 'Warehouse bin locations'},
        {'name': 'lots', 'description': 'Lot/batch tracking'},
        {'name': 'serial-numbers', 'description': 'Serial number tracking'},
        {'name': 'stock-items', 'description': 'Stock item catalog'},
        {'name': 'stock-movements', 'description': 'Stock movement history'},
        {'name': 'goods-receipts', 'description': 'Goods receipt notes'},
        {'name': 'stock-transfers', 'description': 'Inter-warehouse transfers'},
        {'name': 'stock-adjustments', 'description': 'Stock adjustments'},
        {'name': 'cycle-counts', 'description': 'Cycle count operations'},
        {'name': 'pick-lists', 'description': 'Pick list management'},
        {'name': 'shipments', 'description': 'Shipment notes'},
        {'name': 'reorder-rules', 'description': 'Automatic reorder rules'},
        {'name': 'valuation-config', 'description': 'Inventory valuation'},
    ],

    'SECURITY': [
        {'sessionAuth': []},
        {'tokenAuth': []},
    ],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'sessionAuth': {
                'type': 'apiKey',
                'in': 'cookie',
                'name': 'sessionid',
            },
            'tokenAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'Token-based auth. Format: "Token <api_key>"',
            },
        },
    },
}

# CORS settings
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:8000').split(',')
# Cache CORS preflight responses for 1 hour to reduce OPTIONS request overhead.
CORS_PREFLIGHT_MAX_AGE = 3600


# Login/Logout URLs
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'


# Docker settings for local PostgreSQL containers
DOCKER_ENABLED = os.getenv('DOCKER_ENABLED', 'True').lower() in ('true', '1', 'yes')
DOCKER_POSTGRES_IMAGE = os.getenv('DOCKER_POSTGRES_IMAGE', 'postgres:15-alpine')
DOCKER_NETWORK = os.getenv('DOCKER_NETWORK', 'erp_network')


# Email settings
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@erp.local')


# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'erp.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB per file
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'tenants': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
(BASE_DIR / 'logs').mkdir(exist_ok=True)


# ── Celery (async task queue) ───────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'


# ── AI / ML Configuration ──────────────────────────────────────────────────
# Global fallback key (used only if a tenant has not set their own).
# Each tenant stores their own OpenAI API key in Company.openai_api_key.
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ML_MODEL_DIR = BASE_DIR / 'ml_models'
ML_MODEL_DIR.mkdir(exist_ok=True)

# How many data points are required before training a model
ML_MIN_TRAINING_SAMPLES = int(os.getenv('ML_MIN_TRAINING_SAMPLES', '30'))

# Service-level target for safety stock (z-score, 1.65 ≈ 95 %)
ML_SAFETY_STOCK_Z = float(os.getenv('ML_SAFETY_STOCK_Z', '1.65'))

# Lead scoring threshold (probability above which a lead is "hot")
ML_LEAD_HOT_THRESHOLD = float(os.getenv('ML_LEAD_HOT_THRESHOLD', '0.70'))


# ── New Relic APM ───────────────────────────────────────────────────────────
NEW_RELIC_LICENSE_KEY = os.getenv('NEW_RELIC_LICENSE_KEY', '')
NEW_RELIC_APP_NAME = os.getenv('NEW_RELIC_APP_NAME', 'ERP Django')
NEW_RELIC_ENABLED = (
    not DEBUG
    and bool(NEW_RELIC_LICENSE_KEY)
)

# ── Sentry Error Tracking ────────────────────────────────────────────────────
# Set SENTRY_DSN in .env to enable real-time error alerting for both Django
# request handling and Celery task failures.  When left empty (the default)
# the Sentry SDK is not initialised and has zero runtime overhead.
# ── Content Security Policy ─────────────────────────────────────────────────
# Activated only when django-csp is installed AND CSP_ENABLED=true.
# Start in report-only mode (CSP_REPORT_ONLY=true) to observe violations
# before enforcing.  Tighten directives incrementally.
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")   # tighten once you add nonces
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "blob:")
CSP_FONT_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'",)
CSP_MEDIA_SRC = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)
CSP_FRAME_ANCESTORS = ("'none'",)           # same as X-Frame-Options: DENY
CSP_FORM_ACTION = ("'self'",)
CSP_REPORT_URI = os.getenv('CSP_REPORT_URI', '')
# Set CSP_REPORT_ONLY=true to receive violation reports without blocking
CSP_REPORT_ONLY = os.getenv('CSP_REPORT_ONLY', 'false').lower() in ('true', '1', 'yes')

# ── Sentry Error Tracking ────────────────────────────────────────────────────
SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        import logging as _logging

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[
                DjangoIntegration(transaction_style='url'),
                CeleryIntegration(monitor_beat_tasks=True),
                LoggingIntegration(
                    level=_logging.WARNING,   # breadcrumbs from WARNING+
                    event_level=_logging.ERROR,  # send event for ERROR+
                ),
            ],
            # Sample 100 % of errors; lower for very high-traffic deployments.
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.0')),
            send_default_pii=False,          # never send passwords / tokens
            environment='production' if not DEBUG else 'development',
            release=os.getenv('GIT_COMMIT', ''),
        )
    except ImportError:
        import warnings
        warnings.warn(
            'SENTRY_DSN is set but sentry-sdk is not installed. '
            'Add sentry-sdk to requirements.txt to enable error tracking.',
            stacklevel=1,
        )
