class ApiConfig {
  // Change this to your server's IP/domain
  static const String baseUrl = 'http://10.0.2.2:8000';
  static const String apiBase = '$baseUrl/api/mobile';

  // Auth
  static const String login = '$apiBase/auth/login/';
  static const String logout = '$apiBase/auth/logout/';

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
