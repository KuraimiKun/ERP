"""
ERP Forms

Form classes for ERP model CRUD operations.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    # Core
    Company, Currency, Department, Branch,
    # HR
    Employee, LeaveType, LeaveRequest, Attendance,
    # Finance
    Customer, Invoice, InvoiceLine, Payment, ExpenseCategory, Expense,
    Account, JournalEntry, JournalEntryLine,
    # Suppliers
    Supplier, SupplierContact, PurchaseOrder, PurchaseOrderLine,
    # CRM
    Lead, LeadActivity, CustomerInteraction, Campaign, Task, TaskComment,
    # Services
    ServiceCategory, ServicePricing, Quote, QuoteLine,
    # Products
    ProductCategory, Product, ProductSupplier,
)

User = get_user_model()


# =============================================================================
# Base Form Mixins
# =============================================================================

class CompanyFilterMixin:
    """Mixin to filter querysets by company."""
    
    def __init__(self, *args, company=None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)
        self.filter_querysets_by_company()
    
    def filter_querysets_by_company(self):
        """Filter all ForeignKey fields by company."""
        if not self.company:
            return
        
        for field_name, field in self.fields.items():
            if hasattr(field, 'queryset'):
                model = field.queryset.model
                if hasattr(model, 'company'):
                    field.queryset = field.queryset.filter(company=self.company)


class BootstrapFormMixin:
    """Mixin to add Bootstrap 5 classes to form fields."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()
    
    def add_bootstrap_classes(self):
        """Add Bootstrap form-control class to all fields."""
        for field_name, field in self.fields.items():
            widget = field.widget
            existing_class = widget.attrs.get('class', '')
            
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = f'{existing_class} form-check-input'.strip()
            elif isinstance(widget, forms.Select):
                widget.attrs['class'] = f'{existing_class} form-select'.strip()
            elif isinstance(widget, forms.Textarea):
                widget.attrs['class'] = f'{existing_class} form-control'.strip()
                widget.attrs.setdefault('rows', 3)
            elif isinstance(widget, forms.FileInput):
                widget.attrs['class'] = f'{existing_class} form-control'.strip()
            else:
                widget.attrs['class'] = f'{existing_class} form-control'.strip()


# =============================================================================
# Core Forms
# =============================================================================

class CompanyForm(BootstrapFormMixin, forms.ModelForm):
    """Form for Company model."""
    
    class Meta:
        model = Company
        fields = [
            'name', 'name_ar', 'legal_name', 'tax_number', 'commercial_register',
            'license_number', 'email', 'phone', 'fax', 'website', 'address', 
            'city', 'state', 'country', 'postal_code', 'logo', 'base_currency',
            'fiscal_year_start', 'bank_name', 'bank_account', 'iban', 'swift_code'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }


class DepartmentForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Department model."""
    
    class Meta:
        model = Department
        fields = ['name', 'name_ar', 'code', 'description', 'parent', 'manager', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class BranchForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Branch model."""
    
    class Meta:
        model = Branch
        fields = [
            'name', 'name_ar', 'code', 'address', 'city', 'country',
            'phone', 'email', 'manager', 'is_headquarters', 'is_active'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }


# =============================================================================
# HR Forms
# =============================================================================

class EmployeeForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Employee model."""
    
    class Meta:
        model = Employee
        fields = [
            'user', 'employee_id', 'first_name', 'last_name', 'first_name_ar', 
            'last_name_ar', 'gender', 'date_of_birth', 'nationality',
            'email', 'phone', 'emergency_contact_name', 'emergency_contact_phone',
            'address', 'city', 'country', 'national_id', 'passport_number',
            'passport_expiry', 'photo', 'department', 'branch', 'job_title',
            'employment_type', 'employment_status', 'hire_date', 'reports_to',
            'basic_salary', 'currency', 'bank_name', 'bank_account', 'iban'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'passport_expiry': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users who don't already have employee profiles
        if not self.instance.pk:
            existing_employee_users = Employee.objects.exclude(user__isnull=True).values_list('user_id', flat=True)
            self.fields['user'].queryset = User.objects.exclude(id__in=existing_employee_users)


class LeaveRequestForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for LeaveRequest model."""
    
    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }


class AttendanceForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Attendance model."""
    
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'check_in', 'check_out', 'is_present', 'is_late', 'late_minutes', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'check_in': forms.TimeInput(attrs={'type': 'time'}),
            'check_out': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


# =============================================================================
# Finance Forms
# =============================================================================

class CustomerForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Customer model."""
    
    class Meta:
        model = Customer
        fields = [
            'customer_type', 'name', 'name_ar', 'email', 'phone', 'mobile',
            'website', 'tax_id', 'tax_number', 'assigned_to', 'is_active',
            'billing_address', 'billing_city', 'billing_state',
            'billing_country', 'billing_postal_code',
            'shipping_address', 'shipping_city', 'shipping_state',
            'shipping_country', 'shipping_postal_code',
            'credit_limit', 'currency', 'payment_terms', 'notes',
        ]
        widgets = {
            'billing_address': forms.Textarea(attrs={'rows': 2}),
            'shipping_address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class InvoiceForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Invoice model."""
    
    class Meta:
        model = Invoice
        fields = [
            'customer', 'invoice_type', 'invoice_date', 'due_date', 
            'reference', 'currency', 'status', 'notes', 'terms'
        ]
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'terms': forms.Textarea(attrs={'rows': 3}),
        }


class InvoiceLineForm(BootstrapFormMixin, forms.ModelForm):
    """Form for InvoiceLine model."""
    
    class Meta:
        model = InvoiceLine
        fields = ['product', 'service_pricing', 'description', 'quantity', 'unit_price', 'discount_percent', 'tax_rate']


InvoiceLineFormSet = forms.inlineformset_factory(
    Invoice, InvoiceLine,
    form=InvoiceLineForm,
    extra=1,
    can_delete=True
)


class PaymentForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Payment model."""
    
    class Meta:
        model = Payment
        fields = [
            'customer', 'payment_type', 'payment_date', 'payment_method',
            'amount', 'currency', 'reference_number', 'notes'
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ExpenseForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Expense model."""
    
    class Meta:
        model = Expense
        fields = [
            'category', 'supplier', 'employee', 'description', 'expense_date',
            'amount', 'tax_amount', 'currency', 'payment_method', 
            'payment_reference', 'status', 'notes'
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


# =============================================================================
# Supplier Forms
# =============================================================================

class SupplierForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Supplier model."""
    
    class Meta:
        model = Supplier
        fields = [
            'supplier_type', 'name', 'name_ar', 'trading_name', 'email', 'phone',
            'mobile', 'website', 'contact_person', 'contact_position', 
            'contact_email', 'contact_phone', 'address', 'city', 'country',
            'postal_code', 'tax_number', 'registration_number', 'bank_name',
            'bank_account_name', 'bank_account_number', 'bank_iban', 'bank_swift',
            'currency', 'payment_terms', 'credit_limit', 'rating', 'notes', 'is_active'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class SupplierContactForm(BootstrapFormMixin, forms.ModelForm):
    """Form for SupplierContact model."""
    
    class Meta:
        model = SupplierContact
        fields = ['name', 'position', 'department', 'email', 'phone', 'mobile', 'is_primary', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


SupplierContactFormSet = forms.inlineformset_factory(
    Supplier, SupplierContact,
    form=SupplierContactForm,
    extra=1,
    can_delete=True
)


class PurchaseOrderForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for PurchaseOrder model."""
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier', 'po_date', 'expected_date', 'reference',
            'currency', 'status', 'notes', 'terms'
        ]
        widgets = {
            'po_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'terms': forms.Textarea(attrs={'rows': 3}),
        }


