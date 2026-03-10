class POSOrder {
  final int id;
  final String orderNumber;
  final String orderDate;
  final String? customerName;
  final String subtotal;
  final String discountAmount;
  final String taxAmount;
  final String totalAmount;
  final String status;

  POSOrder({
    required this.id,
    required this.orderNumber,
    this.orderDate = '',
    this.customerName,
    this.subtotal = '0',
    this.discountAmount = '0',
    this.taxAmount = '0',
    this.totalAmount = '0',
    this.status = 'draft',
  });

  factory POSOrder.fromJson(Map<String, dynamic> json) {
    return POSOrder(
      id: json['id'],
      orderNumber: json['order_number'] ?? '',
      orderDate: json['order_date'] ?? '',
      customerName: json['customer_name'],
      subtotal: json['subtotal']?.toString() ?? '0',
      discountAmount: json['discount_amount']?.toString() ?? '0',
      taxAmount: json['tax_amount']?.toString() ?? '0',
      totalAmount: json['total_amount']?.toString() ?? '0',
      status: json['status'] ?? 'draft',
    );
  }
}

class POSOrderLine {
  final String productName;
  final String productSku;
  final String quantity;
  final String unitPrice;
  final String discountPercent;
  final String taxAmount;
  final String lineTotal;

  POSOrderLine({
    required this.productName,
    this.productSku = '',
    required this.quantity,
    required this.unitPrice,
    this.discountPercent = '0',
    this.taxAmount = '0',
    required this.lineTotal,
  });

  factory POSOrderLine.fromJson(Map<String, dynamic> json) {
    return POSOrderLine(
      productName: json['product_name'] ?? '',
      productSku: json['product_sku'] ?? '',
      quantity: json['quantity']?.toString() ?? '0',
      unitPrice: json['unit_price']?.toString() ?? '0',
      discountPercent: json['discount_percent']?.toString() ?? '0',
      taxAmount: json['tax_amount']?.toString() ?? '0',
      lineTotal: json['line_total']?.toString() ?? '0',
    );
  }
}

class POSReceipt {
  final String orderNumber;
  final String orderDate;
  final String status;
  final String terminalName;
  final String receiptHeader;
  final String receiptFooter;
  final String employeeName;
  final String customerName;
  final String subtotal;
  final String discountAmount;
  final String taxAmount;
  final String totalAmount;
  final String companyName;
  final String companyNameAr;
  final List<POSOrderLine> lines;
  final List<ReceiptPayment> payments;

  POSReceipt({
    required this.orderNumber,
    this.orderDate = '',
    this.status = '',
    this.terminalName = '',
    this.receiptHeader = '',
    this.receiptFooter = '',
    this.employeeName = '',
    this.customerName = '',
    this.subtotal = '0',
    this.discountAmount = '0',
    this.taxAmount = '0',
    this.totalAmount = '0',
    this.companyName = '',
    this.companyNameAr = '',
    this.lines = const [],
    this.payments = const [],
  });

  factory POSReceipt.fromJson(Map<String, dynamic> json) {
    return POSReceipt(
      orderNumber: json['order_number'] ?? '',
      orderDate: json['order_date'] ?? '',
      status: json['status'] ?? '',
      terminalName: json['terminal_name'] ?? '',
      receiptHeader: json['receipt_header'] ?? '',
      receiptFooter: json['receipt_footer'] ?? '',
      employeeName: json['employee_name'] ?? '',
      customerName: json['customer_name'] ?? '',
      subtotal: json['subtotal']?.toString() ?? '0',
      discountAmount: json['discount_amount']?.toString() ?? '0',
      taxAmount: json['tax_amount']?.toString() ?? '0',
      totalAmount: json['total_amount']?.toString() ?? '0',
      companyName: json['company_name'] ?? '',
      companyNameAr: json['company_name_ar'] ?? '',
      lines: (json['lines'] as List? ?? [])
          .map((e) => POSOrderLine.fromJson(e))
          .toList(),
      payments: (json['payments'] as List? ?? [])
          .map((e) => ReceiptPayment.fromJson(e))
          .toList(),
    );
  }
}

class ReceiptPayment {
  final String method;
  final String amount;
  final String tendered;
  final String change;

  ReceiptPayment({
    required this.method,
    required this.amount,
    this.tendered = '0',
    this.change = '0',
  });

  factory ReceiptPayment.fromJson(Map<String, dynamic> json) {
    return ReceiptPayment(
      method: json['method'] ?? '',
      amount: json['amount']?.toString() ?? '0',
      tendered: json['tendered']?.toString() ?? '0',
      change: json['change']?.toString() ?? '0',
    );
  }
}
