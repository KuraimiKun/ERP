"""
ERP API URL Configuration

Routes for all API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter

from .views import (
    # Core
    CurrencyViewSet,
    CompanyViewSet,
    DepartmentViewSet,
    BranchViewSet,
    FiscalYearViewSet,
    # HR
    EmployeeViewSet,
    LeaveTypeViewSet,
    LeaveRequestViewSet,
    AttendanceViewSet,
    PayrollViewSet,
    # Finance
    AccountViewSet,
    TaxRateViewSet,
    PaymentMethodViewSet,
    CustomerViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    # Supplier
    SupplierViewSet,
    SupplierContactViewSet,
    PurchaseOrderViewSet,
    # CRM
    LeadViewSet,
    LeadActivityViewSet,
    CustomerInteractionViewSet,
    CampaignViewSet,
    TaskViewSet,
    TaskCommentViewSet,
    # Services
    ServiceCategoryViewSet,
    ServicePricingViewSet,
    QuoteViewSet,
    # Reporting
    DashboardViewSet,
    DashboardWidgetViewSet,
    KPIViewSet,
    ReportTemplateViewSet,
    GeneratedReportViewSet,
    DataSourceViewSet,
    # Audit
    AuditLogViewSet,
    NotificationViewSet,
)

from .inventory_views import (
    UnitOfMeasureViewSet,
    UnitOfMeasureConversionViewSet,
    WarehouseViewSet,
    WarehouseZoneViewSet,
    WarehouseBinViewSet,
    LotBatchViewSet,
    SerialNumberViewSet,
    StockItemViewSet,
    StockMovementViewSet,
    GoodsReceiptNoteViewSet,
    StockTransferViewSet,
    StockAdjustmentViewSet,
    CycleCountViewSet,
    PickListViewSet,
    ShipmentNoteViewSet,
    ReorderRuleViewSet,
    InventoryValuationConfigViewSet,
)

from .reports_views import (
    TrialBalanceAPIView,
    ProfitAndLossAPIView,
    BalanceSheetAPIView,
    CashFlowAPIView,
)

# Create router
router = SimpleRouter()

# Core routes
router.register(r"currencies", CurrencyViewSet, basename="currency")
router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"branches", BranchViewSet, basename="branch")
router.register(r"fiscal-years", FiscalYearViewSet, basename="fiscal-year")

# HR routes
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"leave-types", LeaveTypeViewSet, basename="leave-type")
router.register(r"leave-requests", LeaveRequestViewSet, basename="leave-request")
router.register(r"attendance", AttendanceViewSet, basename="attendance")
router.register(r"payroll", PayrollViewSet, basename="payroll")

# Finance routes
router.register(r"accounts", AccountViewSet, basename="account")
router.register(r"tax-rates", TaxRateViewSet, basename="tax-rate")
router.register(r"payment-methods", PaymentMethodViewSet, basename="payment-method")
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register(r"expenses", ExpenseViewSet, basename="expense")

# Supplier routes
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"supplier-contacts", SupplierContactViewSet, basename="supplier-contact")
router.register(r"purchase-orders", PurchaseOrderViewSet, basename="purchase-order")

# CRM routes
router.register(r"leads", LeadViewSet, basename="lead")
router.register(r"lead-activities", LeadActivityViewSet, basename="lead-activity")
router.register(r"customer-interactions", CustomerInteractionViewSet, basename="customer-interaction")
router.register(r"campaigns", CampaignViewSet, basename="campaign")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"task-comments", TaskCommentViewSet, basename="task-comment")

# Services routes
router.register(r"service-categories", ServiceCategoryViewSet, basename="service-category")
router.register(r"service-pricing", ServicePricingViewSet, basename="service-pricing")
router.register(r"quotes", QuoteViewSet, basename="quote")

# Reporting routes
router.register(r"dashboards", DashboardViewSet, basename="dashboard")
router.register(r"dashboard-widgets", DashboardWidgetViewSet, basename="dashboard-widget")
router.register(r"kpis", KPIViewSet, basename="kpi")
router.register(r"report-templates", ReportTemplateViewSet, basename="report-template")
router.register(r"generated-reports", GeneratedReportViewSet, basename="generated-report")
router.register(r"report-data-sources", DataSourceViewSet, basename="report-data-source")

# Audit routes
router.register(r"audit-logs", AuditLogViewSet, basename="audit-log")
router.register(r"notifications", NotificationViewSet, basename="notification")

# Inventory & Warehouse routes
router.register(r"uom", UnitOfMeasureViewSet, basename="uom")
router.register(r"uom-conversions", UnitOfMeasureConversionViewSet, basename="uom-conversion")
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"warehouse-zones", WarehouseZoneViewSet, basename="warehouse-zone")
router.register(r"warehouse-bins", WarehouseBinViewSet, basename="warehouse-bin")
router.register(r"lots", LotBatchViewSet, basename="lot")
router.register(r"serial-numbers", SerialNumberViewSet, basename="serial-number")
router.register(r"stock-items", StockItemViewSet, basename="stock-item")
router.register(r"stock-movements", StockMovementViewSet, basename="stock-movement")
router.register(r"goods-receipts", GoodsReceiptNoteViewSet, basename="goods-receipt")
router.register(r"stock-transfers", StockTransferViewSet, basename="stock-transfer")
router.register(r"stock-adjustments", StockAdjustmentViewSet, basename="stock-adjustment")
router.register(r"cycle-counts", CycleCountViewSet, basename="cycle-count")
router.register(r"pick-lists", PickListViewSet, basename="pick-list")
router.register(r"shipments", ShipmentNoteViewSet, basename="shipment")
router.register(r"reorder-rules", ReorderRuleViewSet, basename="reorder-rule")
router.register(r"valuation-config", InventoryValuationConfigViewSet, basename="valuation-config")

# URL patterns
urlpatterns = [
    # Financial report endpoints are declared before the router so they
    # resolve even if a future router registration uses the same prefix.
    path(
        "finance/reports/trial-balance/",
        TrialBalanceAPIView.as_view(),
        name="finance-report-trial-balance",
    ),
    path(
        "finance/reports/profit-and-loss/",
        ProfitAndLossAPIView.as_view(),
        name="finance-report-profit-and-loss",
    ),
    path(
        "finance/reports/balance-sheet/",
        BalanceSheetAPIView.as_view(),
        name="finance-report-balance-sheet",
    ),
    path(
        "finance/reports/cash-flow/",
        CashFlowAPIView.as_view(),
        name="finance-report-cash-flow",
    ),
    path("", include(router.urls)),
]
