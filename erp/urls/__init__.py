"""
ERP URL Configuration Package

Combines domain-specific URL modules into a single urlpatterns list.
"""

from django.urls import path, include

from erp import views
from erp import setup_views

app_name = 'erp'

# ── Setup Wizard ────────────────────────────────────────────────────────────
_setup_patterns = [
    path('setup/', setup_views.setup_wizard, name='setup_wizard'),
    path('setup/currency/', setup_views.setup_step_currency, name='setup_step_currency'),
    path('setup/company/', setup_views.setup_step_company, name='setup_step_company'),
    path('setup/fiscal-year/', setup_views.setup_step_fiscal_year, name='setup_step_fiscal_year'),
    path('setup/tax/', setup_views.setup_step_tax, name='setup_step_tax'),
    path('setup/payment-methods/', setup_views.setup_step_payment_methods, name='setup_step_payment_methods'),
    path('setup/chart/', setup_views.setup_step_chart, name='setup_step_chart'),
    path('setup/review/', setup_views.setup_step_review, name='setup_step_review'),
    path('setup/go-back/<int:step>/', setup_views.setup_go_back, name='setup_go_back'),
]

# ── Dashboard ───────────────────────────────────────────────────────────────
_dashboard_patterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/charts/', views.dashboard_charts_data, name='dashboard_charts'),
]

# ── Customers ───────────────────────────────────────────────────────────────
_customer_patterns = [
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
]

