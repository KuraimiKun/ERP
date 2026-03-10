import 'product.dart';

class PaymentMethod {
  final int id;
  final String name;
  final String nameAr;
  final String code;
  final bool requiresReference;

  PaymentMethod({
    required this.id,
    required this.name,
    this.nameAr = '',
    required this.code,
    this.requiresReference = false,
  });

  bool get isCash => code.toLowerCase() == 'cash';

  factory PaymentMethod.fromJson(Map<String, dynamic> json) {
    return PaymentMethod(
      id: json['id'],
      name: json['name'] ?? '',
      nameAr: json['name_ar'] ?? '',
      code: json['code'] ?? '',
      requiresReference: json['requires_reference'] ?? false,
    );
  }
}

class POSCustomer {
  final int id;
  final String customerId;
  final String name;
  final String nameAr;
  final String phone;

  POSCustomer({
    required this.id,
    this.customerId = '',
    required this.name,
    this.nameAr = '',
    this.phone = '',
  });

  factory POSCustomer.fromJson(Map<String, dynamic> json) {
    return POSCustomer(
      id: json['id'],
      customerId: json['customer_id'] ?? '',
      name: json['name'] ?? '',
      nameAr: json['name_ar'] ?? '',
      phone: json['phone'] ?? '',
    );
  }
}

/// Cart item (local state, not from API)
class CartItem {
  final Product product;
  int quantity;
  double discountPercent;

  CartItem({
    required this.product,
    this.quantity = 1,
    this.discountPercent = 0,
  });

  double get unitPrice => product.price;

  double get subtotal => unitPrice * quantity;

  double get discountAmount => subtotal * discountPercent / 100;

  double get taxAmount =>
      (subtotal - discountAmount) * product.taxRate / 100;

  double get total => subtotal - discountAmount + taxAmount;
}
