"""JSON report endpoints for the admin mobile API.

Financial reports are **thin wrappers** around
``erp.services.financial_reports`` (the same module powering
``/api/finance/reports/*``).  Sales/aging/top-N reports use simple
aggregations — no duplicate business logic.
"""

from __future__ import annotations

from datetime import date as _date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from erp.api.admin_mobile.helpers import resolve_admin_company
from erp.api.permissions import DefaultDbTokenAuthentication, IsCompanyAdmin
from erp.services import financial_reports as reports

ZERO = Decimal('0')


def _parse_iso_date(value: str, field: str) -> _date:
    try:
        return _date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field: f'Invalid ISO date: {value!r}'}) from exc


def _get_company(request):
    company = resolve_admin_company(request.user)
    if company is None:
        raise ValidationError({'detail': 'No company found for this user.'})
    return company


def _resolve_period(request: Request, company) -> tuple[_date, _date]:
    start_raw = request.query_params.get('start')
    end_raw = request.query_params.get('end')
    if start_raw or end_raw:
        if not (start_raw and end_raw):
            raise ValidationError({'detail': 'Both start and end are required when one is provided.'})
        start = _parse_iso_date(start_raw, 'start')
        end = _parse_iso_date(end_raw, 'end')
        if start > end:
            raise ValidationError({'start': 'start must be on or before end'})
        return start, end
    from erp.models import FiscalYear
    today = _date.today()
    fy = FiscalYear.objects.filter(company=company, is_current=True).first()
    if fy:
        return fy.start_date, fy.end_date
    return today.replace(month=1, day=1), today


def _resolve_as_of(request: Request, company) -> _date:
    raw = request.query_params.get('as_of')
    if raw:
        return _parse_iso_date(raw, 'as_of')
    _, end = _resolve_period(request, company)
    return end


def _serialize_decimal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    return value


