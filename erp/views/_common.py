"""
ERP Views – Shared utilities

Provides get_user_company(), paginate_qs() and the common decorator alias
used by every view module in this package.
"""

from django.contrib import messages  # noqa: F401
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render  # noqa: F401
from django.urls import reverse  # noqa: F401

from erp.decorators import tenant_required as staff_member_required  # noqa: F401

from django.core.exceptions import PermissionDenied

from erp.models import Company

DEFAULT_PAGE_SIZE = 25


def get_user_company(user):
    """Get the company associated with the current user.

    Checks (in order):
      1. Employee profile linked to the user
      2. Company created by the user (owner / admin)

    Raises PermissionDenied if no company can be resolved — never
    falls back to an arbitrary company.
    """
    try:
        if hasattr(user, 'employee_profile') and user.employee_profile:
            return user.employee_profile.company
    except Exception:
        pass

    # Fallback: the user may be the company owner / admin who created it
    company = Company.objects.filter(created_by=user).first()
    if company:
        return company

    raise PermissionDenied(
        'No company is associated with your account. '
        'Please contact your administrator.'
    )


def paginate_qs(request, queryset, per_page=DEFAULT_PAGE_SIZE):
    """Paginate *queryset* and return ``(page_obj, query_string)``.

    ``query_string`` contains every GET parameter **except** ``page`` so
    the reusable pagination template can append ``&page=N`` cleanly.
    """
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Build a query-string that keeps existing filters but strips 'page',
    # 'sort', and 'order' (sort headers rebuild these themselves).
    params = request.GET.copy()
    for key in ('page', 'sort', 'order'):
        params.pop(key, None)
    query_string = params.urlencode()

    return page_obj, query_string


def apply_sorting(request, queryset, allowed_fields, default='-created_at'):
    """Apply user-requested sorting to *queryset* safely.

    Reads ``sort`` (field name) and ``order`` (``asc`` / ``desc``) from
    ``request.GET``.  Only fields listed in *allowed_fields* are accepted;
    anything else falls back to *default*.

    Returns ``(sorted_queryset, current_sort, current_order)`` so that
    templates can render active-sort indicators.
    """
    sort = request.GET.get('sort', '').strip()
    order = request.GET.get('order', 'asc').strip().lower()

    if sort in allowed_fields:
        current_sort = sort
    else:
        # Parse the default to extract sort/order
        if default.startswith('-'):
            current_sort = default[1:]
            order = 'desc'
        else:
            current_sort = default
            order = 'asc'

    current_order = 'desc' if order == 'desc' else 'asc'
    order_field = f'-{current_sort}' if current_order == 'desc' else current_sort
    return queryset.order_by(order_field), current_sort, current_order
