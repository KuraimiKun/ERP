"""
ERP Views Package

Re-exports every view function for backward compatibility.
Usage:  from erp.views import dashboard   (still works)
"""

# ── Shared ──────────────────────────────────────────────────────────────────
from ._common import get_user_company

# ── Export ──────────────────────────────────────────────────────────────────
from .export import export_data

# ── Import ──────────────────────────────────────────────────────────────────
from .import_data import import_upload, import_preview, import_confirm

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
    employee_permissions_update,
    department_list, department_create, department_edit, department_delete,
    attendance_list, attendance_create, attendance_edit,
    leave_request_list, leave_request_create, leave_request_detail, leave_request_approve,
    payroll_list, payroll_create, payroll_edit, payroll_detail, payroll_approve, payroll_delete,
    payroll_get_employee_salary,
)
# ── Employee Portal ─────────────────────────────────────────────
from .employee_portal import (
    employee_portal, employee_portal_attendance,
    employee_portal_profile, attendance_scan_result,
    portal_qr_scanner, portal_leave_list, portal_leave_create, portal_leave_cancel,
    portal_payslip_list, portal_payslip_detail,
    portal_profile_edit, portal_change_password,
    portal_task_list, portal_task_detail,
)

# ── Attendance Devices & Invites ────────────────────────────────
from .attendance_device import (
    device_list, device_create, device_detail, device_edit, device_delete,
    device_approve, device_revoke,
    attendance_kiosk, attendance_qr_data,
    invite_link_list, invite_link_create, invite_link_toggle,
    pending_employees, approve_employee,
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

# ── Support Tickets ─────────────────────────────────────────────────────────
from .support import (
    support_ticket_list, support_ticket_create, support_ticket_detail,
    support_ticket_reply, support_ticket_close, support_ticket_rate,
    support_ticket_reopen,
)

# ── Fixed Assets ────────────────────────────────────────────────────────────
from .fixed_assets import (
    asset_category_list, asset_category_create, asset_category_edit, asset_category_delete,
    asset_list, asset_detail, asset_create, asset_edit, asset_delete, asset_activate,
    depreciation_list, depreciation_generate, depreciation_post, depreciation_post_batch,
    disposal_list, disposal_create, disposal_detail, disposal_process,
    transfer_fa_list, transfer_fa_create,
    revaluation_list, revaluation_create, revaluation_detail, revaluation_process,
    maintenance_list, maintenance_create, maintenance_edit, maintenance_delete,
)

# ── Inventory & Warehouse ───────────────────────────────────────────────────
from .inventory import (
    warehouse_list, warehouse_detail, warehouse_create, warehouse_edit, warehouse_delete,
    zone_detail, zone_create, zone_edit, zone_delete,
    uom_list, uom_create, uom_edit, uom_delete,
    lot_list, lot_create, lot_edit, lot_delete,
    serial_list, serial_create, serial_edit,
    grn_list, grn_detail, grn_create, grn_edit, grn_confirm, grn_delete,
    transfer_list, transfer_detail, transfer_create, transfer_edit,
    transfer_ship, transfer_receive, transfer_delete,
    adjustment_list, adjustment_detail, adjustment_create, adjustment_edit,
    adjustment_approve, adjustment_delete,
    cycle_count_list, cycle_count_detail, cycle_count_create, cycle_count_edit,
    cycle_count_complete, cycle_count_delete,
    pick_list_list, pick_list_detail, pick_list_create, pick_list_edit,
    pick_list_complete, pick_list_delete,
    shipment_list, shipment_detail, shipment_create, shipment_edit,
    shipment_ship, shipment_delete,
    reorder_rule_list, reorder_rule_create, reorder_rule_edit, reorder_rule_delete,
    reorder_suggestions,
    stock_movement_list, stock_levels, valuation_config,
)

# ── POS ────────────────────────────────────────────────────────────────────
from .pos import (
    pos_terminal_select, pos_session_open, pos_main,
    pos_session_close, pos_order_history, pos_order_receipt,
    pos_generate_invoice,
    pos_api_products, pos_api_categories, pos_api_customers,
    pos_api_create_order, pos_api_complete_order,
    # Admin views
    pos_terminal_list, pos_terminal_create, pos_terminal_detail,
    pos_terminal_edit, pos_terminal_delete,
    pos_session_list, pos_session_detail_admin,
    pos_order_list, pos_order_detail_admin,
)

# ── Report Builder ──────────────────────────────────────────────────────────
from .report_builder import (
    report_builder_list, report_builder_create, report_builder_edit,
    report_builder_save, report_builder_delete,
    report_builder_preview, report_builder_generate,
    generated_report_list, generated_report_status,
)
