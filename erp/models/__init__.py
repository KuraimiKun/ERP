"""
ERP Models Package

This package contains all the models for the ERP system, organized by module.
"""

# Base models and mixins
from .base import (
    TimeStampedModel,
    AuditMixin,
    SoftDeleteMixin,
    SoftDeleteManager,
    ERPBaseModel,
)

# Core models
from .core import (
    Currency,
    Company,
    Department,
    Branch,
    FiscalYear,
    Sequence,
)

# HR models
from .hr import (
    Employee,
    EmployeeDocument,
    LeaveType,
    LeaveRequest,
    Attendance,
    Payroll,
)

# Finance models
from .finance import (
    Account,
    TaxRate,
    PaymentMethod,
    Customer,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentAllocation,
    Expense,
    ExpenseCategory,
    ExpenseAttachment,
    JournalEntry,
    JournalEntryLine,
)

# Supplier models
from .supplier import (
    Supplier,
    SupplierContact,
    SupplierDocument,
    PurchaseOrder,
    PurchaseOrderLine,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierPayment,
    SupplierPaymentAllocation,
)

# CRM models
from .crm import (
    Lead,
    LeadActivity,
    CustomerInteraction,
    Campaign,
    CampaignLead,
    Task,
    TaskComment,
)

# Service models
from .services import (
    ServiceCategory,
    ServicePricing,
    PriceTier,
    ServicePackage,
    PackageItem,
    Quote,
    QuoteLine,
    ProductCategory,
    Product,
    ProductSupplier,
)

# Reporting models
from .reporting import (
    ReportTemplate,
    GeneratedReport,
    Dashboard,
    DashboardWidget,
    KPI,
    KPIValue,
)

# Audit and System models
from .audit import (
    AuditLog,
    SystemSetting,
    Notification,
    EmailTemplate,
    FileAttachment,
    ScheduledTask,
    IntegrationLog,
)

__all__ = [
    # Base
    'TimeStampedModel',
    'AuditMixin',
    'SoftDeleteMixin',
    'SoftDeleteManager',
    'ERPBaseModel',
    
    # Core
    'Currency',
    'Company',
    'Department',
    'Branch',
    'FiscalYear',
    'Sequence',
    
    # HR
    'Employee',
    'EmployeeDocument',
    'LeaveType',
    'LeaveRequest',
    'Attendance',
    'Payroll',
    
    # Finance
    'Account',
    'TaxRate',
    'PaymentMethod',
    'Customer',
    'Invoice',
    'InvoiceLine',
    'Payment',
    'PaymentAllocation',
    'Expense',
    'ExpenseCategory',
    'ExpenseAttachment',
    'JournalEntry',
    'JournalEntryLine',
    
    # Supplier
    'Supplier',
    'SupplierContact',
    'SupplierDocument',
    'PurchaseOrder',
    'PurchaseOrderLine',
    'SupplierInvoice',
    'SupplierInvoiceLine',
    'SupplierPayment',
    'SupplierPaymentAllocation',
    
    # CRM
    'Lead',
    'LeadActivity',
    'CustomerInteraction',
    'Campaign',
    'CampaignLead',
    'Task',
    'TaskComment',
    
    # Services
    'ServiceCategory',
    'ServicePricing',
    'PriceTier',
    'ServicePackage',
    'PackageItem',
    'Quote',
    'QuoteLine',
    
    # Products
    'ProductCategory',
    'Product',
    'ProductSupplier',
    
    # Reporting
    'ReportTemplate',
    'GeneratedReport',
    'Dashboard',
    'DashboardWidget',
    'KPI',
    'KPIValue',
    
    # Audit
    'AuditLog',
    'SystemSetting',
    'Notification',
    'EmailTemplate',
    'FileAttachment',
    'ScheduledTask',
    'IntegrationLog',
]
