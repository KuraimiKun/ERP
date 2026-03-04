"""
ERP Views – Shared utilities

Provides get_user_company(), paginate_qs() and the common decorator alias
used by every view module in this package.
"""

from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse

from erp.models import Company
from erp.decorators import tenant_required as staff_member_required

DEFAULT_PAGE_SIZE = 25


def get_user_company(user):
    """Get the company associated with the current user."""
    try:
        if hasattr(user, 'employee_profile') and user.employee_profile:
            return user.employee_profile.company
    except Exception:
        pass
    return Company.objects.first()


def paginate_qs(request, queryset, per_page=DEFAULT_PAGE_SIZE):
    """Paginate *queryset* and return ``(page_obj, query_string)``.

    ``query_string`` contains every GET parameter **except** ``page`` so
    the reusable pagination template can append ``&page=N`` cleanly.
    """
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Build a query-string that keeps existing filters but strips 'page'
    params = request.GET.copy()
    params.pop('page', None)
    query_string = params.urlencode()

    return page_obj, query_string