class PurchaseOrderLineForm(BootstrapFormMixin, forms.ModelForm):
    """Form for PurchaseOrderLine model."""
    
    class Meta:
        model = PurchaseOrderLine
        fields = ['product', 'description', 'quantity', 'unit_price', 'tax_rate']


PurchaseOrderLineFormSet = forms.inlineformset_factory(
    PurchaseOrder, PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    extra=1,
    can_delete=True
)


# =============================================================================
# CRM Forms
# =============================================================================

class LeadForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Lead model."""
    
    class Meta:
        model = Lead
        fields = [
            'title', 'first_name', 'last_name', 'email', 'phone', 'mobile',
            'company_name', 'job_title', 'address', 'city', 'country',
            'source', 'status', 'service_interest',
            'estimated_value', 'expected_close_date', 'probability',
            'assigned_to', 'notes'
        ]
        widgets = {
            'expected_close_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class LeadActivityForm(BootstrapFormMixin, forms.ModelForm):
    """Form for LeadActivity model."""
    
    class Meta:
        model = LeadActivity
        fields = ['activity_type', 'subject', 'description', 'activity_date', 'is_completed']
        widgets = {
            'activity_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class CustomerInteractionForm(BootstrapFormMixin, forms.ModelForm):
    """Form for CustomerInteraction model."""
    
    class Meta:
        model = CustomerInteraction
        fields = [
            'interaction_type', 'subject', 'description', 'interaction_date',
            'requires_follow_up', 'follow_up_date', 'follow_up_notes'
        ]
        widgets = {
            'interaction_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'follow_up_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'follow_up_notes': forms.Textarea(attrs={'rows': 2}),
        }


class CampaignForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Campaign model."""
    
    class Meta:
        model = Campaign
        fields = [
            'name', 'campaign_type', 'status', 'start_date', 'end_date',
            'target_audience', 'currency', 'budget', 'expected_leads',
            'expected_revenue', 'description', 'owner'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'target_audience': forms.Textarea(attrs={'rows': 2}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class TaskForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Task model."""
    
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'priority', 'status',
            'assigned_to', 'due_date', 'related_customer', 'related_lead',
            'reminder_date'
        ]
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'reminder_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class TaskCommentForm(BootstrapFormMixin, forms.ModelForm):
    """Form for TaskComment model."""
    
    class Meta:
        model = TaskComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add a comment...'}),
        }


# =============================================================================
# Service Forms
# =============================================================================

class ServiceCategoryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for ServiceCategory model."""
    
    class Meta:
        model = ServiceCategory
        fields = ['name', 'name_ar', 'code', 'description', 'parent', 'is_active', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class ServicePricingForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for ServicePricing model."""
    
    class Meta:
        model = ServicePricing
        fields = [
            'name', 'name_ar', 'code', 'website_service_name', 'category',
            'description', 'pricing_type', 'currency', 'base_price', 'cost_price',
            'tax_rate', 'is_tax_inclusive', 'agent_commission_percent', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class QuoteForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Quote model."""
    
    class Meta:
        model = Quote
        fields = [
            'customer', 'lead', 'quote_date', 'valid_until', 'reference',
            'currency', 'discount_percent', 'status', 'notes', 'terms',
            'prepared_by'
        ]
        widgets = {
            'quote_date': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'terms': forms.Textarea(attrs={'rows': 4}),
        }


class QuoteLineForm(BootstrapFormMixin, forms.ModelForm):
    """Form for QuoteLine model."""
    
    class Meta:
        model = QuoteLine
        fields = ['service_pricing', 'description', 'quantity', 'unit_price', 'discount_percent', 'tax_rate']


QuoteLineFormSet = forms.inlineformset_factory(
    Quote, QuoteLine,
    form=QuoteLineForm,
    extra=1,
    can_delete=True
)


# =============================================================================
# Financial Configuration Forms
# =============================================================================

from .models import Account, TaxRate, PaymentMethod, ExpenseCategory
from .models import Currency, FiscalYear


class AccountForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Account (Chart of Accounts) model."""
    
    class Meta:
        model = Account
        fields = [
            'code', 'name', 'name_ar', 'account_type', 'parent',
            'description', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class TaxRateForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for TaxRate model."""
    
    class Meta:
        model = TaxRate
        fields = ['name', 'name_ar', 'rate', 'is_default', 'is_active']


class PaymentMethodForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for PaymentMethod model."""
    
    class Meta:
        model = PaymentMethod
        fields = ['name', 'name_ar', 'code', 'is_active', 'requires_reference', 'account']


class ExpenseCategoryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for ExpenseCategory model."""
    
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'name_ar', 'code', 'parent', 'account', 'is_active']


class CurrencyForm(BootstrapFormMixin, forms.ModelForm):
    """Form for Currency model."""
    
    class Meta:
        model = Currency
        fields = ['code', 'name', 'name_ar', 'symbol', 'exchange_rate', 'is_active']


class FiscalYearForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for FiscalYear model."""
    
    class Meta:
        model = FiscalYear
        fields = ['name', 'start_date', 'end_date', 'is_current', 'is_closed']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class JournalEntryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """نموذج قيد اليومية"""
    
    class Meta:
        model = JournalEntry
        fields = ['entry_number', 'entry_date', 'entry_type', 'description', 'reference', 'fiscal_year']
        widgets = {
            'entry_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'entry_number': 'رقم القيد',
            'entry_date': 'التاريخ',
            'entry_type': 'نوع القيد',
            'description': 'البيان',
            'reference': 'المرجع',
            'fiscal_year': 'السنة المالية',
        }


class JournalEntryLineForm(BootstrapFormMixin, forms.ModelForm):
    """نموذج سطر قيد اليومية"""
    
    class Meta:
        model = JournalEntryLine
        fields = ['account', 'description', 'debit_amount', 'credit_amount']
        labels = {
            'account': 'الحساب',
            'description': 'البيان',
            'debit_amount': 'مدين',
            'credit_amount': 'دائن',
        }
    
    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company:
            self.fields['account'].queryset = Account.objects.filter(company=company, is_active=True).order_by('code')


class BaseJournalEntryLineFormSet(forms.BaseInlineFormSet):
    """FormSet أساسي لأسطر قيود اليومية مع دعم فلترة الشركة"""
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
    
    def _construct_form(self, i, **kwargs):
        kwargs['company'] = self.company
        return super()._construct_form(i, **kwargs)


JournalEntryLineFormSet = forms.inlineformset_factory(
    JournalEntry,
    JournalEntryLine,
    form=JournalEntryLineForm,
    formset=BaseJournalEntryLineFormSet,
    extra=4,
    can_delete=True,
    min_num=2,
    validate_min=True,
)


# =============================================================================
# Product Forms
# =============================================================================

class ProductCategoryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for ProductCategory model."""

    class Meta:
        model = ProductCategory
        fields = ['name', 'name_ar', 'code', 'description', 'parent', 'is_active', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class ProductForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Product model."""

    class Meta:
        model = Product
        fields = [
            'sku', 'barcode', 'name', 'name_ar', 'description', 'image',
            'product_type', 'category', 'currency',
            'selling_price', 'cost_price', 'min_selling_price', 'tax_rate',
            'track_inventory', 'quantity_on_hand', 'reorder_level',
            'reorder_quantity', 'unit_of_measure',
            'supplier', 'supplier_sku',
            'is_active', 'notes',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ProductSupplierForm(BootstrapFormMixin, forms.ModelForm):
    """Form for ProductSupplier (additional suppliers per product)."""

    class Meta:
        model = ProductSupplier
        fields = [
            'supplier', 'supplier_sku', 'supplier_price', 'currency',
            'lead_time_days', 'min_order_qty', 'is_preferred', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


ProductSupplierFormSet = forms.inlineformset_factory(
    Product, ProductSupplier,
    form=ProductSupplierForm,
    extra=1,
    can_delete=True,
)