# ── Finance ─────────────────────────────────────────────────────────────────
_finance_patterns = [
    # Invoices
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/add/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/edit/', views.invoice_edit, name='invoice_edit'),
    path('invoices/<int:pk>/delete/', views.invoice_delete, name='invoice_delete'),
    # Payments
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/add/', views.payment_create, name='payment_create'),
    path('payments/<int:pk>/', views.payment_detail, name='payment_detail'),
    path('payments/<int:pk>/delete/', views.payment_delete, name='payment_delete'),
    # Expenses
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/add/', views.expense_create, name='expense_create'),
    path('expenses/<int:pk>/edit/', views.expense_edit, name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    # Quotes
    path('quotes/', views.quote_list, name='quote_list'),
    path('quotes/add/', views.quote_create, name='quote_create'),
    path('quotes/<int:pk>/', views.quote_detail, name='quote_detail'),
    path('quotes/<int:pk>/edit/', views.quote_edit, name='quote_edit'),
    path('quotes/<int:pk>/delete/', views.quote_delete, name='quote_delete'),
    # Accounts
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/add/', views.account_create, name='account_create'),
    path('accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('accounts/<int:pk>/delete/', views.account_delete, name='account_delete'),
    # Tax Rates
    path('tax-rates/', views.tax_rate_list, name='tax_rate_list'),
    path('tax-rates/add/', views.tax_rate_create, name='tax_rate_create'),
    path('tax-rates/<int:pk>/edit/', views.tax_rate_edit, name='tax_rate_edit'),
    path('tax-rates/<int:pk>/delete/', views.tax_rate_delete, name='tax_rate_delete'),
    # Payment Methods
    path('payment-methods/', views.payment_method_list, name='payment_method_list'),
    path('payment-methods/add/', views.payment_method_create, name='payment_method_create'),
    path('payment-methods/<int:pk>/edit/', views.payment_method_edit, name='payment_method_edit'),
    path('payment-methods/<int:pk>/delete/', views.payment_method_delete, name='payment_method_delete'),
    # Expense Categories
    path('expense-categories/', views.expense_category_list, name='expense_category_list'),
    path('expense-categories/add/', views.expense_category_create, name='expense_category_create'),
    path('expense-categories/<int:pk>/edit/', views.expense_category_edit, name='expense_category_edit'),
    path('expense-categories/<int:pk>/delete/', views.expense_category_delete, name='expense_category_delete'),
    # Currencies
    path('currencies/', views.currency_list, name='currency_list'),
    path('currencies/add/', views.currency_create, name='currency_create'),
    path('currencies/<int:pk>/edit/', views.currency_edit, name='currency_edit'),
    path('currencies/<int:pk>/delete/', views.currency_delete, name='currency_delete'),
    # Fiscal Years
    path('fiscal-years/', views.fiscal_year_list, name='fiscal_year_list'),
    path('fiscal-years/add/', views.fiscal_year_create, name='fiscal_year_create'),
    path('fiscal-years/<int:pk>/edit/', views.fiscal_year_edit, name='fiscal_year_edit'),
    path('fiscal-years/<int:pk>/delete/', views.fiscal_year_delete, name='fiscal_year_delete'),
    # Account Detail
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
    # Financial Reports
    path('finance/reports/', views.financial_reports, name='financial_reports'),
    path('finance/trial-balance/', views.trial_balance, name='trial_balance'),
    path('finance/profit-and-loss/', views.profit_and_loss, name='profit_and_loss'),
    path('finance/balance-sheet/', views.balance_sheet, name='balance_sheet'),
    path('finance/cash-flow/', views.cash_flow, name='cash_flow'),
    path('finance/aging-receivables/', views.aging_receivables, name='aging_receivables'),
    path('finance/aging-payables/', views.aging_payables, name='aging_payables'),
]

# ── HR ──────────────────────────────────────────────────────────────────────
_hr_patterns = [
    # Employees
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),
    path('employees/<int:pk>/permissions/', views.employee_permissions_update, name='employee_permissions_update'),
    # Departments
    path('departments/', views.department_list, name='department_list'),
    path('departments/add/', views.department_create, name='department_create'),
    path('departments/<int:pk>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:pk>/delete/', views.department_delete, name='department_delete'),
    # Attendance
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/add/', views.attendance_create, name='attendance_create'),
    path('attendance/<int:pk>/edit/', views.attendance_edit, name='attendance_edit'),
    # Leave Requests
    path('leave-requests/', views.leave_request_list, name='leave_request_list'),
    path('leave-requests/add/', views.leave_request_create, name='leave_request_create'),
    path('leave-requests/<int:pk>/', views.leave_request_detail, name='leave_request_detail'),
    path('leave-requests/<int:pk>/approve/', views.leave_request_approve, name='leave_request_approve'),
    # Payroll
    path('payroll/', views.payroll_list, name='payroll_list'),
    path('payroll/add/', views.payroll_create, name='payroll_create'),
    path('payroll/<int:pk>/', views.payroll_detail, name='payroll_detail'),
    path('payroll/<int:pk>/edit/', views.payroll_edit, name='payroll_edit'),
    path('payroll/<int:pk>/approve/', views.payroll_approve, name='payroll_approve'),
    path('payroll/<int:pk>/delete/', views.payroll_delete, name='payroll_delete'),
]

# ── CRM ─────────────────────────────────────────────────────────────────────
_crm_patterns = [
    # Leads
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/add/', views.lead_create, name='lead_create'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('leads/<int:pk>/edit/', views.lead_edit, name='lead_edit'),
    path('leads/<int:pk>/delete/', views.lead_delete, name='lead_delete'),
    path('leads/<int:pk>/activity/add/', views.lead_add_activity, name='lead_add_activity'),
    # Campaigns
    path('campaigns/', views.campaign_list, name='campaign_list'),
    path('campaigns/add/', views.campaign_create, name='campaign_create'),
    path('campaigns/<int:pk>/', views.campaign_detail, name='campaign_detail'),
    path('campaigns/<int:pk>/edit/', views.campaign_edit, name='campaign_edit'),
    path('campaigns/<int:pk>/delete/', views.campaign_delete, name='campaign_delete'),
    # Tasks
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/add/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/comment/add/', views.task_add_comment, name='task_add_comment'),
]

# ── Suppliers ───────────────────────────────────────────────────────────────
_supplier_patterns = [
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),
    # Purchase Orders
    path('purchase-orders/', views.purchase_order_list, name='purchase_order_list'),
    path('purchase-orders/add/', views.purchase_order_create, name='purchase_order_create'),
    path('purchase-orders/<int:pk>/', views.purchase_order_detail, name='purchase_order_detail'),
    path('purchase-orders/<int:pk>/edit/', views.purchase_order_edit, name='purchase_order_edit'),
    path('purchase-orders/<int:pk>/delete/', views.purchase_order_delete, name='purchase_order_delete'),
    path('purchase-orders/<int:pk>/approve/', views.purchase_order_approve, name='purchase_order_approve'),
    path('purchase-orders/<int:pk>/create-invoice/', views.purchase_order_create_invoice, name='purchase_order_create_invoice'),
    # Supplier Invoices
    path('supplier-invoices/', views.supplier_invoice_list, name='supplier_invoice_list'),
    path('supplier-invoices/add/', views.supplier_invoice_create, name='supplier_invoice_create'),
    path('supplier-invoices/<int:pk>/', views.supplier_invoice_detail, name='supplier_invoice_detail'),
    path('supplier-invoices/<int:pk>/edit/', views.supplier_invoice_edit, name='supplier_invoice_edit'),
    path('supplier-invoices/<int:pk>/delete/', views.supplier_invoice_delete, name='supplier_invoice_delete'),
    # Supplier Payments
    path('supplier-payments/', views.supplier_payment_list, name='supplier_payment_list'),
    path('supplier-payments/add/', views.supplier_payment_create, name='supplier_payment_create'),
    path('supplier-payments/<int:pk>/', views.supplier_payment_detail, name='supplier_payment_detail'),
    path('supplier-payments/<int:pk>/delete/', views.supplier_payment_delete, name='supplier_payment_delete'),
]

