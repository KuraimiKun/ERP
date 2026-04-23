"""Helpers shared across admin-mobile views.

Specifically, a single function that resolves the authenticated admin's
:class:`erp.models.Employee` record whether or not the reverse
``user.employee_profile`` accessor is populated.

Some admins are created without ``Employee.user_id`` being back-filled
(e.g. when the admin user was created first and the Employee row later).
Relying solely on ``user.employee_profile`` yielded 403s across the
admin-mobile API after login.  This helper mirrors the fallback already
used by the login view and optionally back-fills the FK so subsequent
requests hit the fast path.
"""

from __future__ import annotations

from typing import Optional

from django.db import transaction


def resolve_admin_employee(user, *, backfill: bool = True):
    """Return the Employee for ``user`` or ``None``.

    Preference order:

    1. ``user.employee_profile`` (reverse OneToOne; zero queries after
       the standard Django caching).
    2. ``Employee.objects.filter(email=user.email).first()`` — the same
       fallback the login view uses.

    When the fallback finds a match and ``backfill`` is True, the
    Employee's ``user`` FK is persisted so the next request resolves
    through the reverse accessor and ``IsCompanyAdmin`` stops hitting
    the fallback.
    """
    employee = getattr(user, 'employee_profile', None)
    if employee is not None:
        return employee

    email = (getattr(user, 'email', '') or '').strip()
    if not email:
        return None

    # Local import keeps the module cheap to import (e.g. inside
    # permission classes that load at startup).
    from erp.models import Employee

    try:
        employee = (
            Employee.objects
            .filter(email__iexact=email)
            .order_by('-created_at')
            .first()
        )
    except Exception:
        employee = None

    if employee is None:
        return None

    if backfill and employee.user_id is None:
        try:
            with transaction.atomic(using=employee._state.db or 'default'):
                employee.user = user
                employee.save(update_fields=['user'])
        except Exception:
            # Non-fatal — we still have the Employee in hand for this
            # request; the next login attempt will try again.
            pass

    return employee


def resolve_admin_company(user) -> Optional[object]:
    """Return the admin's Company or ``None``.

    For owners/admins that do not have an Employee record on the tenant
    DB (common for the tenant creator), fall back to the first Company
    row on the active tenant database.  An ERP tenant database is
    provisioned with a single Company, so this is unambiguous.
    """
    employee = resolve_admin_employee(user)
    if employee is not None and employee.company_id is not None:
        return employee.company

    from erp.models import Company
    from tenants.routers import get_current_db_alias

    db_alias = get_current_db_alias()
    if db_alias == 'default':
        return None
    try:
        return Company.objects.using(db_alias).order_by('id').first()
    except Exception:
        return None
