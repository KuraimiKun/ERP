"""Approval queues + approve/reject actions for the admin mobile API.

Each endpoint delegates to the existing service / model method that
encodes the business rule so approval side-effects (journal entries,
audit logging, state-machine transitions) stay consistent with the web
API at ``/api/v1/``.
"""

from __future__ import annotations

import logging

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from erp.api.admin_mobile.base import AdminMobileReadOnlyViewSet
from erp.api.admin_mobile.serializers import (
    ExpenseMobileListSerializer,
    LeaveRequestMobileListSerializer,
    PurchaseOrderMobileListSerializer,
    QuoteMobileListSerializer,
    SupplierInvoiceMobileListSerializer,
)

logger = logging.getLogger("erp.api.admin_mobile")


def _log_admin_action(name: str, user, obj):
    logger.info(
        "Admin mobile %s",
        name,
        extra={
            "admin_action": name,
            "user_id": getattr(user, "pk", None),
            "object_id": getattr(obj, "pk", None),
            "object_type": type(obj).__name__,
        },
    )


# ---------------------------------------------------------------------------
# Leaves
# ---------------------------------------------------------------------------


class PendingLeavesViewSet(AdminMobileReadOnlyViewSet):
    """List + approve/reject pending leave requests."""

    serializer_class = LeaveRequestMobileListSerializer
    filterset_fields = ["employee", "leave_type"]
    ordering_fields = ["start_date", "created_at"]
    ordering = ["-created_at"]

    @extend_schema(tags=["admin-mobile"], summary="List pending leave requests")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        from erp.models import LeaveRequest

        company = self.get_company()
        qs = LeaveRequest.objects.select_related("employee", "leave_type").filter(
            status="pending",
        )
        if company:
            qs = qs.filter(employee__company=company)
        return qs

    @extend_schema(tags=["admin-mobile"], summary="Approve a leave request")
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        leave = self.get_object()
        if leave.status != "pending":
            return Response({"detail": "Can only approve pending requests."}, status=400)
        leave.status = "approved"
        employee = getattr(request.user, "employee_profile", None)
        if employee is not None:
            leave.approved_by = employee
        leave.approval_date = timezone.now()
        leave.approval_notes = request.data.get("notes") or ""
        leave.save()
        _log_admin_action("leave_approve", request.user, leave)
        return Response(LeaveRequestMobileListSerializer(leave).data)

    @extend_schema(tags=["admin-mobile"], summary="Reject a leave request")
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        leave = self.get_object()
        if leave.status != "pending":
            return Response({"detail": "Can only reject pending requests."}, status=400)
        leave.status = "rejected"
        leave.approval_notes = request.data.get("reason") or ""
        leave.save()
        _log_admin_action("leave_reject", request.user, leave)
        return Response(LeaveRequestMobileListSerializer(leave).data)


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


class PendingExpensesViewSet(AdminMobileReadOnlyViewSet):
    """List + approve/reject pending expenses.

    Approval delegates to ``erp.services.accounting.create_expense_journal_entry``
    so the double-entry posting stays aligned with ``/api/v1/expenses/``.
    """

    serializer_class = ExpenseMobileListSerializer
    filterset_fields = ["category", "employee"]
    ordering_fields = ["expense_date", "total_amount"]
    ordering = ["-expense_date"]

    def get_queryset(self):
        from erp.models import Expense

        company = self.get_company()
        qs = Expense.objects.select_related("category", "employee").filter(
            status__in=["submitted", "draft"],
        )
        if company:
            qs = qs.filter(company=company)
        return qs

    @extend_schema(tags=["admin-mobile"], summary="Approve an expense (posts journal entry)")
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        expense = self.get_object()
        if expense.status not in ("submitted", "draft"):
            return Response(
                {"detail": "Can only approve submitted/draft expenses."},
                status=400,
            )

        expense.status = "approved"
        employee = getattr(request.user, "employee_profile", None)
        if employee is not None:
            expense.approved_by = employee
        expense.approval_date = timezone.now()
        expense.save()

        # Post journal entry via the existing service. Failures are logged
        # but do NOT roll back the approval — matching the /api/v1 behaviour
        # in erp/api/views.py which wraps the call in try/except.
        try:
            from erp.services.accounting import create_expense_journal_entry

            create_expense_journal_entry(expense, request.user)
        except Exception:
            logger.exception("create_expense_journal_entry failed for expense %s", expense.pk)

        _log_admin_action("expense_approve", request.user, expense)
        return Response(ExpenseMobileListSerializer(expense).data)

    @extend_schema(tags=["admin-mobile"], summary="Reject an expense")
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        expense = self.get_object()
        if expense.status not in ("submitted", "draft"):
            return Response(
                {"detail": "Can only reject submitted/draft expenses."},
                status=400,
            )
        expense.status = "rejected"
        expense.save()
        _log_admin_action("expense_reject", request.user, expense)
        return Response(ExpenseMobileListSerializer(expense).data)


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


