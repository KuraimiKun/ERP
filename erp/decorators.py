"""
Decorators for ERP Multi-Tenant System
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def tenant_required(view_func):
    """
    Decorator that checks if the user is authenticated, approved,
    and has an assigned database.

    Employees (role='user') are redirected to the employee portal
    when they try to access management views.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        # Check authentication
        if not user.is_authenticated:
            return redirect('tenants:login')

        # Staff/superusers bypass tenant checks
        if user.is_staff or user.is_superuser:
            return view_func(request, *args, **kwargs)

        # Check approval status
        if not getattr(user, 'is_approved', False):
            status = getattr(user, 'approval_status', 'pending')
            if status == 'pending':
                return redirect('tenants:pending_approval')
            elif status == 'rejected':
                return redirect('tenants:rejected')
            elif status == 'suspended':
                messages.error(request, 'Your account has been suspended.')
                return redirect('tenants:logout')

        # Check database assignment
        if not getattr(user, 'assigned_database', None):
            return redirect('tenants:no_database')

        # Check role – employees (role='user') go to their portal
        assignment = user.database_assignments.filter(is_active=True).first()
        if assignment and assignment.role == 'user':
            from django.urls import resolve
            # Avoid redirect loop: if we're already on a portal URL, proceed
            if hasattr(request, 'resolver_match') and request.resolver_match:
                url_name = request.resolver_match.url_name or ''
                if url_name.startswith('employee_portal'):
                    return view_func(request, *args, **kwargs)
            return redirect('erp:employee_portal')

        return view_func(request, *args, **kwargs)

    return wrapper


def employee_or_owner_required(view_func):
    """
    Like tenant_required but allows employees (role='user') as well.

    Use this for employee-portal views that both employees AND
    owners/admins should be able to access.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return redirect('tenants:login')

        if user.is_staff or user.is_superuser:
            return view_func(request, *args, **kwargs)

        if not getattr(user, 'is_approved', False):
            status = getattr(user, 'approval_status', 'pending')
            if status == 'pending':
                return redirect('tenants:pending_approval')
            elif status == 'rejected':
                return redirect('tenants:rejected')
            elif status == 'suspended':
                messages.error(request, 'Your account has been suspended.')
                return redirect('tenants:logout')

        if not getattr(user, 'assigned_database', None):
            return redirect('tenants:no_database')

        return view_func(request, *args, **kwargs)

    return wrapper


def erp_login_required(view_func):
    """
    Combined decorator for ERP views.
    Requires user to be authenticated and have tenant access.
    """
    @wraps(view_func)
    @login_required
    @tenant_required
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)

    return wrapper