def _serialize(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _serialize(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [_serialize(v) for v in node]
    return _serialize_decimal(node)


class _AdminReportView(APIView):
    authentication_classes = [DefaultDbTokenAuthentication]
    permission_classes = [IsAuthenticated, IsCompanyAdmin]


# ---------------------------------------------------------------------------
# Financial reports — wrappers
# ---------------------------------------------------------------------------


@extend_schema(
    tags=['admin-mobile'],
    summary='Trial Balance',
    parameters=[
        OpenApiParameter('start', str, description='ISO date (YYYY-MM-DD)'),
        OpenApiParameter('end', str, description='ISO date (YYYY-MM-DD)'),
    ],
)
class TrialBalanceView(_AdminReportView):
    def get(self, request):
        company = _get_company(request)
        start, end = _resolve_period(request, company)
        return Response(_serialize(reports.trial_balance(company, start, end)))


@extend_schema(
    tags=['admin-mobile'],
    summary='Profit & Loss',
    parameters=[
        OpenApiParameter('start', str), OpenApiParameter('end', str),
    ],
)
class ProfitAndLossView(_AdminReportView):
    def get(self, request):
        company = _get_company(request)
        start, end = _resolve_period(request, company)
        return Response(_serialize(reports.profit_and_loss(company, start, end)))


@extend_schema(
    tags=['admin-mobile'],
    summary='Balance Sheet',
    parameters=[OpenApiParameter('as_of', str)],
)
class BalanceSheetView(_AdminReportView):
    def get(self, request):
        company = _get_company(request)
        as_of = _resolve_as_of(request, company)
        return Response(_serialize(reports.balance_sheet(company, as_of)))


@extend_schema(
    tags=['admin-mobile'],
    summary='Cash Flow',
    parameters=[OpenApiParameter('start', str), OpenApiParameter('end', str)],
)
class CashFlowView(_AdminReportView):
    def get(self, request):
        company = _get_company(request)
        start, end = _resolve_period(request, company)
        return Response(_serialize(reports.cash_flow(company, start, end)))


# ---------------------------------------------------------------------------
# Operational reports (aggregations)
# ---------------------------------------------------------------------------


def _period_window(period: str) -> tuple[_date, _date]:
    today = _date.today()
    if period == 'day':
        return today, today
    if period == 'week':
        return today - timedelta(days=7), today
    if period == 'month':
        return today.replace(day=1), today
    if period == 'year':
        return today.replace(month=1, day=1), today
    raise ValidationError({'period': f'must be one of day|week|month|year, got {period!r}'})


@extend_schema(
    tags=['admin-mobile'],
    summary='Sales summary (revenue + count) over a window',
    parameters=[OpenApiParameter('period', str, description='day | week | month | year')],
)
class SalesSummaryView(_AdminReportView):
    def get(self, request):
        from erp.models import Invoice
        company = _get_company(request)
        period = request.query_params.get('period', 'month')
        start, end = _period_window(period)
        agg = (
            Invoice.objects
            .filter(company=company, invoice_date__gte=start, invoice_date__lte=end)
            .aggregate(
                revenue=Coalesce(Sum('total_amount'), ZERO),
                paid=Coalesce(Sum('paid_amount'), ZERO),
                outstanding=Coalesce(Sum('balance_due'), ZERO),
                count=Count('id'),
            )
        )
        return Response({
            'period': period,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'revenue': _serialize_decimal(agg['revenue']),
            'paid': _serialize_decimal(agg['paid']),
            'outstanding': _serialize_decimal(agg['outstanding']),
            'count': agg['count'],
        })


@extend_schema(
    tags=['admin-mobile'],
    summary='Top products by revenue',
    parameters=[OpenApiParameter('period', str), OpenApiParameter('limit', int)],
)
class TopProductsView(_AdminReportView):
    def get(self, request):
        from erp.models import POSOrderLine
        company = _get_company(request)
        period = request.query_params.get('period', 'month')
        start, end = _period_window(period)
        limit = max(1, min(int(request.query_params.get('limit') or 10), 50))
        qs = (
            POSOrderLine.objects
            .filter(order__company=company, order__created_at__date__gte=start,
                    order__created_at__date__lte=end)
            .values('product')
            .annotate(
                product_name=F('product__name'),
                quantity=Coalesce(Sum('quantity'), ZERO),
                revenue=Coalesce(Sum('line_total'), ZERO),
            )
            .order_by('-revenue')[:limit]
        )
        return Response({
            'period': period,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'results': [
                {
                    'product': row['product'],
                    'product_name': row['product_name'],
                    'quantity': _serialize_decimal(row['quantity']),
                    'revenue': _serialize_decimal(row['revenue']),
                }
                for row in qs
            ],
        })


@extend_schema(
    tags=['admin-mobile'],
    summary='Top customers by revenue',
    parameters=[OpenApiParameter('period', str), OpenApiParameter('limit', int)],
)
class TopCustomersView(_AdminReportView):
    def get(self, request):
        from erp.models import Invoice
        company = _get_company(request)
        period = request.query_params.get('period', 'month')
        start, end = _period_window(period)
        limit = max(1, min(int(request.query_params.get('limit') or 10), 50))
        qs = (
            Invoice.objects
            .filter(company=company, invoice_date__gte=start, invoice_date__lte=end)
            .values('customer')
            .annotate(
                customer_name=F('customer__name'),
                revenue=Coalesce(Sum('total_amount'), ZERO),
                invoices=Count('id'),
            )
            .order_by('-revenue')[:limit]
        )
        return Response({
            'period': period,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'results': [
                {
                    'customer': row['customer'],
                    'customer_name': row['customer_name'],
                    'revenue': _serialize_decimal(row['revenue']),
                    'invoices': row['invoices'],
                }
                for row in qs
            ],
        })


def _aging_buckets(qs, date_field: str) -> dict:
    """Aging buckets: 0-30, 31-60, 61-90, 90+ days overdue."""
    today = _date.today()
    out = {'0-30': ZERO, '31-60': ZERO, '61-90': ZERO, '90+': ZERO, 'total': ZERO}
    for obj in qs:
        amount = getattr(obj, 'balance_due', ZERO) or ZERO
        if amount <= 0:
            continue
        ref = getattr(obj, date_field, None) or today
        days = (today - ref).days
        if days <= 30:
            out['0-30'] += amount
        elif days <= 60:
            out['31-60'] += amount
        elif days <= 90:
            out['61-90'] += amount
        else:
            out['90+'] += amount
        out['total'] += amount
    return {k: _serialize_decimal(v) for k, v in out.items()}


@extend_schema(tags=['admin-mobile'], summary='Aging receivables (customer invoices)')
class AgingReceivablesView(_AdminReportView):
    def get(self, request):
        from erp.models import Invoice
        company = _get_company(request)
        qs = Invoice.objects.filter(company=company, balance_due__gt=0)
        return Response(_aging_buckets(qs, 'due_date'))


@extend_schema(tags=['admin-mobile'], summary='Aging payables (supplier invoices)')
class AgingPayablesView(_AdminReportView):
    def get(self, request):
        from erp.models import SupplierInvoice
        company = _get_company(request)
        qs = SupplierInvoice.objects.filter(company=company, balance_due__gt=0)
        return Response(_aging_buckets(qs, 'due_date'))
