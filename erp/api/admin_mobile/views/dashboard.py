"""Dashboard, activity, and KPI endpoints for the admin mobile API."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from erp.api.permissions import DefaultDbTokenAuthentication, IsCompanyAdmin
from erp.api.admin_mobile.serializers import AuditLogMobileSerializer
from erp.api.admin_mobile.helpers import resolve_admin_company

ZERO = Decimal('0')


def _get_company(user):
    """Return the authenticated admin's company, or None."""
    return resolve_admin_company(user)


def _dec(v):
    return str(v) if isinstance(v, Decimal) else v


# ---------------------------------------------------------------------------
# GET /dashboard/
# ---------------------------------------------------------------------------


@extend_schema(
    tags=['admin-mobile'],
    summary='Home-screen dashboard summary',
    description=(
        'One call returning: today revenue, cash in hand, pending approval '
        'counts, low-stock items, open POS sessions, overdue invoice total, '
        'this-month P&L summary. 5-minute cache keyed by company.'
    ),
    responses={200: inline_serializer(
        name='AdminDashboardResponse',
        fields={
            'today_revenue': serializers.CharField(),
            'cash_in_hand': serializers.CharField(),
            'pending_leave_approvals': serializers.IntegerField(),
            'pending_expense_approvals': serializers.IntegerField(),
            'pending_po_approvals': serializers.IntegerField(),
            'low_stock_items': serializers.IntegerField(),
            'open_pos_sessions': serializers.IntegerField(),
            'overdue_invoices_amount': serializers.CharField(),
            'this_month_revenue': serializers.CharField(),
            'this_month_expenses': serializers.CharField(),
        },
    )},
)
@api_view(['GET'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def dashboard_summary(request):
    company = _get_company(request.user)
    if company is None:
        # Superusers without a company context get an empty shell rather
        # than a 500.
        return Response({
            'today_revenue': '0',
            'cash_in_hand': '0',
            'pending_leave_approvals': 0,
            'pending_expense_approvals': 0,
            'pending_po_approvals': 0,
            'low_stock_items': 0,
            'open_pos_sessions': 0,
            'overdue_invoices_amount': '0',
            'this_month_revenue': '0',
            'this_month_expenses': '0',
        })

    cache_key = f'adminmobile:dashboard:{company.pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    today = timezone.localdate()
    month_start = today.replace(day=1)

    # Imports are local to keep this module importable even if optional
    # sub-modules change.
    from erp.models import (
        Expense,
        Invoice,
        LeaveRequest,
        POSSession,
        Payment,
        Product,
        PurchaseOrder,
    )

    today_revenue = (
        Invoice.objects
        .filter(company=company, invoice_date=today)
        .aggregate(t=Coalesce(Sum('total_amount'), ZERO))['t']
    )
    cash_in_hand = (
        Payment.objects
        .filter(company=company, payment_date=today)
        .aggregate(t=Coalesce(Sum('amount'), ZERO))['t']
    )
    pending_leaves = LeaveRequest.objects.filter(
        employee__company=company, status='pending',
    ).count()
    pending_expenses = Expense.objects.filter(
        company=company, status__in=['submitted', 'draft'],
    ).count()
    pending_pos = PurchaseOrder.objects.filter(
        company=company, status__in=['draft', 'pending'],
    ).count()
    low_stock = Product.objects.filter(
        company=company, track_inventory=True,
        quantity_on_hand__lte=F('reorder_level'),
    ).count()
    open_sessions = POSSession.objects.filter(
        company=company, status='open',
    ).count()
    overdue = (
        Invoice.objects
        .filter(company=company, due_date__lt=today, balance_due__gt=0)
        .aggregate(t=Coalesce(Sum('balance_due'), ZERO))['t']
    )
    month_revenue = (
        Invoice.objects
        .filter(company=company, invoice_date__gte=month_start, invoice_date__lte=today)
        .aggregate(t=Coalesce(Sum('total_amount'), ZERO))['t']
    )
    month_expenses = (
        Expense.objects
        .filter(company=company, expense_date__gte=month_start, expense_date__lte=today)
        .aggregate(t=Coalesce(Sum('total_amount'), ZERO))['t']
    )

    payload = {
        'today_revenue': _dec(today_revenue),
        'cash_in_hand': _dec(cash_in_hand),
        'pending_leave_approvals': pending_leaves,
        'pending_expense_approvals': pending_expenses,
        'pending_po_approvals': pending_pos,
        'low_stock_items': low_stock,
        'open_pos_sessions': open_sessions,
        'overdue_invoices_amount': _dec(overdue),
        'this_month_revenue': _dec(month_revenue),
        'this_month_expenses': _dec(month_expenses),
    }
    cache.set(cache_key, payload, timeout=60 * 5)
    return Response(payload)


# ---------------------------------------------------------------------------
# GET /dashboard/activity/
# ---------------------------------------------------------------------------


@extend_schema(
    tags=['admin-mobile'],
    summary='Recent audit log entries (last 50)',
    responses={200: AuditLogMobileSerializer(many=True)},
)
@api_view(['GET'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def dashboard_activity(request):
    from erp.models import AuditLog

    qs = AuditLog.objects.select_related('user', 'content_type').order_by('-created_at')[:50]
    data = AuditLogMobileSerializer(qs, many=True).data
    return Response(data)


# ---------------------------------------------------------------------------
# GET /dashboard/kpis/
# ---------------------------------------------------------------------------


@extend_schema(
    tags=['admin-mobile'],
    summary='Cross-module KPI snapshot',
    description=(
        'Rolling 30-day KPIs: revenue, expenses, new customers, new leads, '
        'invoices-issued, payments-received. Intended for the Flutter home '
        'screen KPI strip.'
    ),
    responses={200: inline_serializer(
        name='AdminKPIResponse',
        fields={
            'period_days': serializers.IntegerField(),
            'revenue': serializers.CharField(),
            'expenses': serializers.CharField(),
            'net': serializers.CharField(),
            'new_customers': serializers.IntegerField(),
            'new_leads': serializers.IntegerField(),
            'invoices_issued': serializers.IntegerField(),
            'payments_received': serializers.CharField(),
        },
    )},
)
@api_view(['GET'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def dashboard_kpis(request):
    company = _get_company(request.user)
    if company is None:
        return Response({
            'period_days': 30,
            'revenue': '0', 'expenses': '0', 'net': '0',
            'new_customers': 0, 'new_leads': 0,
            'invoices_issued': 0, 'payments_received': '0',
        })

    today = timezone.localdate()
    start = today - timedelta(days=30)

    from erp.models import Customer, Expense, Invoice, Lead, Payment

    rev = (Invoice.objects
           .filter(company=company, invoice_date__gte=start, invoice_date__lte=today)
           .aggregate(t=Coalesce(Sum('total_amount'), ZERO), n=Count('id')))
    exp = (Expense.objects
           .filter(company=company, expense_date__gte=start, expense_date__lte=today)
           .aggregate(t=Coalesce(Sum('total_amount'), ZERO)))
    new_customers = Customer.objects.filter(
        company=company, created_at__date__gte=start,
    ).count()
    new_leads = Lead.objects.filter(
        company=company, created_at__date__gte=start,
    ).count()
    payments = (Payment.objects
                .filter(company=company, payment_date__gte=start, payment_date__lte=today)
                .aggregate(t=Coalesce(Sum('amount'), ZERO))['t'])

    net = rev['t'] - exp['t']
    return Response({
        'period_days': 30,
        'revenue': _dec(rev['t']),
        'expenses': _dec(exp['t']),
        'net': _dec(net),
        'new_customers': new_customers,
        'new_leads': new_leads,
        'invoices_issued': rev['n'],
        'payments_received': _dec(payments),
    })
