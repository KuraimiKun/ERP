class ApiConfig {
  // Change this to your server's IP/domain
  static const String baseUrl = 'http://34.31.117.185';
  static const String apiBase = '$baseUrl/api/mobile';
  static const String adminApiBase = '$baseUrl/api/mobile/admin/v1';

  // Auth (employee)
  static const String login = '$apiBase/auth/login/';
  static const String logout = '$apiBase/auth/logout/';

  // Auth (admin)
  static const String adminLogin = '$adminApiBase/auth/login/';
  static const String adminLogout = '$adminApiBase/auth/logout/';
  static const String adminMe = '$adminApiBase/auth/me/';
  static const String adminChangePassword =
      '$adminApiBase/auth/change-password/';

  // Admin dashboard / KPIs
  static const String adminDashboard = '$adminApiBase/dashboard/';
  static const String adminDashboardKpis = '$adminApiBase/dashboard/kpis/';
  static const String adminDashboardActivity =
      '$adminApiBase/dashboard/activity/';

  // Admin approvals
  static const String adminPendingLeaves = '$adminApiBase/leaves/pending/';
  static const String adminPendingExpenses = '$adminApiBase/expenses/pending/';
  static const String adminPendingPurchaseOrders =
      '$adminApiBase/purchase-orders/pending/';
  static const String adminPendingQuotes = '$adminApiBase/quotes/pending/';
  static const String adminPendingSupplierInvoices =
      '$adminApiBase/supplier-invoices/pending/';

  // Admin HR
  static const String adminEmployees = '$adminApiBase/employees/';
  static const String adminDepartments = '$adminApiBase/departments/';
  static const String adminBranches = '$adminApiBase/branches/';
  static const String adminAttendance = '$adminApiBase/attendance/';
  static const String adminLeaveRequests = '$adminApiBase/leave-requests/';
  static const String adminPayroll = '$adminApiBase/payroll/';

  // Admin Finance
  static const String adminCustomers = '$adminApiBase/customers/';
  static const String adminInvoices = '$adminApiBase/invoices/';
  static const String adminPayments = '$adminApiBase/payments/';
  static const String adminExpenses = '$adminApiBase/expenses/';
  static const String adminAccounts = '$adminApiBase/accounts/';
  static const String adminTaxRates = '$adminApiBase/tax-rates/';

  // Admin Suppliers
  static const String adminSuppliers = '$adminApiBase/suppliers/';
  static const String adminPurchaseOrders = '$adminApiBase/purchase-orders/';
  static const String adminSupplierInvoices =
      '$adminApiBase/supplier-invoices/';
  static const String adminSupplierPayments =
      '$adminApiBase/supplier-payments/';

  // Admin Inventory
  static const String adminWarehouses = '$adminApiBase/warehouses/';
  static const String adminProducts = '$adminApiBase/products/';
  static const String adminStockItems = '$adminApiBase/stock-items/';
  static const String adminStockMovements = '$adminApiBase/stock-movements/';
  static const String adminGoodsReceipts = '$adminApiBase/goods-receipts/';
  static const String adminStockAdjustments =
      '$adminApiBase/stock-adjustments/';

  // Admin POS
  static const String adminPosTerminals = '$adminApiBase/pos/terminals/';
  static const String adminPosSessions = '$adminApiBase/pos/sessions/';
  static const String adminPosOrders = '$adminApiBase/pos/orders/';

  // Admin CRM
  static const String adminLeads = '$adminApiBase/leads/';
  static const String adminLeadActivities = '$adminApiBase/lead-activities/';
  static const String adminCustomerInteractions =
      '$adminApiBase/customer-interactions/';
  static const String adminTasks = '$adminApiBase/tasks/';
  static const String adminCampaigns = '$adminApiBase/campaigns/';

  // Admin Services
  static const String adminQuotes = '$adminApiBase/quotes/';
  static const String adminServicePricing = '$adminApiBase/service-pricing/';

  // Admin misc
  static const String adminNotifications = '$adminApiBase/notifications/';
  static const String adminNotificationsRead =
      '$adminApiBase/notifications/read/';
  static const String adminNotificationsReadAll =
      '$adminApiBase/notifications/read-all/';
  static const String adminNotificationsUnreadCount =
      '$adminApiBase/notifications/unread-count/';
  static const String adminAuditLogs = '$adminApiBase/audit-logs/';
  static const String adminFiscalYears = '$adminApiBase/fiscal-years/';
  static const String adminCurrencies = '$adminApiBase/currencies/';
  static const String adminCompany = '$adminApiBase/company/';
  static const String adminFeatureFlags =
      '$adminApiBase/company/feature-flags/';
  static const String adminSearch = '$adminApiBase/search/';

  // Admin reports
  static const String adminReportTrialBalance =
      '$adminApiBase/reports/trial-balance/';
  static const String adminReportProfitAndLoss =
      '$adminApiBase/reports/profit-and-loss/';
  static const String adminReportBalanceSheet =
      '$adminApiBase/reports/balance-sheet/';
  static const String adminReportCashFlow = '$adminApiBase/reports/cash-flow/';
  static const String adminReportSalesSummary =
      '$adminApiBase/reports/sales-summary/';
  static const String adminReportTopProducts =
      '$adminApiBase/reports/top-products/';
  static const String adminReportTopCustomers =
      '$adminApiBase/reports/top-customers/';
  static const String adminReportAgingReceivables =
      '$adminApiBase/reports/aging-receivables/';
  static const String adminReportAgingPayables =
      '$adminApiBase/reports/aging-payables/';

  // Dashboard
  static const String dashboard = '$apiBase/dashboard/';

  // Profile
  static const String profile = '$apiBase/profile/';
  static const String changePassword = '$apiBase/password/';

  // Attendance
  static const String attendance = '$apiBase/attendance/';
  static const String attendanceScan = '$apiBase/attendance/scan/';

  // Leaves
  static const String leaves = '$apiBase/leaves/';
  static String leaveCancel(int id) => '$apiBase/leaves/$id/cancel/';

  // Payslips
  static const String payslips = '$apiBase/payslips/';
  static String payslipDetail(int id) => '$apiBase/payslips/$id/';

  // Tasks
  static const String tasks = '$apiBase/tasks/';
  static String taskDetail(int id) => '$apiBase/tasks/$id/';
  static String taskStatus(int id) => '$apiBase/tasks/$id/status/';
  static String taskComment(int id) => '$apiBase/tasks/$id/comment/';

  // Notifications
  static const String notifications = '$apiBase/notifications/';
  static const String notificationsRead = '$apiBase/notifications/read/';

  // POS
  static const String posTerminals = '$apiBase/pos/terminals/';
  static const String posSessionOpen = '$apiBase/pos/sessions/open/';
  static String posSessionDetail(int id) => '$apiBase/pos/sessions/$id/';
  static String posSessionClose(int id) => '$apiBase/pos/sessions/$id/close/';
  static const String posProducts = '$apiBase/pos/products/';
  static const String posCategories = '$apiBase/pos/categories/';
  static const String posCustomers = '$apiBase/pos/customers/';
  static const String posPaymentMethods = '$apiBase/pos/payment-methods/';
  static const String posCreateOrder = '$apiBase/pos/orders/create/';
  static const String posCompleteOrder = '$apiBase/pos/orders/complete/';
  static String posReceipt(int id) => '$apiBase/pos/orders/$id/receipt/';
  static String posOrderHistory(int sessionId) =>
      '$apiBase/pos/orders/history/$sessionId/';
  static const String posStats = '$apiBase/pos/stats/';
}
