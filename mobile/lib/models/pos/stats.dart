class POSStats {
  final String period;
  final SalesSummary summary;
  final List<PaymentBreakdown> paymentBreakdown;
  final List<TopProduct> topProducts;
  final List<RecentSession> recentSessions;
  final List<HourlySales> hourlySales;

  POSStats({
    required this.period,
    required this.summary,
    required this.paymentBreakdown,
    required this.topProducts,
    required this.recentSessions,
    required this.hourlySales,
  });

  factory POSStats.fromJson(Map<String, dynamic> json) {
    return POSStats(
      period: json['period'] ?? 'today',
      summary: SalesSummary.fromJson(json['summary'] ?? {}),
      paymentBreakdown: (json['payment_breakdown'] as List? ?? [])
          .map((e) => PaymentBreakdown.fromJson(e))
          .toList(),
      topProducts: (json['top_products'] as List? ?? [])
          .map((e) => TopProduct.fromJson(e))
          .toList(),
      recentSessions: (json['recent_sessions'] as List? ?? [])
          .map((e) => RecentSession.fromJson(e))
          .toList(),
      hourlySales: (json['hourly_sales'] as List? ?? [])
          .map((e) => HourlySales.fromJson(e))
          .toList(),
    );
  }
}

class SalesSummary {
  final String totalSales;
  final int totalOrders;
  final String averageOrder;
  final String totalItemsSold;
  final String totalDiscount;
  final String totalTax;
  final String totalRefunds;
  final int refundCount;

  SalesSummary({
    required this.totalSales,
    required this.totalOrders,
    required this.averageOrder,
    required this.totalItemsSold,
    required this.totalDiscount,
    required this.totalTax,
    required this.totalRefunds,
    required this.refundCount,
  });

  factory SalesSummary.fromJson(Map<String, dynamic> json) {
    return SalesSummary(
      totalSales: json['total_sales'] ?? '0',
      totalOrders: json['total_orders'] ?? 0,
      averageOrder: json['average_order'] ?? '0',
      totalItemsSold: json['total_items_sold'] ?? '0',
      totalDiscount: json['total_discount'] ?? '0',
      totalTax: json['total_tax'] ?? '0',
      totalRefunds: json['total_refunds'] ?? '0',
      refundCount: json['refund_count'] ?? 0,
    );
  }
}

class PaymentBreakdown {
  final String method;
  final String code;
  final String total;
  final int count;

  PaymentBreakdown({
    required this.method,
    required this.code,
    required this.total,
    required this.count,
  });

  factory PaymentBreakdown.fromJson(Map<String, dynamic> json) {
    return PaymentBreakdown(
      method: json['method'] ?? '',
      code: json['code'] ?? '',
      total: json['total'] ?? '0',
      count: json['count'] ?? 0,
    );
  }
}

class TopProduct {
  final String name;
  final String sku;
  final String quantity;
  final String total;

  TopProduct({
    required this.name,
    required this.sku,
    required this.quantity,
    required this.total,
  });

  factory TopProduct.fromJson(Map<String, dynamic> json) {
    return TopProduct(
      name: json['name'] ?? '',
      sku: json['sku'] ?? '',
      quantity: json['quantity'] ?? '0',
      total: json['total'] ?? '0',
    );
  }
}

class RecentSession {
  final int id;
  final String sessionNumber;
  final String terminalName;
  final String? openedAt;
  final String? closedAt;
  final String status;
  final String totalSales;
  final int totalOrders;
  final String cashDifference;

  RecentSession({
    required this.id,
    required this.sessionNumber,
    required this.terminalName,
    this.openedAt,
    this.closedAt,
    required this.status,
    required this.totalSales,
    required this.totalOrders,
    required this.cashDifference,
  });

  factory RecentSession.fromJson(Map<String, dynamic> json) {
    return RecentSession(
      id: json['id'] ?? 0,
      sessionNumber: json['session_number'] ?? '',
      terminalName: json['terminal_name'] ?? '',
      openedAt: json['opened_at'],
      closedAt: json['closed_at'],
      status: json['status'] ?? '',
      totalSales: json['total_sales']?.toString() ?? '0',
      totalOrders: json['total_orders'] ?? 0,
      cashDifference: json['cash_difference']?.toString() ?? '0',
    );
  }
}

class HourlySales {
  final int hour;
  final String total;
  final int count;

  HourlySales({
    required this.hour,
    required this.total,
    required this.count,
  });

  factory HourlySales.fromJson(Map<String, dynamic> json) {
    return HourlySales(
      hour: json['hour'] ?? 0,
      total: json['total'] ?? '0',
      count: json['count'] ?? 0,
    );
  }
}
