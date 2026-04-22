"""Master-data CRUD viewsets for the admin mobile API.

Each viewset is a thin, mobile-shaped wrapper over an existing
``erp.api.views`` ViewSet:

* lists use a lightweight serializer from ``admin_mobile.serializers``;
* detail / create / update reuse the richer v1 serializer unchanged;
* deletes are routed through ``ERPBaseModel.soft_delete`` via
  ``AdminMobileBaseViewSet.perform_destroy``.

Heavy business logic (journal entries, state machines, …) stays in
``erp.services`` — endpoints only orchestrate.
"""

from __future__ import annotations

import logging

from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from erp.api.admin_mobile.base import (
    AdminMobileBaseViewSet,
    AdminMobileReadOnlyViewSet,
)
from erp.api.admin_mobile.serializers import (
    AccountMobileSerializer,
    AttendanceMobileListSerializer,
    BranchMobileSerializer,
    CampaignMobileListSerializer,
    CustomerInteractionMobileSerializer,
    CustomerMobileListSerializer,
    DepartmentMobileSerializer,
    EmployeeMobileListSerializer,
    ExpenseMobileListSerializer,
    GoodsReceiptMobileListSerializer,
    InvoiceMobileListSerializer,
    LeadActivityMobileSerializer,
    LeadMobileListSerializer,
    LeaveRequestMobileListSerializer,
    PayrollMobileListSerializer,
    POSOrderMobileListSerializer,
    POSSessionMobileListSerializer,
    POSTerminalMobileSerializer,
    PaymentMobileListSerializer,
    ProductMobileListSerializer,
    ProductMobileSerializer,
    PurchaseOrderMobileListSerializer,
    QuoteMobileListSerializer,
    ServicePricingMobileSerializer,
    StockAdjustmentMobileListSerializer,
    StockItemMobileListSerializer,
    StockMovementMobileListSerializer,
    SupplierInvoiceMobileListSerializer,
    SupplierInvoiceMobileSerializer,
    SupplierMobileListSerializer,
    SupplierPaymentMobileListSerializer,
    SupplierPaymentMobileSerializer,
    TaskMobileListSerializer,
    TaxRateMobileSerializer,
    WarehouseMobileListSerializer,
)
from erp.api.serializers import (
    AttendanceSerializer,
    BranchSerializer,
    CampaignSerializer,
    CustomerInteractionSerializer,
    CustomerSerializer,
    DepartmentSerializer,
    EmployeeSerializer,
    ExpenseSerializer,
    InvoiceSerializer,
    LeadActivitySerializer,
    LeadSerializer,
    LeaveRequestSerializer,
    PaymentSerializer,
    PayrollSerializer,
    PurchaseOrderSerializer,
    QuoteSerializer,
    TaskSerializer,
)
from erp.api.inventory_serializers import (
    GoodsReceiptNoteSerializer,
    StockAdjustmentSerializer,
)
from erp.models import (
    Account,
    Attendance,
    Branch,
    Campaign,
    Customer,
    CustomerInteraction,
    Department,
    Employee,
    Expense,
    GoodsReceiptNote,
    Invoice,
    Lead,
    LeadActivity,
    LeaveRequest,
    POSOrder,
    POSSession,
    POSTerminal,
    Payment,
    Payroll,
    Product,
    PurchaseOrder,
    Quote,
    ServicePricing,
    StockAdjustment,
    StockItem,
    StockMovement,
    Supplier,
    SupplierInvoice,
    SupplierPayment,
    Task,
    TaxRate,
    Warehouse,
)

logger = logging.getLogger('erp.api.admin_mobile')


class _DualSerializerMixin:
    """Pick ``list_serializer_class`` on list, ``detail_serializer_class`` elsewhere."""

    list_serializer_class = None
    detail_serializer_class = None

    def get_serializer_class(self):
        if self.action == 'list' and self.list_serializer_class is not None:
            return self.list_serializer_class
        if self.detail_serializer_class is not None:
            return self.detail_serializer_class
        return super().get_serializer_class()


# ═══════════════════════════════════════════════════════════════════════════
# HR
# ═══════════════════════════════════════════════════════════════════════════


class EmployeeViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Employee.objects.select_related('department', 'branch')
    list_serializer_class = EmployeeMobileListSerializer
    detail_serializer_class = EmployeeSerializer
    search_fields = ['first_name', 'last_name', 'email', 'employee_id']
    filterset_fields = ['department', 'branch', 'employment_status']
    ordering_fields = ['first_name', 'last_name', 'created_at']
    ordering = ['first_name', 'last_name']


class DepartmentViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Department.objects.select_related('parent')
    list_serializer_class = DepartmentMobileSerializer
    detail_serializer_class = DepartmentSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['is_active', 'parent']
    ordering = ['name']


class BranchViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Branch.objects.all()
    list_serializer_class = BranchMobileSerializer
    detail_serializer_class = BranchSerializer
    search_fields = ['name', 'code', 'city']
    filterset_fields = ['is_active', 'is_headquarters']
    ordering = ['name']


class _EmployeeCompanyScopedMixin:
    """Scope querysets joining through ``employee.company`` rather than ``company``."""

    def get_queryset(self):
        qs = viewsets.ModelViewSet.get_queryset(self)
        company = self.get_company()
        if company:
            qs = qs.filter(employee__company=company)
        return qs


class AttendanceViewSet(_DualSerializerMixin, _EmployeeCompanyScopedMixin, AdminMobileBaseViewSet):
    queryset = Attendance.objects.select_related('employee')
    list_serializer_class = AttendanceMobileListSerializer
    detail_serializer_class = AttendanceSerializer
    filterset_fields = ['employee', 'date']
    ordering = ['-date']


class LeaveRequestViewSet(_DualSerializerMixin, _EmployeeCompanyScopedMixin, AdminMobileBaseViewSet):
    queryset = LeaveRequest.objects.select_related('employee', 'leave_type')
    list_serializer_class = LeaveRequestMobileListSerializer
    detail_serializer_class = LeaveRequestSerializer
    filterset_fields = ['employee', 'leave_type', 'status']
    ordering = ['-created_at']


class PayrollViewSet(_DualSerializerMixin, _EmployeeCompanyScopedMixin, AdminMobileBaseViewSet):
    queryset = Payroll.objects.select_related('employee')
    list_serializer_class = PayrollMobileListSerializer
    detail_serializer_class = PayrollSerializer
    filterset_fields = ['employee', 'status']
    ordering = ['-period_end']


# ═══════════════════════════════════════════════════════════════════════════
# Finance
# ═══════════════════════════════════════════════════════════════════════════


class CustomerViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Customer.objects.select_related('currency')
    list_serializer_class = CustomerMobileListSerializer
    detail_serializer_class = CustomerSerializer
    search_fields = ['name', 'email', 'customer_id', 'phone']
    filterset_fields = ['customer_type', 'is_active']
    ordering = ['name']


class InvoiceViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    """Invoice CRUD. Creation posts a journal entry via the service layer."""

    queryset = Invoice.objects.select_related('customer', 'currency').prefetch_related('lines')
    list_serializer_class = InvoiceMobileListSerializer
    detail_serializer_class = InvoiceSerializer
    search_fields = ['invoice_number', 'customer__name']
    filterset_fields = ['customer', 'status']
    ordering = ['-invoice_date']

    def perform_create(self, serializer):
        with transaction.atomic():
            obj = serializer.save(company=self.get_company())
        try:
            from erp.services.accounting import create_invoice_journal_entry
            create_invoice_journal_entry(obj, self.request.user)
        except Exception:
            logger.exception('create_invoice_journal_entry failed for invoice %s', obj.pk)


class PaymentViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Payment.objects.select_related('customer', 'payment_method')
    list_serializer_class = PaymentMobileListSerializer
    detail_serializer_class = PaymentSerializer
    search_fields = ['payment_number', 'customer__name']
    filterset_fields = ['customer', 'payment_method']
    ordering = ['-payment_date']

    def perform_create(self, serializer):
        with transaction.atomic():
            obj = serializer.save(company=self.get_company())
        try:
            from erp.services.accounting import create_payment_journal_entry
            create_payment_journal_entry(obj, self.request.user)
        except Exception:
            logger.exception('create_payment_journal_entry failed for payment %s', obj.pk)


class ExpenseViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Expense.objects.select_related('category', 'employee', 'approved_by')
    list_serializer_class = ExpenseMobileListSerializer
    detail_serializer_class = ExpenseSerializer
    search_fields = ['expense_number', 'description']
    filterset_fields = ['category', 'status', 'employee']
    ordering = ['-expense_date']