# ── Journal Entries ─────────────────────────────────────────────────────────
_journal_patterns = [
    path('journal-entries/', views.journal_entry_list, name='journal_entry_list'),
    path('journal-entries/add/', views.journal_entry_create, name='journal_entry_create'),
    path('journal-entries/<int:pk>/', views.journal_entry_detail, name='journal_entry_detail'),
    path('journal-entries/<int:pk>/edit/', views.journal_entry_edit, name='journal_entry_edit'),
    path('journal-entries/<int:pk>/delete/', views.journal_entry_delete, name='journal_entry_delete'),
    path('journal-entries/<int:pk>/post/', views.journal_entry_post, name='journal_entry_post'),
]

# ── Products & Services ────────────────────────────────────────────────────
_product_patterns = [
    path('product-categories/', views.product_category_list, name='product_category_list'),
    path('product-categories/add/', views.product_category_create, name='product_category_create'),
    path('product-categories/<int:pk>/edit/', views.product_category_edit, name='product_category_edit'),
    path('product-categories/<int:pk>/delete/', views.product_category_delete, name='product_category_delete'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('service-categories/', views.service_category_list, name='service_category_list'),
    path('service-categories/add/', views.service_category_create, name='service_category_create'),
    path('service-categories/<int:pk>/edit/', views.service_category_edit, name='service_category_edit'),
    path('service-categories/<int:pk>/delete/', views.service_category_delete, name='service_category_delete'),
    path('services/', views.service_list, name='service_list'),
    path('services/add/', views.service_create, name='service_create'),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),
    path('services/<int:pk>/edit/', views.service_edit, name='service_edit'),
    path('services/<int:pk>/delete/', views.service_delete, name='service_delete'),
]

# ── API ─────────────────────────────────────────────────────────────────────
_api_patterns = [
    path('api/', include('erp.api.urls')),
]

