"""
Tenant Middleware

This middleware:
1. Determines the current user's tenant database
2. Sets the database context for the request
3. Handles access control for unapproved users
"""

from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings

from .routers import set_current_db_alias, clear_current_db_alias, get_tenant_db_alias, add_tenant_database


# URLs that don't require tenant database access
PUBLIC_URLS = [
    '/admin/',
    '/accounts/login/',
    '/accounts/logout/',
    '/accounts/signup/',
    '/accounts/pending/',
    '/accounts/rejected/',
    '/accounts/register/',
    '/',
    '/static/',
    '/media/',
]

# URL fragments for kiosk pages – authenticated via device cookie, not user session
KIOSK_URL_FRAGMENTS = [
    '/attendance/kiosk/',
    '/api/attendance/qr/',
]


class TenantMiddleware:
    """
    Middleware to handle tenant database routing and access control.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Clear any previous tenant context
        clear_current_db_alias()

        # Check if this is a public URL
        path = request.path
        is_public = any(path.startswith(url) for url in PUBLIC_URLS)

        # Mobile API: use X-Tenant-DB header for tenant context.
        # Login endpoint is excluded (it resolves tenant itself).
        if '/api/mobile/' in path:
            tenant_db = request.META.get('HTTP_X_TENANT_DB', '')
            if tenant_db:
                if tenant_db in settings.DATABASES:
                    set_current_db_alias(tenant_db)
                elif tenant_db.startswith('tenant_'):
                    # After server restart, dynamically added DBs are lost.
                    # Re-register from the TenantDatabase record.
                    try:
                        from .models import TenantDatabase
                        db_id = tenant_db.replace('tenant_', '')
                        tdb = TenantDatabase.objects.get(id=db_id, status='active')
                        add_tenant_database(tdb)
                        set_current_db_alias(tenant_db)
                    except Exception:
                        pass
            response = self.get_response(request)
            clear_current_db_alias()
            return response

        # Kiosk pages are public (cookie-authenticated, not user-session)
        is_kiosk = any(fragment in path for fragment in KIOSK_URL_FRAGMENTS)
        if is_kiosk:
            # The kiosk view itself will set up the tenant DB context
            response = self.get_response(request)
            clear_current_db_alias()
            return response
        
        # Handle authenticated users
        if request.user.is_authenticated:
            # Admin users always use default database
            if request.user.is_staff or request.user.is_superuser:
                set_current_db_alias('default')
            else:
                # Check approval status
                if not request.user.is_approved:
                    # Allow access to public URLs and waiting pages
                    if not is_public:
                        if request.user.approval_status == 'pending':
                            return redirect('tenants:pending_approval')
                        elif request.user.approval_status == 'rejected':
                            return redirect('tenants:rejected')
                        elif request.user.approval_status == 'suspended':
                            messages.error(request, 'Your account has been suspended.')
                            return redirect('tenants:login')
                else:
                    # Get and set the tenant database
                    db_alias = get_tenant_db_alias(request.user)
                    
                    if db_alias == 'default' and not is_public and not path.startswith('/admin/'):
                        # User is approved but has no database assigned
                        if not path.startswith('/accounts/no-database/'):
                            return redirect('tenants:no_database')
                    
                    set_current_db_alias(db_alias)
        
        # Process the request
        response = self.get_response(request)
        
        # Clear tenant context after request
        clear_current_db_alias()
        
        return response
