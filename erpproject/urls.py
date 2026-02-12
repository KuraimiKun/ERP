"""
URL configuration for ERP Multi-Tenant Project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from tenants import views as tenant_views

urlpatterns = [
    # Admin site
    path('admin/', admin.site.urls),
    
    # Tenant/Auth URLs
    path('', tenant_views.home, name='home'),
    path('accounts/', include('tenants.urls')),
    
    # ERP application URLs (protected by tenant middleware)
    path('erp/', include('erp.urls')),
    
    # API URLs
    path('api/', include('erp.api.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
