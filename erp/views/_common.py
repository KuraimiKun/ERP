"""
ERP Views – Shared utilities

Provides get_user_company() and the common decorator alias used by every
view module in this package.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse

from erp.models import Company
from erp.decorators import tenant_required as staff_member_required


def get_user_company(user):
    """Get the company associated with the current user."""
    if hasattr(user, 'employee_profile') and user.employee_profile:
        return user.employee_profile.company
    return Company.objects.first()
