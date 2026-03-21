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
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
