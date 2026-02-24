"""
ERP Views Package

Re-exports every view function for backward compatibility.
Usage:  from erp.views import dashboard   (still works)
"""

# ── Shared ──────────────────────────────────────────────────────────────────
from ._common import get_user_company

# ── Dashboard ───────────────────────────────────────────────────────────────
from .dashboard import dashboard, dashboard_charts_data

# ── Customers ───────────────────────────────────────────────────────────────
from .customers import (
    customer_list, customer_detail, customer_create, customer_edit, customer_delete,
)

# ── Finance ─────────────────────────────────────────────────────────────────
from .finance import (
    invoice_list, invoice_detail, invoice_create, invoice_edit, invoice_delete,
    payment_list, payment_create, payment_detail, payment_delete,
    expense_list, expense_create, expense_edit, expense_delete,
    account_list, account_create, account_edit, account_delete,
    tax_rate_list, tax_rate_create, tax_rate_edit, tax_rate_delete,
    payment_method_list, payment_method_create, payment_method_edit, payment_method_delete,
    expense_category_list, expense_category_create, expense_category_edit, expense_category_delete,
    currency_list, currency_create, currency_edit, currency_delete,
    fiscal_year_list, fiscal_year_create, fiscal_year_edit, fiscal_year_delete,
    financial_reports,
)

# ── HR ──────────────────────────────────────────────────────────────────────
from .hr import (
    employee_list, employee_detail, employee_create, employee_edit, employee_delete,
    department_list, department_create, department_edit, department_delete,
    attendance_list, attendance_create, attendance_edit,
    leave_request_list, leave_request_create, leave_request_detail, leave_request_approve,
    payroll_list, payroll_create, payroll_edit, payroll_detail, payroll_approve, payroll_delete,
    payroll_get_employee_salary,
)

# ── CRM ─────────────────────────────────────────────────────────────────────
from .crm import (
    lead_list, lead_detail, lead_create, lead_edit, lead_delete, lead_add_activity,
    campaign_list, campaign_detail, campaign_create, campaign_edit, campaign_delete,
    task_list, task_detail, task_create, task_edit, task_delete, task_add_comment,
)

# ── Suppliers ───────────────────────────────────────────────────────────────
from .suppliers import (
    supplier_list, supplier_detail, supplier_create, supplier_edit, supplier_delete,
    purchase_order_list, purchase_order_detail, purchase_order_create,
    purchase_order_edit, purchase_order_delete,
    purchase_order_approve, purchase_order_create_invoice,
    supplier_invoice_list, supplier_invoice_detail, supplier_invoice_create,
    supplier_invoice_edit, supplier_invoice_delete,
    supplier_payment_list, supplier_payment_detail, supplier_payment_create,
    supplier_payment_delete,
)

# ── Services & Quotes ──────────────────────────────────────────────────────
from .services import (
    quote_list, quote_detail, quote_create, quote_edit, quote_delete,
    service_category_list, service_category_create, service_category_edit, service_category_delete,
    service_list, service_detail, service_create, service_edit, service_delete,
)

# ── Products ────────────────────────────────────────────────────────────────
from .products import (
    product_category_list, product_category_create, product_category_edit, product_category_delete,
    product_list, product_detail, product_create, product_edit, product_delete,
)

# ── Journal Entries ─────────────────────────────────────────────────────────
from .journal import (
    journal_entry_list, journal_entry_create, journal_entry_detail,
    journal_entry_edit, journal_entry_delete, journal_entry_post,
)

# ── AJAX ────────────────────────────────────────────────────────────────────
from .ajax import ajax_item_price

# ── Reports ─────────────────────────────────────────────────────────────────
from .reports import (
    trial_balance, profit_and_loss, balance_sheet, cash_flow,
    aging_receivables, aging_payables, account_detail,
)

# ── PDF ─────────────────────────────────────────────────────────────────────
from .pdf import (
    invoice_pdf, quote_pdf, purchase_order_pdf, payslip_pdf,
)

# ── Conversions ─────────────────────────────────────────────────────────────
from .conversions import (
    quote_convert_to_invoice, lead_convert_to_customer,
)

# ── Credit/Debit Notes ─────────────────────────────────────────────────────
from .credit_debit import (
    credit_note_create, debit_note_create,
)

# ── Tax Report ──────────────────────────────────────────────────────────────
from .tax_report import tax_report

# ── Notifications ───────────────────────────────────────────────────────────
from .notifications import (
    notification_list, notification_dropdown,
    notification_mark_read, notification_mark_all_read,
)

# ── Audit Log ───────────────────────────────────────────────────────────────
from .audit_log import audit_log_list
