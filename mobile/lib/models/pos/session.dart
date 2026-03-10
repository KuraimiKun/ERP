class POSSession {
  final int id;
  final String sessionNumber;
  final String terminalName;
  final String status;
  final String openingBalance;
  final String expectedCash;
  final String closingBalance;
  final String cashDifference;
  final String totalSales;
  final int orderCount;
  final int totalOrders;
  final String? openedAt;
  final String? closedAt;

  POSSession({
    required this.id,
    required this.sessionNumber,
    this.terminalName = '',
    this.status = 'open',
    this.openingBalance = '0',
    this.expectedCash = '0',
    this.closingBalance = '0',
    this.cashDifference = '0',
    this.totalSales = '0',
    this.orderCount = 0,
    this.totalOrders = 0,
    this.openedAt,
    this.closedAt,
  });

  bool get isOpen => status == 'open';

  factory POSSession.fromJson(Map<String, dynamic> json) {
    return POSSession(
      id: json['id'],
      sessionNumber: json['session_number'] ?? '',
      terminalName: json['terminal_name'] ?? '',
      status: json['status'] ?? 'open',
      openingBalance: json['opening_balance']?.toString() ?? '0',
      expectedCash: json['expected_cash']?.toString() ?? '0',
      closingBalance: json['closing_balance']?.toString() ?? '0',
      cashDifference: json['cash_difference']?.toString() ?? '0',
      totalSales: json['total_sales']?.toString() ?? '0',
      orderCount: json['order_count'] ?? 0,
      totalOrders: json['total_orders'] ?? 0,
      openedAt: json['opened_at'],
      closedAt: json['closed_at'],
    );
  }
}
