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

# SECURITY WARNING: keep the secret key used in production secret!
_secret = os.getenv('SECRET_KEY', '')
if not _secret:
    import warnings
    _secret = 'django-insecure-change-this-in-production-please!'
    warnings.warn(
        'SECRET_KEY is not set! Using an insecure default. '
        'Set the SECRET_KEY environment variable before deploying.',
        stacklevel=1,
    )
SECRET_KEY = _secret

# ── Field-level encryption key (Fernet, base64url-encoded 32-byte key) ──
_enc_key = os.getenv('FIELD_ENCRYPTION_KEY', '')
if not _enc_key:
    import warnings
    warnings.warn(
        'FIELD_ENCRYPTION_KEY is not set! Encrypted model fields will fail. '
        'Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
        stacklevel=1,
    )
FIELD_ENCRYPTION_KEY = _enc_key

# SECURITY WARNING: don't run with debug turned on in production!
# Defaults to False so a missing .env in production does NOT accidentally
# expose debug pages.
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,10.0.2.2').split(',')

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
    CSRF_COOKIE_SECURE = True
    # 1 year HSTS; remove includeSubDomains if subdomains don't use HTTPS
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True


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
    
    # Local apps
    'tenants',  # Multi-tenant management app
    'erp',      # ERP application
    'erp.ai',   # AI & ML module
    
    # Task scheduling
    'django_celery_beat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'


# ── Cache (used for rate-limiting and sessions) ────────────────────────────
_redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/1')

# Probe Redis availability so the app can start without it during development.
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
        f'Redis not reachable at {_redis_url} – falling back to local-memory cache. '
        'Run "docker compose up -d" to start Redis.',
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
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# CORS settings
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:8000').split(',')


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
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'erp.log',
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