# ── AJAX helpers ────────────────────────────────────────────────────────────
_ajax_patterns = [
    path('ajax/item-price/', views.ajax_item_price, name='ajax_item_price'),
    path('ajax/payroll-employee-salary/', views.payroll_get_employee_salary, name='payroll_get_employee_salary'),
]

# ── Employee Portal (self-service for role='user') ──────────────────────────
_employee_portal_patterns = [
    path('portal/', views.employee_portal, name='employee_portal'),
    path('portal/attendance/', views.employee_portal_attendance, name='employee_portal_attendance'),
    path('portal/profile/', views.employee_portal_profile, name='employee_portal_profile'),
    path('portal/profile/edit/', views.portal_profile_edit, name='employee_portal_profile_edit'),
    path('portal/password/', views.portal_change_password, name='employee_portal_change_password'),
    path('portal/qr-scanner/', views.portal_qr_scanner, name='employee_portal_qr_scanner'),
    path('portal/leaves/', views.portal_leave_list, name='employee_portal_leave_list'),
    path('portal/leaves/new/', views.portal_leave_create, name='employee_portal_leave_create'),
    path('portal/leaves/<int:pk>/cancel/', views.portal_leave_cancel, name='employee_portal_leave_cancel'),
    path('portal/payslips/', views.portal_payslip_list, name='employee_portal_payslip_list'),
    path('portal/payslips/<int:pk>/', views.portal_payslip_detail, name='employee_portal_payslip_detail'),
    path('portal/tasks/', views.portal_task_list, name='employee_portal_task_list'),
    path('portal/tasks/<int:pk>/', views.portal_task_detail, name='employee_portal_task_detail'),
    path('attendance/scan/', views.attendance_scan_result, name='attendance_scan_result'),
]

# ── Attendance Devices & Kiosk (owner/admin) ────────────────────────────────
_device_patterns = [
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.device_create, name='device_create'),
    path('devices/<int:pk>/', views.device_detail, name='device_detail'),
    path('devices/<int:pk>/edit/', views.device_edit, name='device_edit'),
    path('devices/<int:pk>/delete/', views.device_delete, name='device_delete'),
    path('devices/<int:pk>/approve/', views.device_approve, name='device_approve'),
    path('devices/<int:pk>/revoke/', views.device_revoke, name='device_revoke'),
    path('attendance/kiosk/<uuid:device_id>/', views.attendance_kiosk, name='attendance_kiosk'),
    path('api/attendance/qr/<uuid:device_id>/', views.attendance_qr_data, name='attendance_qr_data'),
]

# ── Employee Invite Links & Approvals (owner/admin) ────────────────────────
_invite_approval_patterns = [
    path('invite-links/', views.invite_link_list, name='invite_link_list'),
    path('invite-links/create/', views.invite_link_create, name='invite_link_create'),
    path('invite-links/<uuid:pk>/toggle/', views.invite_link_toggle, name='invite_link_toggle'),
    path('employees/pending/', views.pending_employees, name='pending_employees'),
    path('employees/pending/<int:pk>/approve/', views.approve_employee, name='approve_employee'),
]

