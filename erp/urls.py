"""
ERP URL Configuration

URL patterns for the ERP system including dashboard views and API endpoints.
"""

from django.urls import path, include
from . import views
from . import setup_views

app_name = 'erp'

urlpatterns = [
    # =========================================================================
    # SETUP WIZARD
    # =========================================================================
    path('setup/', setup_views.setup_wizard, name='setup_wizard'),
    path('setup/currency/', setup_views.setup_step_currency, name='setup_step_currency'),
    path('setup/company/', setup_views.setup_step_company, name='setup_step_company'),
    path('setup/fiscal-year/', setup_views.setup_step_fiscal_year, name='setup_step_fiscal_year'),
    path('setup/tax/', setup_views.setup_step_tax, name='setup_step_tax'),
    path('setup/payment-methods/', setup_views.setup_step_payment_methods, name='setup_step_payment_methods'),
    path('setup/chart/', setup_views.setup_step_chart, name='setup_step_chart'),
    path('setup/review/', setup_views.setup_step_review, name='setup_step_review'),
    path('setup/go-back/<int:step>/', setup_views.setup_go_back, name='setup_go_back'),
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('dashboard/charts/', views.dashboard_charts_data, name='dashboard_charts'),
    
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
    
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
    
    # Employees
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),
    
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
    
    # Suppliers
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
    
    # Tasks
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/add/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/comment/add/', views.task_add_comment, name='task_add_comment'),
    
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
    
    # =========================================================================
    # FINANCIAL CONFIGURATION
    # =========================================================================
    
    # Chart of Accounts
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/add/', views.account_create, name='account_create'),
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
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
    
    # Financial Reports
    path('finance/reports/', views.financial_reports, name='financial_reports'),
    
    # =========================================================================
    # JOURNAL ENTRIES - القيود اليومية
    # =========================================================================
    path('journal-entries/', views.journal_entry_list, name='journal_entry_list'),
    path('journal-entries/add/', views.journal_entry_create, name='journal_entry_create'),
    path('journal-entries/<int:pk>/', views.journal_entry_detail, name='journal_entry_detail'),
    path('journal-entries/<int:pk>/edit/', views.journal_entry_edit, name='journal_entry_edit'),
    path('journal-entries/<int:pk>/delete/', views.journal_entry_delete, name='journal_entry_delete'),
    path('journal-entries/<int:pk>/post/', views.journal_entry_post, name='journal_entry_post'),
    
    # =========================================================================
    # PRODUCTS & SERVICES - المنتجات والخدمات
    # =========================================================================
    
    # Product Categories
    path('product-categories/', views.product_category_list, name='product_category_list'),
    path('product-categories/add/', views.product_category_create, name='product_category_create'),
    path('product-categories/<int:pk>/edit/', views.product_category_edit, name='product_category_edit'),
    path('product-categories/<int:pk>/delete/', views.product_category_delete, name='product_category_delete'),
    
    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    
    # Service Categories
    path('service-categories/', views.service_category_list, name='service_category_list'),
    path('service-categories/add/', views.service_category_create, name='service_category_create'),
    path('service-categories/<int:pk>/edit/', views.service_category_edit, name='service_category_edit'),
    path('service-categories/<int:pk>/delete/', views.service_category_delete, name='service_category_delete'),
    
    # Services
    path('services/', views.service_list, name='service_list'),
    path('services/add/', views.service_create, name='service_create'),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),
    path('services/<int:pk>/edit/', views.service_edit, name='service_edit'),
    path('services/<int:pk>/delete/', views.service_delete, name='service_delete'),
    
    # AJAX helpers
    path('ajax/item-price/', views.ajax_item_price, name='ajax_item_price'),
    
    # =========================================================================
    # EMPLOYEE PORTAL (self-service for role='user')
    # =========================================================================
    path('portal/', views.employee_portal, name='employee_portal'),
    path('portal/attendance/', views.employee_portal_attendance, name='employee_portal_attendance'),
    path('portal/profile/', views.employee_portal_profile, name='employee_portal_profile'),
    path('attendance/scan/', views.attendance_scan_result, name='attendance_scan_result'),
    
    # =========================================================================
    # ATTENDANCE DEVICES & KIOSK (owner/admin)
    # =========================================================================
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.device_create, name='device_create'),
    path('devices/<int:pk>/', views.device_detail, name='device_detail'),
    path('devices/<int:pk>/edit/', views.device_edit, name='device_edit'),
    path('devices/<int:pk>/delete/', views.device_delete, name='device_delete'),
    
    # Kiosk (public – no login required, secured by device UUID)
    path('attendance/kiosk/<uuid:device_id>/', views.attendance_kiosk, name='attendance_kiosk'),
    path('api/attendance/qr/<uuid:device_id>/', views.attendance_qr_data, name='attendance_qr_data'),
    
    # =========================================================================
    # EMPLOYEE INVITE LINKS & APPROVALS (owner/admin)
    # =========================================================================
    path('invite-links/', views.invite_link_list, name='invite_link_list'),
    path('invite-links/create/', views.invite_link_create, name='invite_link_create'),
    path('invite-links/<int:pk>/toggle/', views.invite_link_toggle, name='invite_link_toggle'),
    path('employees/pending/', views.pending_employees, name='pending_employees'),
    path('employees/pending/<int:pk>/approve/', views.approve_employee, name='approve_employee'),
    
    # API endpoints
    path('api/', include('erp.api.urls')),
]
