"""
Financial Reports JSON API.

Exposes the four standard accounting statements (Trial Balance, P&L,
Balance Sheet, Cash Flow) as JSON endpoints under
``/api/finance/reports/``.

All endpoints:
 * require an authenticated user with an ``employee_profile`` linked to a
   company (same permission class used by the rest of the ERP API)
 * compute numbers for *that* user's company only — no cross-tenant access
 * accept ``start`` / ``end`` / ``as_of`` query parameters in ISO ``YYYY-MM-DD``
   form and fall back to the current fiscal year (or calendar year if none).

The response shape mirrors the dicts returned by ``erp.services.financial_reports``
so that the API and the HTML reports stay in sync.
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from erp.models import FiscalYear
from erp.services import financial_reports as reports

from .permissions import IsCompanyUser


def _get_user_company(request: Request):
    """Return the request user's company or raise 403 — mirrors ``ERPBaseViewSet``."""
    user = request.user
    if hasattr(user, "employee_profile") and user.employee_profile:
        return user.employee_profile.company
    raise PermissionDenied("No employee profile found for this user.")


def _parse_iso_date(raw: str, field: str) -> _date:
    try:
        return _date.fromisoformat(raw)
    except (TypeError, ValueError):
        raise ValidationError({field: f"Invalid date; expected YYYY-MM-DD, got {raw!r}"})


def _resolve_period(request: Request, company) -> tuple[_date, _date]:
    """Resolve (start, end) from ``?start=&end=`` or current fiscal year."""
    start_raw = request.query_params.get("start")
    end_raw = request.query_params.get("end")
    if start_raw and end_raw:
        start = _parse_iso_date(start_raw, "start")
        end = _parse_iso_date(end_raw, "end")
        if start > end:
            raise ValidationError({"start": "start must be on or before end"})
        return start, end

    today = _date.today()
    fy = FiscalYear.objects.filter(company=company, is_current=True).first()
    if fy:
        return fy.start_date, fy.end_date
    return today.replace(month=1, day=1), today


def _resolve_as_of(request: Request, company) -> _date:
    raw = request.query_params.get("as_of")
    if raw:
        return _parse_iso_date(raw, "as_of")
    # Fall back to the end of the current period.
    _, end = _resolve_period(request, company)
    return end


# ── Serialization helpers ──────────────────────────────────────────────────


def _serialize_decimal(value: Any) -> Any:
    """Ensure Decimal round-trips cleanly through the default JSON encoder."""
    if isinstance(value, Decimal):
        # Normalise trailing zeros without mutating precision of large values.
        return str(value)
    return value


def _serialize(node: Any) -> Any:
    """Recursively convert Decimals / nested dicts & lists for JSON output."""
    if isinstance(node, dict):
        return {k: _serialize(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_serialize(v) for v in node]
    return _serialize_decimal(node)


# ── Query parameter serializers (for schema/docs) ──────────────────────────


class _PeriodQuerySerializer(serializers.Serializer):
    """Documents the accepted query parameters for period-based reports."""

    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)


class _AsOfQuerySerializer(serializers.Serializer):
    as_of = serializers.DateField(required=False)


# ── API endpoints ──────────────────────────────────────────────────────────


class _BaseReportView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]


class TrialBalanceAPIView(_BaseReportView):
    """GET /api/finance/reports/trial-balance/?start=&end= — Trial Balance."""

    def get(self, request: Request):
        company = _get_user_company(request)
        start, end = _resolve_period(request, company)
        data = reports.trial_balance(company, start, end)
        return Response(_serialize(data))


class ProfitAndLossAPIView(_BaseReportView):
    """GET /api/finance/reports/profit-and-loss/?start=&end= — P&L."""

    def get(self, request: Request):
        company = _get_user_company(request)
        start, end = _resolve_period(request, company)
        data = reports.profit_and_loss(company, start, end)
        return Response(_serialize(data))


class BalanceSheetAPIView(_BaseReportView):
    """GET /api/finance/reports/balance-sheet/?as_of= — Balance Sheet."""

    def get(self, request: Request):
        company = _get_user_company(request)
        as_of = _resolve_as_of(request, company)
        data = reports.balance_sheet(company, as_of)
        return Response(_serialize(data))


class CashFlowAPIView(_BaseReportView):
    """GET /api/finance/reports/cash-flow/?start=&end= — Cash Flow."""

    def get(self, request: Request):
        company = _get_user_company(request)
        start, end = _resolve_period(request, company)
        data = reports.cash_flow(company, start, end)
        return Response(_serialize(data))