class AccountReadOnlyViewSet(AdminMobileReadOnlyViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountMobileSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['account_type', 'is_active']
    ordering = ['code']


class TaxRateReadOnlyViewSet(AdminMobileReadOnlyViewSet):
    queryset = TaxRate.objects.all()
    serializer_class = TaxRateMobileSerializer
    search_fields = ['name']
    filterset_fields = ['is_active']
    ordering = ['name']


# ═══════════════════════════════════════════════════════════════════════════
# Supplier
# ═══════════════════════════════════════════════════════════════════════════


class SupplierViewSet(AdminMobileBaseViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierMobileListSerializer
    search_fields = ['name', 'email', 'supplier_id']
    filterset_fields = ['is_active']
    ordering = ['name']


class PurchaseOrderViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = PurchaseOrder.objects.select_related('supplier', 'currency').prefetch_related('lines')
    list_serializer_class = PurchaseOrderMobileListSerializer
    detail_serializer_class = PurchaseOrderSerializer
    search_fields = ['po_number', 'supplier__name']
    filterset_fields = ['supplier', 'status']
    ordering = ['-po_date']


class SupplierInvoiceViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = SupplierInvoice.objects.select_related('supplier', 'currency')
    list_serializer_class = SupplierInvoiceMobileListSerializer
    detail_serializer_class = SupplierInvoiceMobileSerializer
    search_fields = ['invoice_number', 'supplier__name']
    filterset_fields = ['supplier', 'status']
    ordering = ['-invoice_date']


class SupplierPaymentViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = SupplierPayment.objects.select_related('supplier')
    list_serializer_class = SupplierPaymentMobileListSerializer
    detail_serializer_class = SupplierPaymentMobileSerializer
    search_fields = ['payment_number', 'supplier__name']
    filterset_fields = ['supplier']
    ordering = ['-payment_date']


# ═══════════════════════════════════════════════════════════════════════════
# Inventory
# ═══════════════════════════════════════════════════════════════════════════


class WarehouseViewSet(AdminMobileBaseViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseMobileListSerializer
    search_fields = ['code', 'name', 'city']
    filterset_fields = ['is_active']
    ordering = ['name']


class ProductViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Product.objects.select_related('category', 'currency')
    list_serializer_class = ProductMobileListSerializer
    detail_serializer_class = ProductMobileSerializer
    search_fields = ['sku', 'name']
    filterset_fields = ['category', 'is_active', 'product_type']
    ordering = ['name']


class _ProductCompanyScopedMixin:
    def get_queryset(self):
        qs = viewsets.ReadOnlyModelViewSet.get_queryset(self)
        company = self.get_company()
        if company:
            qs = qs.filter(product__company=company)
        return qs


class StockItemReadOnlyViewSet(_ProductCompanyScopedMixin, AdminMobileReadOnlyViewSet):
    queryset = StockItem.objects.select_related('product', 'warehouse')
    serializer_class = StockItemMobileListSerializer
    filterset_fields = ['warehouse', 'product']
    ordering = ['-on_hand']


class StockMovementReadOnlyViewSet(AdminMobileReadOnlyViewSet):
    queryset = StockMovement.objects.select_related('product', 'warehouse')
    serializer_class = StockMovementMobileListSerializer
    filterset_fields = ['warehouse', 'product', 'movement_type']
    ordering = ['-movement_date']


class GoodsReceiptViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = GoodsReceiptNote.objects.select_related('supplier', 'purchase_order')
    list_serializer_class = GoodsReceiptMobileListSerializer
    detail_serializer_class = GoodsReceiptNoteSerializer
    search_fields = ['grn_number']
    filterset_fields = ['supplier', 'status']
    ordering = ['-receipt_date']


class StockAdjustmentViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = StockAdjustment.objects.select_related('warehouse')
    list_serializer_class = StockAdjustmentMobileListSerializer
    detail_serializer_class = StockAdjustmentSerializer
    search_fields = ['adjustment_number']
    filterset_fields = ['warehouse', 'status', 'adjustment_type']
    ordering = ['-adjustment_date']


# ═══════════════════════════════════════════════════════════════════════════
# POS
# ═══════════════════════════════════════════════════════════════════════════


class POSTerminalViewSet(AdminMobileBaseViewSet):
    queryset = POSTerminal.objects.all()
    serializer_class = POSTerminalMobileSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['is_active']
    ordering = ['code']


class POSSessionViewSet(AdminMobileBaseViewSet):
    """POS sessions — list + retrieve + close action.

    Open/update/destroy happen via the dedicated POS endpoints; admins can
    only inspect and force-close sessions from mobile.
    """

    queryset = POSSession.objects.select_related('terminal', 'opened_by')
    serializer_class = POSSessionMobileListSerializer
    filterset_fields = ['terminal', 'status']
    ordering = ['-opened_at']
    http_method_names = ['get', 'head', 'options', 'post']

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        from erp.services import pos as pos_service
        session = self.get_object()
        employee = getattr(request.user, 'employee_profile', None)
        if employee is None:
            return Response(
                {'detail': 'Current user is not linked to an employee.'}, status=400,
            )
        closing_balance = request.data.get('closing_balance')
        if closing_balance is None:
            return Response({'detail': 'closing_balance is required.'}, status=400)
        try:
            pos_service.close_session(
                session=session,
                employee=employee,
                closing_balance=closing_balance,
                notes=request.data.get('notes', ''),
            )
        except (ValueError, TypeError):
            logger.warning('Invalid close_session request for session %s', session.pk)
            return Response(
                {'detail': 'Invalid closing_balance or session state.'},
                status=400,
            )
        session.refresh_from_db()
        return Response(POSSessionMobileListSerializer(session).data)


class POSOrderReadOnlyViewSet(AdminMobileReadOnlyViewSet):
    queryset = POSOrder.objects.select_related('session', 'customer')
    serializer_class = POSOrderMobileListSerializer
    search_fields = ['order_number']
    filterset_fields = ['session', 'customer', 'status']
    ordering = ['-created_at']


# ═══════════════════════════════════════════════════════════════════════════
# CRM
# ═══════════════════════════════════════════════════════════════════════════


class LeadViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Lead.objects.all()
    list_serializer_class = LeadMobileListSerializer
    detail_serializer_class = LeadSerializer
    search_fields = ['first_name', 'last_name', 'email', 'company_name', 'lead_number']
    filterset_fields = ['status', 'assigned_to']
    ordering = ['-created_at']


class _LeadCompanyScopedMixin:
    def get_queryset(self):
        qs = viewsets.ModelViewSet.get_queryset(self)
        company = self.get_company()
        if company:
            qs = qs.filter(lead__company=company)
        return qs


class LeadActivityViewSet(_DualSerializerMixin, _LeadCompanyScopedMixin, AdminMobileBaseViewSet):
    queryset = LeadActivity.objects.select_related('lead')
    list_serializer_class = LeadActivityMobileSerializer
    detail_serializer_class = LeadActivitySerializer
    filterset_fields = ['lead', 'activity_type', 'is_completed']
    ordering = ['-activity_date']


class _CustomerCompanyScopedMixin:
    def get_queryset(self):
        qs = viewsets.ModelViewSet.get_queryset(self)
        company = self.get_company()
        if company:
            qs = qs.filter(customer__company=company)
        return qs


class CustomerInteractionViewSet(
    _DualSerializerMixin, _CustomerCompanyScopedMixin, AdminMobileBaseViewSet
):
    queryset = CustomerInteraction.objects.select_related('customer')
    list_serializer_class = CustomerInteractionMobileSerializer
    detail_serializer_class = CustomerInteractionSerializer
    filterset_fields = ['customer', 'interaction_type']
    ordering = ['-interaction_date']


class TaskViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Task.objects.all()
    list_serializer_class = TaskMobileListSerializer
    detail_serializer_class = TaskSerializer
    search_fields = ['title']
    filterset_fields = ['status', 'priority', 'assigned_to']
    ordering = ['-created_at']


class CampaignViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Campaign.objects.all()
    list_serializer_class = CampaignMobileListSerializer
    detail_serializer_class = CampaignSerializer
    search_fields = ['name']
    filterset_fields = ['campaign_type', 'status']
    ordering = ['-start_date']


# ═══════════════════════════════════════════════════════════════════════════
# Services
# ═══════════════════════════════════════════════════════════════════════════


class QuoteViewSet(_DualSerializerMixin, AdminMobileBaseViewSet):
    queryset = Quote.objects.select_related('customer', 'currency').prefetch_related('lines')
    list_serializer_class = QuoteMobileListSerializer
    detail_serializer_class = QuoteSerializer
    search_fields = ['quote_number', 'customer__name']
    filterset_fields = ['customer', 'status']
    ordering = ['-quote_date']


class ServicePricingReadOnlyViewSet(AdminMobileReadOnlyViewSet):
    queryset = ServicePricing.objects.select_related('category', 'currency')
    serializer_class = ServicePricingMobileSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['category', 'pricing_type', 'is_active']
    ordering = ['name']
