class Product {
  final int id;
  final String sku;
  final String barcode;
  final String name;
  final String nameAr;
  final String sellingPrice;
  final String costPrice;
  final String minSellingPrice;
  final int? taxRateId;
  final String taxRatePercent;
  final bool trackInventory;
  final String quantityOnHand;
  final String imageUrl;
  final int? categoryId;
  final String categoryName;

  Product({
    required this.id,
    required this.sku,
    this.barcode = '',
    required this.name,
    this.nameAr = '',
    required this.sellingPrice,
    this.costPrice = '0',
    this.minSellingPrice = '0',
    this.taxRateId,
    this.taxRatePercent = '0',
    this.trackInventory = false,
    this.quantityOnHand = '0',
    this.imageUrl = '',
    this.categoryId,
    this.categoryName = '',
  });

  double get price => double.tryParse(sellingPrice) ?? 0;
  double get taxRate => double.tryParse(taxRatePercent) ?? 0;

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      id: json['id'],
      sku: json['sku'] ?? '',
      barcode: json['barcode'] ?? '',
      name: json['name'] ?? '',
      nameAr: json['name_ar'] ?? '',
      sellingPrice: json['selling_price']?.toString() ?? '0',
      costPrice: json['cost_price']?.toString() ?? '0',
      minSellingPrice: json['min_selling_price']?.toString() ?? '0',
      taxRateId: json['tax_rate_id'],
      taxRatePercent: json['tax_rate_percent']?.toString() ?? '0',
      trackInventory: json['track_inventory'] ?? false,
      quantityOnHand: json['quantity_on_hand']?.toString() ?? '0',
      imageUrl: json['image_url'] ?? '',
      categoryId: json['category_id'],
      categoryName: json['category_name'] ?? '',
    );
  }
}

class ProductCategory {
  final int id;
  final String name;
  final String nameAr;
  final String code;

  ProductCategory({
    required this.id,
    required this.name,
    this.nameAr = '',
    this.code = '',
  });

  factory ProductCategory.fromJson(Map<String, dynamic> json) {
    return ProductCategory(
      id: json['id'],
      name: json['name'] ?? '',
      nameAr: json['name_ar'] ?? '',
      code: json['code'] ?? '',
    );
  }
}
