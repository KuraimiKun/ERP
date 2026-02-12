"""
ERP Setup Middleware

Middleware to check if ERP setup is complete and redirect to setup wizard if not.
Works with the multi-tenant architecture to check setup per tenant database.
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

from .setup_views import is_setup_complete


class ERPSetupMiddleware:
    """
    Middleware that checks if ERP setup is complete.
    If not, redirects to the setup wizard for all ERP URLs.
    
    This middleware runs after TenantMiddleware, so the correct
    database context is already set.
    """
    
    # URLs that should be accessible without completing setup
    ALLOWED_URLS = [
        '/erp/setup/',
        '/admin/',
        '/api/',
        '/static/',
        '/media/',
        '/accounts/',  # Auth URLs
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only check for ERP URLs
        if request.path.startswith('/erp/'):
            # Skip check for allowed URLs
            for allowed in self.ALLOWED_URLS:
                if request.path.startswith(allowed):
                    return self.get_response(request)
            
            # Check if user is authenticated
            if request.user.is_authenticated:
                # For approved users with database access
                if hasattr(request.user, 'is_approved') and request.user.is_approved:
                    # Check if setup is complete for this tenant database
                    try:
                        if not is_setup_complete():
                            # Redirect to setup wizard
                            setup_url = reverse('erp:setup_wizard')
                            if not request.path.startswith(setup_url.rstrip('/')):
                                return redirect('erp:setup_wizard')
                    except Exception:
                        # If setup check fails, let the request proceed
                        # The view will handle any database errors
                        pass
        
        return self.get_response(request)
