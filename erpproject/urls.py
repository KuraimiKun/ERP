"""
URL configuration for ERP Multi-Tenant Project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from tenants import views as tenant_views

from django.conf.urls.i18n import i18n_patterns

from .views import health_check

urlpatterns = [
    # ── Infrastructure ────────────────────────────────────────────────────────
    # No i18n prefix, no authentication — safe for load-balancer / Docker probes.
    path('health/', health_check, name='health_check'),

    # ── Admin & i18n ──────────────────────────────────────────────────────────
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),

    # ── Versioned REST API (no i18n prefix — clients use Accept-Language) ─────
    # v1 canonical path — all new integrations should target /api/v1/.
    path('api/v1/', include('erp.api.urls')),
    # Legacy unversioned alias kept for backward compatibility with existing
    # clients.  Will be deprecated in a future release.
    path('api/', include('erp.api.urls')),

    # Mobile API - outside i18n_patterns (uses Accept-Language header instead)
    path('api/mobile/', include('erp.api.mobile_urls')),
]

urlpatterns += i18n_patterns(
    # Tenant/Auth URLs
    path('', tenant_views.home, name='home'),
    path('accounts/', include('tenants.urls')),

    # ERP application URLs (protected by tenant middleware)
    path('erp/', include('erp.urls')),
)


# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
