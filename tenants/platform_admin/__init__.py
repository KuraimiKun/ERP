"""
Platform Admin Package

Professional management console for superusers to manage
tenants, databases, servers, and system operations.

This package separates concerns into individual modules:
- views_dashboard: Dashboard and overview
- views_users: User/tenant management
- views_servers: PostgreSQL server management
- views_databases: Tenant database management
- views_logs: System logs viewer
- views_activity: Activity feed
- views_settings: Platform settings
- views_invites: Employee invite link management
- views_analytics: Analytics and reporting
- views_backups: Backup management
- views_health: System health overview
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator

from tenants.models import TenantUser


# ── Shared Decorator ─────────────────────────────────────────────────────────

def platform_admin_required(view_func):
    """Only allow superusers to access platform admin views."""
    @wraps(view_func)
    @login_required(login_url='tenants:login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, _('You do not have permission to access the platform admin.'))
            return redirect('tenants:home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Shared Context Helper ────────────────────────────────────────────────────

def pa_context(request, extra=None):
    """Inject common context for all platform admin views."""
    ctx = {
        'pending_users_count': TenantUser.objects.filter(
            approval_status='pending', is_staff=False,
        ).count(),
    }
    if extra:
        ctx.update(extra)
    return ctx


# ── Shared Pagination Helper ────────────────────────────────────────────────

def paginate(request, qs, per_page=25):
    """Paginate a queryset using the 'page' GET parameter."""
    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)
