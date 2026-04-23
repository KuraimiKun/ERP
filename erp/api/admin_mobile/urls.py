"""URL configuration for the admin mobile API.

Mounted by ``erpproject.urls`` at ``/api/mobile/admin/v1/``.  Keeping an
explicit ``v1/`` segment from day one means future breaking changes can
ship at ``/api/mobile/admin/v2/`` without disturbing existing clients.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import auth as auth_views
from .views import dashboard as dashboard_views
from .views import approvals as approval_views
from .views import masters as masters_views
from .views import reports as report_views
from .views import misc as misc_views

app_name = "admin_mobile"

router = DefaultRouter()

# Approvals — pending queues + approve/reject actions
router.register(r"leaves/pending", approval_views.PendingLeavesViewSet, basename="leaves-pending")
router.register(r"expenses/pending", approval_views.PendingExpensesViewSet, basename="expenses-pending")
router.register(
    r"purchase-orders/pending", approval_views.PendingPurchaseOrdersViewSet, basename="purchase-orders-pending"
)
router.register(r"quotes/pending", approval_views.PendingQuotesViewSet, basename="quotes-pending")
router.register(
    r"supplier-invoices/pending", approval_views.PendingSupplierInvoicesViewSet, basename="supplier-invoices-pending"
)

# Masters — HR
router.register(r"employees", masters_views.EmployeeViewSet, basename="employees")
router.register(r"departments", masters_views.DepartmentViewSet, basename="departments")
router.register(r"branches", masters_views.BranchViewSet, basename="branches")
router.register(r"attendance", masters_views.AttendanceViewSet, basename="attendance")
router.register(r"leave-requests", masters_views.LeaveRequestViewSet, basename="leave-requests")
router.register(r"payroll", masters_views.PayrollViewSet, basename="payroll")

# Masters — Finance
router.register(r"customers", masters_views.CustomerViewSet, basename="customers")
router.register(r"invoices", masters_views.InvoiceViewSet, basename="invoices")
router.register(r"payments", masters_views.PaymentViewSet, basename="payments")
router.register(r"expenses", masters_views.ExpenseViewSet, basename="expenses")
router.register(r"accounts", masters_views.AccountReadOnlyViewSet, basename="accounts")
router.register(r"tax-rates", masters_views.TaxRateReadOnlyViewSet, basename="tax-rates")

# Masters — Supplier
router.register(r"suppliers", masters_views.SupplierViewSet, basename="suppliers")
router.register(r"purchase-orders", masters_views.PurchaseOrderViewSet, basename="purchase-orders")
router.register(r"supplier-invoices", masters_views.SupplierInvoiceViewSet, basename="supplier-invoices")
router.register(r"supplier-payments", masters_views.SupplierPaymentViewSet, basename="supplier-payments")

# Masters — Inventory
router.register(r"warehouses", masters_views.WarehouseViewSet, basename="warehouses")
router.register(r"products", masters_views.ProductViewSet, basename="products")
router.register(r"stock-items", masters_views.StockItemReadOnlyViewSet, basename="stock-items")
router.register(r"stock-movements", masters_views.StockMovementReadOnlyViewSet, basename="stock-movements")
router.register(r"goods-receipts", masters_views.GoodsReceiptViewSet, basename="goods-receipts")
router.register(r"stock-adjustments", masters_views.StockAdjustmentViewSet, basename="stock-adjustments")

# Masters — POS
router.register(r"pos/terminals", masters_views.POSTerminalViewSet, basename="pos-terminals")
router.register(r"pos/sessions", masters_views.POSSessionViewSet, basename="pos-sessions")
router.register(r"pos/orders", masters_views.POSOrderReadOnlyViewSet, basename="pos-orders")

# Masters — CRM
router.register(r"leads", masters_views.LeadViewSet, basename="leads")
router.register(r"lead-activities", masters_views.LeadActivityViewSet, basename="lead-activities")
router.register(r"customer-interactions", masters_views.CustomerInteractionViewSet, basename="customer-interactions")
router.register(r"tasks", masters_views.TaskViewSet, basename="tasks")
router.register(r"campaigns", masters_views.CampaignViewSet, basename="campaigns")

# Masters — Services
router.register(r"quotes", masters_views.QuoteViewSet, basename="quotes")
router.register(r"service-pricing", masters_views.ServicePricingReadOnlyViewSet, basename="service-pricing")

# Notifications / audit / settings / search
router.register(r"notifications", misc_views.NotificationViewSet, basename="notifications")
router.register(r"audit-logs", misc_views.AuditLogViewSet, basename="audit-logs")
router.register(r"fiscal-years", misc_views.FiscalYearReadOnlyViewSet, basename="fiscal-years")
router.register(r"currencies", misc_views.CurrencyReadOnlyViewSet, basename="currencies")


urlpatterns = [
    # ── Auth & session ────────────────────────────────────────────────
    path("auth/login/", auth_views.admin_login, name="auth-login"),
    path("auth/logout/", auth_views.admin_logout, name="auth-logout"),
    path("auth/me/", auth_views.admin_me, name="auth-me"),
    path("auth/change-password/", auth_views.admin_change_password, name="auth-change-password"),
    path("devices/register/", auth_views.admin_device_register, name="devices-register"),
    # ── Dashboard ─────────────────────────────────────────────────────
    path("dashboard/", dashboard_views.dashboard_summary, name="dashboard"),
    path("dashboard/activity/", dashboard_views.dashboard_activity, name="dashboard-activity"),
    path("dashboard/kpis/", dashboard_views.dashboard_kpis, name="dashboard-kpis"),
    # ── Reports ───────────────────────────────────────────────────────
    path("reports/trial-balance/", report_views.TrialBalanceView.as_view(), name="reports-trial-balance"),
    path("reports/profit-and-loss/", report_views.ProfitAndLossView.as_view(), name="reports-profit-and-loss"),
    path("reports/balance-sheet/", report_views.BalanceSheetView.as_view(), name="reports-balance-sheet"),
    path("reports/cash-flow/", report_views.CashFlowView.as_view(), name="reports-cash-flow"),
    path("reports/sales-summary/", report_views.SalesSummaryView.as_view(), name="reports-sales-summary"),
    path("reports/top-products/", report_views.TopProductsView.as_view(), name="reports-top-products"),
    path("reports/top-customers/", report_views.TopCustomersView.as_view(), name="reports-top-customers"),
    path("reports/aging-receivables/", report_views.AgingReceivablesView.as_view(), name="reports-aging-receivables"),
    path("reports/aging-payables/", report_views.AgingPayablesView.as_view(), name="reports-aging-payables"),
    # ── Settings ──────────────────────────────────────────────────────
    path("company/", misc_views.company_detail, name="company-detail"),
    path("company/feature-flags/", misc_views.feature_flags, name="company-feature-flags"),
    # ── Search ────────────────────────────────────────────────────────
    path("search/", misc_views.search, name="search"),
    # ── Routers (CRUD + approvals) ────────────────────────────────────
    path("", include(router.urls)),
]
