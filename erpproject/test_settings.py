"""
Test-specific settings.

Inherits everything from main settings but disables the multi-tenant
database router so all tables (including ERP models) are created in the
default test database.
"""

from .settings import *  # noqa: F401,F403

# Disable multi-tenant routing — all tables go to 'default' test DB.
DATABASE_ROUTERS = []

# Tests run without a live Redis — use in-process cache so they are hermetic
# and don't fail when Redis is absent.  This overrides the fail-fast Redis
# cache configured in settings.py for production (DEBUG=False).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Disable HTTPS redirects during pure unit tests since the test client
# makes unencrypted HTTP requests by default.
SECURE_SSL_REDIRECT = False

# Disable DRF throttling in tests — the LocMemCache is shared across the
# whole test process, so the 60/min burst throttle otherwise spills between
# unrelated tests and causes spurious 429 responses.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}
