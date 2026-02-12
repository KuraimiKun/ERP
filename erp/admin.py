"""
ERP Admin Registration

This module registers all ERP models with the Django admin.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    # Core
    Currency, Company, Department, Branch, FiscalYear, Sequence,
    # HR
    Employee, EmployeeDocument, LeaveType, LeaveRequest, Attendance, Payroll,
    # Finance
    Account, TaxRate, PaymentMethod, Customer, Invoice, InvoiceLine,
    Payment, PaymentAllocation, Expense, ExpenseCategory, ExpenseAttachment,
    # Supplier
    Supplier, SupplierContact, SupplierDocument, PurchaseOrder, PurchaseOrderLine,
    SupplierInvoice, SupplierInvoiceLine, SupplierPayment, SupplierPaymentAllocation,
    # CRM
    Lead, LeadActivity, CustomerInteraction, Campaign, CampaignLead, Task, TaskComment,
    # Services
    ServiceCategory, ServicePricing, PriceTier, ServicePackage, PackageItem, Quote, QuoteLine,
    # Reporting
    ReportTemplate, GeneratedReport, Dashboard, DashboardWidget, KPI, KPIValue,
    # Audit
    AuditLog, SystemSetting, Notification, EmailTemplate, FileAttachment, ScheduledTask, IntegrationLog,
)


# =============================================================================
# Core Admin
# =============================================================================

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'exchange_rate', 'is_base', 'is_active']
    list_filter = ['is_base', 'is_active']
    search_fields = ['code', 'name']
    list_editable = ['exchange_rate', 'is_active']


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'city', 'country']
    search_fields = ['name', 'email', 'legal_name']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'name_ar', 'legal_name', 'logo', 'favicon')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'fax', 'website')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Tax & Registration', {
            'fields': ('tax_number', 'commercial_register', 'license_number')
        }),
        ('Banking', {
            'fields': ('bank_name', 'bank_account', 'iban', 'swift_code')
        }),
        ('Settings', {
            'fields': ('base_currency', 'fiscal_year_start')
        }),
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'company', 'manager', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'company', 'city', 'is_headquarters', 'is_active']
    list_filter = ['company', 'is_headquarters', 'is_active']
    search_fields = ['name', 'code', 'city']


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'start_date', 'end_date', 'is_current', 'is_closed']
    list_filter = ['company', 'is_current', 'is_closed']
    search_fields = ['name']


@admin.register(Sequence)
class SequenceAdmin(admin.ModelAdmin):
    list_display = ['sequence_type', 'company', 'prefix', 'next_number', 'padding', 'reset_period']
    list_filter = ['company', 'sequence_type', 'reset_period']
    search_fields = ['prefix']


# =============================================================================
# HR Admin
# =============================================================================

class EmployeeDocumentInline(admin.TabularInline):
    model = EmployeeDocument
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'full_name', 'department', 'job_title', 'employment_status', 'employment_type']
    list_filter = ['company', 'department', 'employment_status', 'employment_type']
    search_fields = ['employee_id', 'first_name', 'last_name', 'email']
    inlines = [EmployeeDocumentInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'employee_id', 'company', 'branch')
        }),
        ('Personal Details', {
            'fields': ('first_name', 'last_name', 'first_name_ar', 'last_name_ar', 'gender', 'date_of_birth', 'nationality')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'address', 'city', 'country')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone')
        }),
        ('Documents', {
            'fields': ('national_id', 'passport_number', 'passport_expiry', 'photo')
        }),
        ('Employment', {
            'fields': ('department', 'job_title', 'reports_to', 'employment_type', 'employment_status', 'hire_date', 'termination_date')
        }),
        ('Compensation', {
            'fields': ('basic_salary', 'currency', 'bank_name', 'bank_account', 'iban')
        }),
        ('Leave Balance', {
            'fields': ('annual_leave_balance', 'sick_leave_balance')
        }),
    )


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'days_allowed', 'is_paid', 'is_active']
    list_filter = ['is_paid', 'is_active']
    search_fields = ['name', 'code']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'days_requested', 'status']
    list_filter = ['status', 'leave_type', 'start_date']
    search_fields = ['employee__first_name', 'employee__last_name']
    date_hierarchy = 'start_date'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'check_in', 'check_out', 'hours_worked', 'is_present', 'is_late']
    list_filter = ['is_present', 'is_late', 'date']
    search_fields = ['employee__first_name', 'employee__last_name']
    date_hierarchy = 'date'


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ['employee', 'period_start', 'period_end', 'gross_salary', 'net_salary', 'status']
    list_filter = ['status', 'period_start']
    search_fields = ['employee__first_name', 'employee__last_name']


# =============================================================================
# Finance Admin
# =============================================================================

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'current_balance', 'is_active']
    list_filter = ['company', 'account_type', 'is_active']
    search_fields = ['code', 'name']
    list_editable = ['is_active']


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ['name', 'rate', 'is_default', 'is_active']
    list_filter = ['company', 'is_default', 'is_active']


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']
    list_filter = ['company', 'is_active']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'name', 'customer_type', 'email', 'phone', 'current_balance', 'is_active']
    list_filter = ['company', 'customer_type', 'is_active']
    search_fields = ['customer_id', 'name', 'email', 'phone']


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer', 'invoice_date', 'due_date', 'total_amount', 'balance_due', 'status']
    list_filter = ['status', 'invoice_type', 'invoice_date']
    search_fields = ['invoice_number', 'customer__name']
    date_hierarchy = 'invoice_date'
    inlines = [InvoiceLineInline]
    readonly_fields = ['subtotal', 'tax_amount', 'total_amount', 'paid_amount', 'balance_due']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_number', 'customer', 'payment_date', 'payment_method', 'amount', 'allocated_amount']
    list_filter = ['payment_type', 'payment_method', 'payment_date']
    search_fields = ['payment_number', 'customer__name']
    date_hierarchy = 'payment_date'


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'parent', 'is_active']
    list_filter = ['company', 'is_active']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['expense_number', 'expense_date', 'category', 'total_amount', 'status']
    list_filter = ['status', 'category', 'expense_date']
    search_fields = ['expense_number', 'description']
    date_hierarchy = 'expense_date'


# =============================================================================
# Supplier Admin
# =============================================================================

class SupplierContactInline(admin.TabularInline):
    model = SupplierContact
    extra = 0


class SupplierDocumentInline(admin.TabularInline):
    model = SupplierDocument
    extra = 0


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['supplier_id', 'name', 'supplier_type', 'email', 'phone', 'current_balance', 'is_active']
    list_filter = ['company', 'supplier_type', 'is_active']
    search_fields = ['supplier_id', 'name', 'email']
    inlines = [SupplierContactInline, SupplierDocumentInline]


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['po_number', 'supplier', 'po_date', 'total_amount', 'status']
    list_filter = ['status', 'po_date']
    search_fields = ['po_number', 'supplier__name']
    date_hierarchy = 'po_date'
    inlines = [PurchaseOrderLineInline]


class SupplierInvoiceLineInline(admin.TabularInline):
    model = SupplierInvoiceLine
    extra = 1


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'supplier', 'invoice_date', 'due_date', 'total_amount', 'balance_due', 'status']
    list_filter = ['status', 'invoice_date']
    search_fields = ['invoice_number', 'supplier__name']
    date_hierarchy = 'invoice_date'
    inlines = [SupplierInvoiceLineInline]


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_number', 'supplier', 'payment_date', 'amount', 'allocated_amount']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['payment_number', 'supplier__name']
    date_hierarchy = 'payment_date'


# =============================================================================
# CRM Admin
# =============================================================================

class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    ordering = ['-activity_date']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['lead_number', 'full_name', 'email', 'phone', 'source', 'status', 'assigned_to']
    list_filter = ['status', 'source', 'assigned_to']
    search_fields = ['lead_number', 'first_name', 'last_name', 'email', 'company_name']
    inlines = [LeadActivityInline]


@admin.register(CustomerInteraction)
class CustomerInteractionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'interaction_type', 'subject', 'interaction_date', 'handled_by']
    list_filter = ['interaction_type', 'interaction_date']
    search_fields = ['customer__name', 'subject']
    date_hierarchy = 'interaction_date'


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'campaign_type', 'status', 'start_date', 'budget', 'actual_leads']
    list_filter = ['status', 'campaign_type']
    search_fields = ['name']
    date_hierarchy = 'start_date'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'status', 'assigned_to', 'due_date']
    list_filter = ['status', 'priority', 'assigned_to']
    search_fields = ['title', 'description']


# =============================================================================
# Services Admin
# =============================================================================

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'parent', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['name', 'code']


@admin.register(ServicePricing)
class ServicePricingAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'pricing_type', 'base_price', 'cost_price', 'is_active']
    list_filter = ['category', 'pricing_type', 'is_active']
    search_fields = ['code', 'name']


class PackageItemInline(admin.TabularInline):
    model = PackageItem
    extra = 1


@admin.register(ServicePackage)
class ServicePackageAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'regular_price', 'package_price', 'is_active', 'is_featured']
    list_filter = ['is_active', 'is_featured']
    search_fields = ['code', 'name']
    inlines = [PackageItemInline]


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 1


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ['quote_number', 'customer', 'quote_date', 'valid_until', 'total_amount', 'status']
    list_filter = ['status', 'quote_date']
    search_fields = ['quote_number', 'customer__name']
    date_hierarchy = 'quote_date'
    inlines = [QuoteLineInline]


# =============================================================================
# Reporting Admin
# =============================================================================

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'default_format', 'is_public', 'is_active']
    list_filter = ['report_type', 'is_public', 'is_active']
    search_fields = ['name']


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ['template', 'generated_by', 'date_from', 'date_to', 'output_format', 'is_ready', 'created_at']
    list_filter = ['template', 'output_format', 'is_ready']
    date_hierarchy = 'created_at'


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_default', 'is_public']
    list_filter = ['is_default', 'is_public']
    search_fields = ['name']


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ['name', 'kpi_type', 'target_value', 'unit', 'is_active']
    list_filter = ['kpi_type', 'is_active']
    search_fields = ['name']


# =============================================================================
# Audit Admin
# =============================================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'object_repr', 'ip_address']
    list_filter = ['action', 'created_at']
    search_fields = ['user__email', 'object_repr']
    date_hierarchy = 'created_at'
    readonly_fields = ['user', 'action', 'content_type', 'object_id', 'object_repr', 'changes', 'ip_address', 'user_agent', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'category', 'setting_type', 'is_editable']
    list_filter = ['company', 'category', 'setting_type']
    search_fields = ['key', 'category']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']
    search_fields = ['title', 'recipient__email']
    date_hierarchy = 'created_at'


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'subject', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['name', 'code', 'subject']


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'task_type', 'status', 'last_run', 'next_run', 'is_enabled']
    list_filter = ['status', 'is_enabled']
    search_fields = ['name', 'task_type']


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ['integration_name', 'direction', 'status', 'status_code', 'duration_ms', 'created_at']
    list_filter = ['integration_name', 'direction', 'status']
    date_hierarchy = 'created_at'
    readonly_fields = ['integration_name', 'direction', 'endpoint', 'method', 'request_data', 'response_data', 'status', 'status_code', 'error_message', 'duration_ms', 'created_at']
