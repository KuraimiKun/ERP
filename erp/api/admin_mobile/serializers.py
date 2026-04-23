"""Mobile-light serializers for the Admin Mobile API.

These serializers are designed for bandwidth-constrained mobile clients:
only the fields a card / list row needs are exposed.  Detail endpoints
can reuse the richer serializers from ``erp.api.serializers`` and
``erp.api.inventory_serializers`` directly.
"""

from __future__ import annotations

from rest_framework import serializers

from erp.models import (
    Account,
    Attendance,
    AuditLog,
    Branch,
    Campaign,
    Company,
    Currency,
    Customer,
    CustomerInteraction,
    Department,
    Employee,
    Expense,
    ExpenseCategory,
    FiscalYear,
    GoodsReceiptNote,
    Invoice,
    Lead,
    LeadActivity,
    LeaveRequest,
    LeaveType,
    Notification,
    POSOrder,
    POSSession,
    POSTerminal,
    Payment,
    PaymentMethod,
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

# ---------------------------------------------------------------------------
# HR
# ---------------------------------------------------------------------------


class EmployeeMobileListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_id",
            "first_name",
            "last_name",
            "email",
            "job_title",
            "department",
            "department_name",
            "employment_status",
        ]


class DepartmentMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "code", "is_active"]


class BranchMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "city", "country", "is_headquarters"]


class AttendanceMobileListSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee",
            "employee_name",
            "date",
            "check_in",
            "check_out",
            "hours_worked",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"


class LeaveRequestMobileListSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_name",
            "leave_type",
            "leave_type_name",
            "start_date",
            "end_date",
            "days_requested",
            "status",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"


class LeaveTypeMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "name", "is_active"]


class PayrollMobileListSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Payroll
        fields = [
            "id",
            "employee",
            "employee_name",
            "period_start",
            "period_end",
            "gross_salary",
            "net_salary",
            "status",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------


class CustomerMobileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_id",
            "name",
            "email",
            "phone",
            "current_balance",
            "is_active",
        ]


class InvoiceMobileListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "customer",
            "customer_name",
            "invoice_date",
            "due_date",
            "total_amount",
            "balance_due",
            "status",
        ]


class PaymentMobileListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_number",
            "customer",
            "customer_name",
            "payment_date",
            "amount",
            "payment_method",
        ]


class ExpenseMobileListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "expense_number",
            "category",
            "category_name",
            "expense_date",
            "amount",
            "total_amount",
            "status",
        ]


class AccountMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["id", "code", "name", "account_type", "current_balance", "is_active"]


class TaxRateMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRate
        fields = ["id", "name", "rate", "is_active"]


class CurrencyMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "code", "name", "symbol", "exchange_rate", "is_base", "is_active"]


class FiscalYearMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalYear
        fields = ["id", "name", "start_date", "end_date", "is_current", "is_closed"]


class ExpenseCategoryMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "code", "is_active"]


class PaymentMethodMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ["id", "name", "is_active"]


class CompanyMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "name_ar",
            "email",
            "phone",
            "address",
            "city",
            "country",
            "tax_number",
            "ai_enabled",
        ]
        read_only_fields = ["id", "tax_number", "ai_enabled"]


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


class SupplierMobileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "supplier_id",
            "name",
            "email",
            "phone",
            "current_balance",
            "is_active",
        ]


class PurchaseOrderMobileListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "supplier",
            "supplier_name",
            "po_date",
            "total_amount",
            "balance_due",
            "status",
        ]


class SupplierInvoiceMobileListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            "id",
            "invoice_number",
            "supplier",
            "supplier_name",
            "invoice_date",
            "due_date",
            "total_amount",
            "balance_due",
            "status",
        ]


class SupplierInvoiceMobileSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            "id",
            "company",
            "supplier",
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "due_date",
            "currency",
            "subtotal",
            "tax_amount",
            "total_amount",
            "paid_amount",
            "balance_due",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "total_amount",
            "balance_due",
            "created_at",
            "updated_at",
        ]


class SupplierPaymentMobileListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = SupplierPayment
        fields = [
            "id",
            "payment_number",
            "supplier",
            "supplier_name",
            "payment_date",
            "amount",
            "payment_method",
        ]


class SupplierPaymentMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierPayment
        fields = [
            "id",
            "company",
            "supplier",
            "payment_number",
            "payment_date",
            "amount",
            "currency",
            "payment_method",
            "reference_number",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["payment_number", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


class ProductMobileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "selling_price",
            "cost_price",
            "quantity_on_hand",
            "reorder_level",
            "is_active",
        ]


class ProductMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "company",
            "sku",
            "name",
            "description",
            "product_type",
            "category",
            "currency",
            "selling_price",
            "cost_price",
            "min_selling_price",
            "track_inventory",
            "quantity_on_hand",
            "reorder_level",
            "reorder_quantity",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class WarehouseMobileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "code", "name", "city", "is_active"]


class StockItemMobileListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = StockItem
        fields = [
            "id",
            "product",
            "product_name",
            "warehouse",
            "warehouse_name",
            "on_hand",
            "allocated",
        ]


class StockMovementMobileListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "product",
            "product_name",
            "warehouse",
            "movement_type",
            "quantity",
            "movement_date",
        ]


class GoodsReceiptMobileListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = GoodsReceiptNote
        fields = [
            "id",
            "grn_number",
            "supplier",
            "supplier_name",
            "receipt_date",
            "status",
        ]


class StockAdjustmentMobileListSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = StockAdjustment
        fields = [
            "id",
            "adjustment_number",
            "warehouse",
            "warehouse_name",
            "adjustment_date",
            "reason",
            "status",
        ]


# ---------------------------------------------------------------------------
# POS
# ---------------------------------------------------------------------------


class POSTerminalMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = POSTerminal
        fields = ["id", "code", "name", "is_active"]


class POSSessionMobileListSerializer(serializers.ModelSerializer):
    terminal_code = serializers.CharField(source="terminal.code", read_only=True)
    opened_by_name = serializers.SerializerMethodField()

    class Meta:
        model = POSSession
        fields = [
            "id",
            "session_number",
            "terminal",
            "terminal_code",
            "opened_by",
            "opened_by_name",
            "opened_at",
            "closed_at",
            "status",
            "total_sales",
            "total_orders",
        ]

    def get_opened_by_name(self, obj):
        if not obj.opened_by_id:
            return ""
        return f"{obj.opened_by.first_name} {obj.opened_by.last_name}"


class POSOrderMobileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = POSOrder
        fields = [
            "id",
            "order_number",
            "session",
            "customer",
            "total_amount",
            "status",
            "created_at",
        ]


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------


class LeadMobileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "lead_number",
            "first_name",
            "last_name",
            "company_name",
            "email",
            "phone",
            "status",
            "probability",
        ]


class LeadActivityMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadActivity
        fields = [
            "id",
            "lead",
            "activity_type",
            "subject",
            "description",
            "activity_date",
            "is_completed",
            "completed_date",
            "created_at",
        ]


class CustomerInteractionMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerInteraction
        fields = [
            "id",
            "customer",
            "interaction_type",
            "subject",
            "description",
            "interaction_date",
            "created_at",
        ]


class TaskMobileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "priority",
            "status",
            "due_date",
            "assigned_to",
            "created_at",
        ]


class CampaignMobileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "campaign_type",
            "status",
            "start_date",
            "end_date",
            "budget",
        ]


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


class QuoteMobileListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = Quote
        fields = [
            "id",
            "quote_number",
            "customer",
            "customer_name",
            "quote_date",
            "valid_until",
            "total_amount",
            "status",
        ]


class ServicePricingMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePricing
        fields = [
            "id",
            "name",
            "code",
            "base_price",
            "cost_price",
            "currency",
            "pricing_type",
            "is_active",
        ]


# ---------------------------------------------------------------------------
# Audit & Notifications
# ---------------------------------------------------------------------------


class AuditLogMobileSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    model = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "user_email",
            "action",
            "model",
            "object_id",
            "object_repr",
            "created_at",
        ]

    def get_model(self, obj):
        return obj.content_type.model if obj.content_type_id else None


class NotificationMobileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "action_url",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = ["read_at", "created_at"]
