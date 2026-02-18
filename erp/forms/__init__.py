"""
ERP Forms Package

Re-exports every form class and formset for backward compatibility.
Usage:  from erp.forms import CustomerForm   (still works)
"""

# ── Mixins ──────────────────────────────────────────────────────
from .mixins import CompanyFilterMixin, BootstrapFormMixin

# ── Core ────────────────────────────────────────────────────────
from .core import CompanyForm, DepartmentForm, BranchForm, CurrencyForm, FiscalYearForm

# ── HR ──────────────────────────────────────────────────────────
from .hr import EmployeeForm, LeaveRequestForm, AttendanceForm

# ── Finance ─────────────────────────────────────────────────────
from .finance import (
    CustomerForm,
    InvoiceForm,
    InvoiceLineForm,
    InvoiceLineFormSet,
    PaymentForm,
    ExpenseForm,
    AccountForm,
    TaxRateForm,
    PaymentMethodForm,
    ExpenseCategoryForm,
)

# ── Supplier / Procurement ──────────────────────────────────────
from .supplier import (
    SupplierForm,
    SupplierContactForm,
    SupplierContactFormSet,
    PurchaseOrderForm,
    PurchaseOrderLineForm,
    PurchaseOrderLineFormSet,
)

# ── CRM ─────────────────────────────────────────────────────────
from .crm import (
    LeadForm,
    LeadActivityForm,
    CustomerInteractionForm,
    CampaignForm,
    TaskForm,
    TaskCommentForm,
)

# ── Services ────────────────────────────────────────────────────
from .services import (
    ServiceCategoryForm,
    ServicePricingForm,
    QuoteForm,
    QuoteLineForm,
    QuoteLineFormSet,
)

# ── Products ────────────────────────────────────────────────────
from .products import (
    ProductCategoryForm,
    ProductForm,
    ProductSupplierForm,
    ProductSupplierFormSet,
)

# ── Journal Entries ─────────────────────────────────────────────
from .journal import (
    JournalEntryForm,
    JournalEntryLineForm,
    BaseJournalEntryLineFormSet,
    JournalEntryLineFormSet,
)

__all__ = [
    # Mixins
    'CompanyFilterMixin', 'BootstrapFormMixin',
    # Core
    'CompanyForm', 'DepartmentForm', 'BranchForm', 'CurrencyForm', 'FiscalYearForm',
    # HR
    'EmployeeForm', 'LeaveRequestForm', 'AttendanceForm',
    # Finance
    'CustomerForm', 'InvoiceForm', 'InvoiceLineForm', 'InvoiceLineFormSet',
    'PaymentForm', 'ExpenseForm', 'AccountForm', 'TaxRateForm',
    'PaymentMethodForm', 'ExpenseCategoryForm',
    # Supplier
    'SupplierForm', 'SupplierContactForm', 'SupplierContactFormSet',
    'PurchaseOrderForm', 'PurchaseOrderLineForm', 'PurchaseOrderLineFormSet',
    # CRM
    'LeadForm', 'LeadActivityForm', 'CustomerInteractionForm',
    'CampaignForm', 'TaskForm', 'TaskCommentForm',
    # Services
    'ServiceCategoryForm', 'ServicePricingForm',
    'QuoteForm', 'QuoteLineForm', 'QuoteLineFormSet',
    # Products
    'ProductCategoryForm', 'ProductForm',
    'ProductSupplierForm', 'ProductSupplierFormSet',
    # Journal
    'JournalEntryForm', 'JournalEntryLineForm',
    'BaseJournalEntryLineFormSet', 'JournalEntryLineFormSet',
]
