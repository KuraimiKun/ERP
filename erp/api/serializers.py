"""
ERP API Serializers

Django REST Framework serializers for the ERP models.
"""

from rest_framework import serializers
from ..models import (
    # Core
    Currency, Company, Department, Branch, FiscalYear, Employee, LeaveType, LeaveRequest, Attendance, Payroll,
    # Finance
    Account, TaxRate, PaymentMethod, Customer, Invoice, InvoiceLine, 
    Payment, Expense, ExpenseCategory, Supplier, SupplierContact, PurchaseOrder, 
    PurchaseOrderLine, Lead, LeadActivity, CustomerInteraction, Campaign, Task, TaskComment,
    # Services
    ServiceCategory, ServicePricing, PriceTier, Quote, QuoteLine,
    # Reporting
    Dashboard, DashboardWidget, KPI, KPIValue,
    ReportTemplate, GeneratedReport,
    # Audit
    AuditLog, Notification,
)


# =============================================================================
# Core Serializers
# =============================================================================

class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'exchange_rate', 'is_base', 'is_active']


class CompanySerializer(serializers.ModelSerializer):
    currency_display = CurrencySerializer(source='base_currency', read_only=True)

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'legal_name', 'tax_number',
            'email', 'phone', 'website', 'address', 'city', 'state',
            'postal_code', 'country', 'base_currency', 'currency_display',
            'fiscal_year_start', 'logo', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class DepartmentSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    manager_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = [
            'id', 'company', 'name', 'code', 'description', 'parent', 
            'parent_name', 'manager', 'manager_name', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_manager_name(self, obj):
        if obj.manager:
            return f"{obj.manager.first_name} {obj.manager.last_name}"
        return None


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            'id', 'company', 'name', 'code', 'address', 'city',
            'country', 'phone', 'email', 'is_headquarters',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class FiscalYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalYear
        fields = [
            'id', 'company', 'name', 'start_date', 'end_date', 
            'is_closed', 'is_current', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


# =============================================================================
# HR Serializers
# =============================================================================

class EmployeeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    department_name = serializers.CharField(source='department.name', read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'first_name', 'last_name', 'full_name',
            'email', 'job_title', 'department', 'department_name',
            'employment_status'
        ]
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    reports_to_name = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'company', 'user', 'employee_id', 'first_name', 'last_name',
            'full_name', 'email', 'phone', 'date_of_birth', 'gender',
            'nationality', 'address', 'city', 'country',
            'department', 'department_name', 'branch', 'job_title', 'reports_to',
            'reports_to_name', 'hire_date', 'termination_date', 'employment_type',
            'employment_status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['employee_id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_reports_to_name(self, obj):
        if obj.reports_to:
            return f"{obj.reports_to.first_name} {obj.reports_to.last_name}"
        return None


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = [
            'id', 'name', 'code', 'days_allowed', 'is_paid',
            'is_active'
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    
    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_name', 'leave_type', 'leave_type_name',
            'start_date', 'end_date', 'days_requested', 'reason', 'status',
            'approved_by', 'approval_date', 'approval_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['days_requested', 'approval_date', 'created_at', 'updated_at']
    
    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'employee', 'employee_name', 'date', 'check_in', 'check_out',
            'hours_worked', 'overtime_hours', 'is_late', 'late_minutes',
            'notes', 'created_at'
        ]
        read_only_fields = ['hours_worked', 'is_late', 'late_minutes', 'created_at']
    
    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"


class PayrollSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Payroll
        fields = [
            'id', 'employee', 'employee_name', 'period_start', 'period_end',
            'basic_salary', 'overtime_amount', 'bonus',
            'gross_salary', 'total_deductions', 'tax_deduction', 'net_salary',
            'status', 'payment_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['gross_salary', 'net_salary', 'created_at', 'updated_at']
    
    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"


# =============================================================================
# Finance Serializers
# =============================================================================

class AccountSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    
    class Meta:
        model = Account
        fields = [
            'id', 'company', 'code', 'name', 'account_type', 'parent',
            'parent_name', 'description', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRate
        fields = ['id', 'company', 'name', 'rate', 'is_active']


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'company', 'name', 'is_active']


class CustomerListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    class Meta:
        model = Customer
        fields = [
            'id', 'customer_id', 'name', 'customer_type', 'email',
            'phone', 'current_balance', 'is_active'
        ]


class CustomerSerializer(serializers.ModelSerializer):
    currency_display = CurrencySerializer(source='currency', read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'company', 'customer_id', 'name', 'customer_type', 'email',
            'phone', 'mobile', 'billing_address', 'billing_city', 'billing_state', 'billing_postal_code',
            'billing_country', 'currency', 'currency_display', 'tax_id', 'credit_limit',
            'payment_terms', 'current_balance', 'notes', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['customer_id', 'current_balance', 'created_at', 'updated_at']


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = [
            'id', 'invoice', 'description', 'quantity', 'unit_price',
            'discount_percent', 'tax_rate', 'tax_amount',
            'line_total'
        ]
        read_only_fields = ['tax_amount', 'line_total']


class InvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'customer', 'customer_name', 'invoice_date',
            'due_date', 'total_amount', 'balance_due', 'status'
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    customer_display = CustomerListSerializer(source='customer', read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    currency_display = CurrencySerializer(source='currency', read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'company', 'customer', 'customer_display', 'invoice_number',
            'invoice_date', 'due_date', 'reference', 'currency', 'currency_display',
            'subtotal', 'discount_amount', 'tax_amount', 'total_amount',
            'paid_amount', 'balance_due', 'status', 'notes', 'terms',
            'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'invoice_number', 'subtotal', 'tax_amount', 'total_amount',
            'paid_amount', 'balance_due', 'created_at', 'updated_at'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'company', 'customer', 'customer_name', 'payment_number',
            'payment_date', 'amount', 'payment_method', 'reference_number', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['payment_number', 'created_at', 'updated_at']


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'company', 'name', 'code', 'parent', 'is_active']


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            'id', 'company', 'expense_number', 'category', 'category_name',
            'expense_date', 'description', 'amount', 'tax_amount', 'total_amount',
            'currency', 'employee', 'employee_name', 'status',
            'approved_by', 'approval_date', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['expense_number', 'total_amount', 'approval_date', 'created_at', 'updated_at']

    def get_employee_name(self, obj):
        if obj.employee:
            return f"{obj.employee.first_name} {obj.employee.last_name}"
        return None


# =============================================================================
# Supplier Serializers
# =============================================================================

class SupplierListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    class Meta:
        model = Supplier
        fields = [
            'id', 'supplier_id', 'name', 'supplier_type', 'email',
            'phone', 'rating', 'is_active'
        ]


class SupplierContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierContact
        fields = [
            'id', 'supplier', 'name', 'position', 'email', 'phone',
            'mobile', 'is_primary', 'notes'
        ]


class SupplierSerializer(serializers.ModelSerializer):
    contacts = SupplierContactSerializer(many=True, read_only=True)
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'company', 'supplier_id', 'name', 'supplier_type',
            'email', 'phone', 'website', 'address', 'city',
            'postal_code', 'country', 'currency', 'tax_number', 'payment_terms',
            'rating', 'notes', 'is_active', 'contacts',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['supplier_id', 'created_at', 'updated_at']


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderLine
        fields = [
            'id', 'purchase_order', 'description', 'quantity', 'unit_price',
            'tax_rate', 'tax_amount', 'line_total'
        ]
        read_only_fields = ['tax_amount', 'line_total']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'company', 'supplier', 'supplier_name', 'po_number',
            'po_date', 'expected_date', 'subtotal', 'tax_amount',
            'total_amount', 'status', 'notes', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'po_number', 'subtotal', 'tax_amount', 'total_amount',
            'created_at', 'updated_at'
        ]


# =============================================================================
# CRM Serializers
# =============================================================================

class LeadListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    full_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Lead
        fields = [
            'id', 'lead_number', 'first_name', 'last_name', 'full_name',
            'email', 'phone', 'source', 'status', 'estimated_value',
            'assigned_to', 'assigned_to_name', 'created_at'
        ]
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None


class LeadActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LeadActivity
        fields = [
            'id', 'lead', 'activity_type', 'activity_date', 'description',
            'performed_by', 'performed_by_name', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return f"{obj.performed_by.first_name} {obj.performed_by.last_name}"
        return None


class LeadSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    activities = LeadActivitySerializer(many=True, read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'company', 'lead_number', 'first_name', 'last_name',
            'email', 'phone', 'mobile', 'company_name', 'job_title',
            'source', 'status', 'estimated_value', 'service_interest',
            'notes', 'assigned_to', 'assigned_to_name', 'last_contact_date',
            'next_follow_up', 'converted_customer', 'conversion_date',
            'activities', 'created_at', 'updated_at'
        ]
        read_only_fields = ['lead_number', 'conversion_date', 'created_at', 'updated_at']
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None


class CustomerInteractionSerializer(serializers.ModelSerializer):
    handled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerInteraction
        fields = [
            'id', 'customer', 'interaction_type', 'interaction_date',
            'subject', 'description', 'handled_by', 'handled_by_name',
            'follow_up_date', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_handled_by_name(self, obj):
        if obj.handled_by:
            return f"{obj.handled_by.first_name} {obj.handled_by.last_name}"
        return None


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = [
            'id', 'company', 'name', 'campaign_type', 'status',
            'start_date', 'end_date', 'budget', 'actual_cost',
            'expected_revenue', 'actual_revenue', 'description',
            'target_audience', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskComment
        fields = ['id', 'task', 'author', 'author_name', 'content', 'created_at']
        read_only_fields = ['created_at']
    
    def get_author_name(self, obj):
        if obj.author:
            return f"{obj.author.first_name} {obj.author.last_name}"
        return None


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    assigned_to_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'priority', 'status', 'due_date',
            'assigned_to', 'assigned_to_name'
        ]
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    comments = TaskCommentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'company', 'title', 'description', 'priority', 'status',
            'due_date', 'assigned_to', 'assigned_to_name', 'related_lead',
            'related_customer', 'comments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None


# =============================================================================
# Services Serializers
# =============================================================================

class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ['id', 'company', 'name', 'description', 'parent', 'is_active']


class PriceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceTier
        fields = ['id', 'service_pricing', 'min_quantity', 'max_quantity', 'price']


class ServicePricingSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    tiers = PriceTierSerializer(many=True, read_only=True)
    
    class Meta:
        model = ServicePricing
        fields = [
            'id', 'company', 'name', 'code', 'category', 'category_name',
            'description', 'pricing_type', 'base_price', 'currency',
            'is_active', 'tiers',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class QuoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteLine
        fields = [
            'id', 'quote', 'description', 'quantity', 'unit_price',
            'discount_percent', 'tax_rate', 'tax_amount',
            'line_total'
        ]
        read_only_fields = ['tax_amount', 'line_total']


class QuoteListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = Quote
        fields = [
            'id', 'quote_number', 'customer', 'customer_name', 'quote_date',
            'valid_until', 'total_amount', 'status'
        ]


class QuoteSerializer(serializers.ModelSerializer):
    customer_display = CustomerListSerializer(source='customer', read_only=True)
    lines = QuoteLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = Quote
        fields = [
            'id', 'company', 'customer', 'customer_display', 'lead',
            'quote_number', 'quote_date', 'valid_until', 'reference',
            'currency', 'subtotal', 'discount_amount', 'tax_amount',
            'total_amount', 'status', 'notes', 'terms', 'converted_to_invoice',
            'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'quote_number', 'subtotal', 'tax_amount', 'total_amount',
            'created_at', 'updated_at'
        ]


# =============================================================================
# Reporting Serializers
# =============================================================================

class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'dashboard', 'title', 'widget_type', 'data_source',
            'configuration', 'row', 'column', 'width', 'height'
        ]


class DashboardSerializer(serializers.ModelSerializer):
    widgets = DashboardWidgetSerializer(many=True, read_only=True)
    
    class Meta:
        model = Dashboard
        fields = [
            'id', 'company', 'name', 'description', 'is_default',
            'owner', 'widgets', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class KPIValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = KPIValue
        fields = ['id', 'kpi', 'value', 'period_start', 'created_at']


class KPISerializer(serializers.ModelSerializer):
    recent_values = serializers.SerializerMethodField()
    
    class Meta:
        model = KPI
        fields = [
            'id', 'company', 'name', 'description', 'kpi_type',
            'target_value', 'unit', 'is_active', 'recent_values'
        ]

    def get_recent_values(self, obj):
        values = obj.values.order_by('-period_start')[:10]
        return KPIValueSerializer(values, many=True).data


# =============================================================================
# Audit Serializers
# =============================================================================

class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'action', 'content_type', 'object_id',
            'object_repr', 'changes', 'ip_address', 'user_agent', 'created_at'
        ]
        read_only_fields = ['created_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'title', 'message', 'notification_type',
            'is_read', 'read_at', 'action_url', 'created_at'
        ]
        read_only_fields = ['read_at', 'created_at']


# =============================================================================
# Report Builder Serializers
# =============================================================================

class ReportTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')
    last_generated = serializers.SerializerMethodField()

    class Meta:
        model = ReportTemplate
        fields = [
            'id', 'name', 'report_type', 'description', 'default_format',
            'is_public', 'is_active', 'is_system', 'created_by', 'created_by_name',
            'last_generated', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_last_generated(self, obj):
        last = obj.generated_reports.order_by('-created_at').values('created_at', 'status').first()
        if last:
            return {
                'date': last['created_at'].isoformat(),
                'status': last['status'],
            }
        return None


class ReportTemplateSerializer(serializers.ModelSerializer):
    """Full serializer for create/update with configuration validation."""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = ReportTemplate
        fields = [
            'id', 'company', 'name', 'report_type', 'description',
            'configuration', 'default_format', 'is_public', 'allowed_roles',
            'is_active', 'is_system', 'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['company', 'created_by', 'created_at', 'updated_at']

    def validate_configuration(self, value):
        from erp.services.report_builder import validate_configuration
        if not value:
            return value
        is_valid, errors = validate_configuration(value)
        if not is_valid:
            raise serializers.ValidationError(errors)
        return value


class GeneratedReportSerializer(serializers.ModelSerializer):
    """Read-only serializer for generated report instances."""
    template_name = serializers.CharField(source='template.name', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.username', read_only=True, default='')
    duration = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'template', 'template_name', 'generated_by', 'generated_by_name',
            'parameters', 'date_from', 'date_to', 'output_format',
            'status', 'is_ready', 'error_message', 'row_count',
            'started_at', 'completed_at', 'duration',
            'download_url', 'created_at',
        ]
        read_only_fields = [
            'status', 'is_ready', 'error_message', 'row_count',
            'started_at', 'completed_at', 'created_at',
        ]

    def get_duration(self, obj):
        d = obj.duration_seconds
        if d is not None:
            return round(d, 1)
        return None

    def get_download_url(self, obj):
        if obj.file and obj.is_ready:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