# ── PDF ─────────────────────────────────────────────────────────────────────
_pdf_patterns = [
    path('invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('quotes/<int:pk>/pdf/', views.quote_pdf, name='quote_pdf'),
    path('purchase-orders/<int:pk>/pdf/', views.purchase_order_pdf, name='purchase_order_pdf'),
    path('payroll/<int:pk>/pdf/', views.payslip_pdf, name='payslip_pdf'),
]

# ── Conversions ─────────────────────────────────────────────────────────────
_conversion_patterns = [
    path('quotes/<int:pk>/convert/', views.quote_convert_to_invoice, name='quote_convert_to_invoice'),
    path('leads/<int:pk>/convert/', views.lead_convert_to_customer, name='lead_convert_to_customer'),
]

# ── Credit / Debit Notes ───────────────────────────────────────────────────
_credit_debit_patterns = [
    path('invoices/<int:pk>/credit-note/', views.credit_note_create, name='credit_note_create'),
    path('invoices/<int:pk>/debit-note/', views.debit_note_create, name='debit_note_create'),
]

# ── Tax Report ──────────────────────────────────────────────────────────────
_tax_report_patterns = [
    path('finance/tax-report/', views.tax_report, name='tax_report'),
]

# ── Notifications ───────────────────────────────────────────────────────────
_notification_patterns = [
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/dropdown/', views.notification_dropdown, name='notification_dropdown'),
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification_mark_all_read'),
]

# ── Audit Log ───────────────────────────────────────────────────────────────
_audit_log_patterns = [
    path('audit-log/', views.audit_log_list, name='audit_log_list'),
]

# ── Inventory & Warehouse ──────────────────────────────────────────────────
_inventory_patterns = [
    # Warehouses
    path('warehouses/', views.warehouse_list, name='warehouse_list'),
    path('warehouses/add/', views.warehouse_create, name='warehouse_create'),
    path('warehouses/<int:pk>/', views.warehouse_detail, name='warehouse_detail'),
    path('warehouses/<int:pk>/edit/', views.warehouse_edit, name='warehouse_edit'),
    path('warehouses/<int:pk>/delete/', views.warehouse_delete, name='warehouse_delete'),
    # Warehouse Zones
    path('warehouses/<int:warehouse_pk>/zones/add/', views.zone_create, name='zone_create'),
    path('zones/<int:pk>/', views.zone_detail, name='zone_detail'),
    path('zones/<int:pk>/edit/', views.zone_edit, name='zone_edit'),
    path('zones/<int:pk>/delete/', views.zone_delete, name='zone_delete'),
    # Units of Measure
    path('uom/', views.uom_list, name='uom_list'),
    path('uom/add/', views.uom_create, name='uom_create'),
    path('uom/<int:pk>/edit/', views.uom_edit, name='uom_edit'),
    path('uom/<int:pk>/delete/', views.uom_delete, name='uom_delete'),
    # Lots / Batches
    path('lots/', views.lot_list, name='lot_list'),
    path('lots/add/', views.lot_create, name='lot_create'),
    path('lots/<int:pk>/edit/', views.lot_edit, name='lot_edit'),
    path('lots/<int:pk>/delete/', views.lot_delete, name='lot_delete'),
    # Serial Numbers
    path('serials/', views.serial_list, name='serial_list'),
    path('serials/add/', views.serial_create, name='serial_create'),
    path('serials/<int:pk>/edit/', views.serial_edit, name='serial_edit'),
    # Goods Receipt Notes
    path('grn/', views.grn_list, name='grn_list'),
    path('grn/add/', views.grn_create, name='grn_create'),
    path('grn/<int:pk>/', views.grn_detail, name='grn_detail'),
    path('grn/<int:pk>/edit/', views.grn_edit, name='grn_edit'),
    path('grn/<int:pk>/confirm/', views.grn_confirm, name='grn_confirm'),
    path('grn/<int:pk>/delete/', views.grn_delete, name='grn_delete'),
    # Stock Transfers
    path('transfers/', views.transfer_list, name='transfer_list'),
    path('transfers/add/', views.transfer_create, name='transfer_create'),
    path('transfers/<int:pk>/', views.transfer_detail, name='transfer_detail'),
    path('transfers/<int:pk>/edit/', views.transfer_edit, name='transfer_edit'),
    path('transfers/<int:pk>/ship/', views.transfer_ship, name='transfer_ship'),
    path('transfers/<int:pk>/receive/', views.transfer_receive, name='transfer_receive'),
    path('transfers/<int:pk>/delete/', views.transfer_delete, name='transfer_delete'),
    # Stock Adjustments
    path('adjustments/', views.adjustment_list, name='adjustment_list'),
    path('adjustments/add/', views.adjustment_create, name='adjustment_create'),
    path('adjustments/<int:pk>/', views.adjustment_detail, name='adjustment_detail'),
    path('adjustments/<int:pk>/edit/', views.adjustment_edit, name='adjustment_edit'),
    path('adjustments/<int:pk>/approve/', views.adjustment_approve, name='adjustment_approve'),
    path('adjustments/<int:pk>/delete/', views.adjustment_delete, name='adjustment_delete'),
    # Cycle Counts
    path('cycle-counts/', views.cycle_count_list, name='cycle_count_list'),
    path('cycle-counts/add/', views.cycle_count_create, name='cycle_count_create'),
    path('cycle-counts/<int:pk>/', views.cycle_count_detail, name='cycle_count_detail'),
    path('cycle-counts/<int:pk>/edit/', views.cycle_count_edit, name='cycle_count_edit'),
    path('cycle-counts/<int:pk>/complete/', views.cycle_count_complete, name='cycle_count_complete'),
    path('cycle-counts/<int:pk>/delete/', views.cycle_count_delete, name='cycle_count_delete'),
    # Pick Lists
    path('pick-lists/', views.pick_list_list, name='pick_list_list'),
    path('pick-lists/add/', views.pick_list_create, name='pick_list_create'),
    path('pick-lists/<int:pk>/', views.pick_list_detail, name='pick_list_detail'),
    path('pick-lists/<int:pk>/edit/', views.pick_list_edit, name='pick_list_edit'),
    path('pick-lists/<int:pk>/complete/', views.pick_list_complete, name='pick_list_complete'),
    path('pick-lists/<int:pk>/delete/', views.pick_list_delete, name='pick_list_delete'),
    # Shipments
    path('shipments/', views.shipment_list, name='shipment_list'),
    path('shipments/add/', views.shipment_create, name='shipment_create'),
    path('shipments/<int:pk>/', views.shipment_detail, name='shipment_detail'),
    path('shipments/<int:pk>/edit/', views.shipment_edit, name='shipment_edit'),
    path('shipments/<int:pk>/ship/', views.shipment_ship, name='shipment_ship'),
    path('shipments/<int:pk>/delete/', views.shipment_delete, name='shipment_delete'),
    # Reorder Rules
    path('reorder-rules/', views.reorder_rule_list, name='reorder_rule_list'),
    path('reorder-rules/add/', views.reorder_rule_create, name='reorder_rule_create'),
    path('reorder-rules/<int:pk>/edit/', views.reorder_rule_edit, name='reorder_rule_edit'),
    path('reorder-rules/<int:pk>/delete/', views.reorder_rule_delete, name='reorder_rule_delete'),
    path('reorder-suggestions/', views.reorder_suggestions, name='reorder_suggestions'),
    # Stock Movements (read-only ledger)
    path('stock-movements/', views.stock_movement_list, name='stock_movement_list'),
    # Stock Levels Dashboard
    path('stock-levels/', views.stock_levels, name='stock_levels'),
    # Valuation Config
    path('valuation-config/', views.valuation_config, name='valuation_config'),
]

# ── Fixed Assets ────────────────────────────────────────────────────────────
_fixed_assets_patterns = [
    # Asset Categories
    path('asset-categories/', views.asset_category_list, name='asset_category_list'),
    path('asset-categories/add/', views.asset_category_create, name='asset_category_create'),
    path('asset-categories/<int:pk>/edit/', views.asset_category_edit, name='asset_category_edit'),
    path('asset-categories/<int:pk>/delete/', views.asset_category_delete, name='asset_category_delete'),
    # Asset Register
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/add/', views.asset_create, name='asset_create'),
    path('assets/<int:pk>/', views.asset_detail, name='asset_detail'),
    path('assets/<int:pk>/edit/', views.asset_edit, name='asset_edit'),
    path('assets/<int:pk>/delete/', views.asset_delete, name='asset_delete'),
    path('assets/<int:pk>/activate/', views.asset_activate, name='asset_activate'),
    # Depreciation
    path('depreciation/', views.depreciation_list, name='depreciation_list'),
    path('assets/<int:pk>/depreciation/generate/', views.depreciation_generate, name='depreciation_generate'),
    path('depreciation/<int:pk>/post/', views.depreciation_post, name='depreciation_post'),
    path('depreciation/post-batch/', views.depreciation_post_batch, name='depreciation_post_batch'),
    # Disposals
    path('disposals/', views.disposal_list, name='disposal_list'),
    path('assets/<int:pk>/dispose/', views.disposal_create, name='disposal_create'),
    path('disposals/<int:pk>/', views.disposal_detail, name='disposal_detail'),
    path('disposals/<int:pk>/process/', views.disposal_process, name='disposal_process'),
    # Transfers (asset transfers — prefixed to avoid inventory clash)
    path('asset-transfers/', views.transfer_fa_list, name='transfer_fa_list'),
    path('assets/<int:pk>/transfer/', views.transfer_fa_create, name='transfer_fa_create'),
    # Revaluations
    path('revaluations/', views.revaluation_list, name='revaluation_list'),
    path('assets/<int:pk>/revalue/', views.revaluation_create, name='revaluation_create'),
    path('revaluations/<int:pk>/', views.revaluation_detail, name='revaluation_detail'),
    path('revaluations/<int:pk>/process/', views.revaluation_process, name='revaluation_process'),
    # Maintenance
    path('asset-maintenance/', views.maintenance_list, name='maintenance_list'),
    path('assets/<int:pk>/maintenance/add/', views.maintenance_create, name='maintenance_create'),
    path('asset-maintenance/<int:pk>/edit/', views.maintenance_edit, name='maintenance_edit'),
    path('asset-maintenance/<int:pk>/delete/', views.maintenance_delete, name='maintenance_delete'),
]

# ── AI & ML ─────────────────────────────────────────────────────────────────
from erp.ai import views as ai_views

_ai_patterns = [
    path('ai/', ai_views.ai_dashboard, name='ai_dashboard'),
    path('ai/insights/', ai_views.ai_insights_list, name='ai_insights_list'),
    path('ai/settings/', ai_views.ai_settings, name='ai_settings'),
    path('ai/api/', include('erp.ai.api.urls')),
]

# ── Support Tickets ─────────────────────────────────────────────────────────
_support_patterns = [
    path('support/', views.support_ticket_list, name='support_ticket_list'),
    path('support/create/', views.support_ticket_create, name='support_ticket_create'),
    path('support/<uuid:pk>/', views.support_ticket_detail, name='support_ticket_detail'),
    path('support/<uuid:pk>/reply/', views.support_ticket_reply, name='support_ticket_reply'),
    path('support/<uuid:pk>/close/', views.support_ticket_close, name='support_ticket_close'),
    path('support/<uuid:pk>/rate/', views.support_ticket_rate, name='support_ticket_rate'),
    path('support/<uuid:pk>/reopen/', views.support_ticket_reopen, name='support_ticket_reopen'),
]

# ── Combined ────────────────────────────────────────────────────────────────
urlpatterns = (
    _setup_patterns
    + _dashboard_patterns
    + _customer_patterns
    + _finance_patterns
    + _hr_patterns
    + _crm_patterns
    + _supplier_patterns
    + _journal_patterns
    + _product_patterns
    + _ajax_patterns
    + _pdf_patterns
    + _conversion_patterns
    + _credit_debit_patterns
    + _tax_report_patterns
    + _notification_patterns
    + _audit_log_patterns
    + _inventory_patterns
    + _fixed_assets_patterns
    + _employee_portal_patterns
    + _device_patterns
    + _invite_approval_patterns
    + _api_patterns
    + _ai_patterns
    + _support_patterns
)