class PendingPurchaseOrdersViewSet(AdminMobileReadOnlyViewSet):
    serializer_class = PurchaseOrderMobileListSerializer
    filterset_fields = ["supplier"]
    ordering = ["-po_date"]

    def get_queryset(self):
        from erp.models import PurchaseOrder

        company = self.get_company()
        qs = PurchaseOrder.objects.select_related("supplier").filter(
            status__in=["draft", "pending"],
        )
        if company:
            qs = qs.filter(company=company)
        return qs

    @extend_schema(tags=["admin-mobile"], summary="Approve a purchase order")
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        po = self.get_object()
        if po.status not in ("draft", "pending"):
            return Response({"detail": "Can only approve draft or pending POs."}, status=400)
        po.status = "approved"
        employee = getattr(request.user, "employee_profile", None)
        if employee is not None:
            po.approved_by = employee
        po.approval_date = timezone.now()
        po.save()
        _log_admin_action("po_approve", request.user, po)
        return Response(PurchaseOrderMobileListSerializer(po).data)

    @extend_schema(tags=["admin-mobile"], summary="Reject (cancel) a purchase order")
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        po = self.get_object()
        if po.status not in ("draft", "pending"):
            return Response({"detail": "Can only reject draft or pending POs."}, status=400)
        po.status = "cancelled"
        po.save()
        _log_admin_action("po_reject", request.user, po)
        return Response(PurchaseOrderMobileListSerializer(po).data)


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


class PendingQuotesViewSet(AdminMobileReadOnlyViewSet):
    serializer_class = QuoteMobileListSerializer
    filterset_fields = ["customer"]
    ordering = ["-quote_date"]

    def get_queryset(self):
        from erp.models import Quote

        company = self.get_company()
        qs = Quote.objects.select_related("customer").filter(
            status__in=["draft", "sent", "viewed"],
        )
        if company:
            qs = qs.filter(company=company)
        return qs

    @extend_schema(tags=["admin-mobile"], summary="Mark a quote as accepted")
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        quote = self.get_object()
        if quote.status in ("accepted", "rejected", "expired"):
            return Response({"detail": f"Quote already {quote.status}."}, status=400)
        quote.status = "accepted"
        quote.save()
        _log_admin_action("quote_accept", request.user, quote)
        return Response(QuoteMobileListSerializer(quote).data)

    @extend_schema(tags=["admin-mobile"], summary="Mark a quote as rejected")
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        quote = self.get_object()
        if quote.status in ("accepted", "rejected", "expired"):
            return Response({"detail": f"Quote already {quote.status}."}, status=400)
        quote.status = "rejected"
        quote.save()
        _log_admin_action("quote_reject", request.user, quote)
        return Response(QuoteMobileListSerializer(quote).data)


# ---------------------------------------------------------------------------
# Supplier invoices
# ---------------------------------------------------------------------------


class PendingSupplierInvoicesViewSet(AdminMobileReadOnlyViewSet):
    serializer_class = SupplierInvoiceMobileListSerializer
    filterset_fields = ["supplier"]
    ordering = ["-invoice_date"]

    def get_queryset(self):
        from erp.models import SupplierInvoice

        company = self.get_company()
        qs = SupplierInvoice.objects.select_related("supplier").filter(
            status__in=["draft", "pending"],
        )
        if company:
            qs = qs.filter(company=company)
        return qs

    @extend_schema(tags=["admin-mobile"], summary="Approve a supplier invoice (posts journal entry)")
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status not in ("draft", "pending"):
            return Response({"detail": "Can only approve draft or pending invoices."}, status=400)
        invoice.status = "approved"
        invoice.save()

        try:
            from erp.services.accounting import create_supplier_invoice_journal_entry

            create_supplier_invoice_journal_entry(invoice, request.user)
        except Exception:
            logger.exception(
                "create_supplier_invoice_journal_entry failed for supplier invoice %s",
                invoice.pk,
            )

        _log_admin_action("supplier_invoice_approve", request.user, invoice)
        return Response(SupplierInvoiceMobileListSerializer(invoice).data)

    @extend_schema(tags=["admin-mobile"], summary="Reject a supplier invoice")
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status not in ("draft", "pending"):
            return Response({"detail": "Can only reject draft or pending invoices."}, status=400)
        invoice.status = "cancelled"
        invoice.save()
        _log_admin_action("supplier_invoice_reject", request.user, invoice)
        return Response(SupplierInvoiceMobileListSerializer(invoice).data)
