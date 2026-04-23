"""
ERP Setup Middleware

Middleware to check if ERP setup is complete and redirect to setup wizard if not.
Works with the multi-tenant architecture to check setup per tenant database.
"""

import re

from django.shortcuts import redirect
from django.urls import reverse

from .setup_views import is_setup_complete

# Regex to strip the i18n language prefix (e.g. /en/, /ar/, /id/)
_LANG_PREFIX_RE = re.compile(r"^/[a-z]{2}(?:-[a-z]{2})?/")


def _strip_lang_prefix(path):
    """Remove the i18n language prefix from a path, if present."""
    return _LANG_PREFIX_RE.sub("/", path)


class ERPSetupMiddleware:
    """
    Middleware that checks if ERP setup is complete.
    If not, redirects to the setup wizard for all ERP URLs.

    This middleware runs after TenantMiddleware, so the correct
    database context is already set.

    Handles i18n-prefixed paths (e.g. /en/erp/, /ar/erp/).
    """

    # URL prefixes (without language prefix) that skip the setup check
    SKIP_PREFIXES = [
        "/erp/setup/",
        "/admin/",
        "/api/",
        "/static/",
        "/media/",
        "/accounts/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Strip the language prefix so checks work regardless of locale
        bare_path = _strip_lang_prefix(request.path)

        # Only check for ERP URLs
        if bare_path.startswith("/erp/"):
            # Skip check for allowed URL prefixes
            for prefix in self.SKIP_PREFIXES:
                if bare_path.startswith(prefix):
                    return self.get_response(request)

            # Check if user is authenticated
            if request.user.is_authenticated:
                # For approved users with database access
                if hasattr(request.user, "is_approved") and request.user.is_approved:
                    # Check if setup is complete for this tenant database
                    try:
                        if not is_setup_complete():
                            setup_url = reverse("erp:setup_wizard")
                            # Don't redirect if we're already on the setup URL
                            if not request.path.startswith(setup_url.rstrip("/")):
                                return redirect("erp:setup_wizard")
                    except Exception:
                        # If setup check fails, let the request proceed
                        # The view will handle any database errors
                        pass

        return self.get_response(request)
