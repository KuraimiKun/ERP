"""
URL configuration for ERP Multi-Tenant Project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from tenants import views as tenant_views

from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _

urlpatterns = [
    # Admin site - keep outside i18n if desired, or inside. Usually admin is fine outside.
    path('admin/', admin.site.urls),
    # Internationalization
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += i18n_patterns(
    # Tenant/Auth URLs
    path('', tenant_views.home, name='home'),
    path('accounts/', include('tenants.urls')),
    
    # ERP application URLs (protected by tenant middleware)
    path('erp/', include('erp.urls')),
    
    # API URLs - generally APIs don't need i18n prefix unless required. Keeping it inside for consistency or outside if preferred.
    # The user asked for "whole website" so i18n patterns makes sense.
    path('api/', include('erp.api.urls')),
)


# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
