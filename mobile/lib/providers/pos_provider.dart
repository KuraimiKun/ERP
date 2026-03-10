import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/pos/terminal.dart';
import '../models/pos/session.dart';
import '../models/pos/product.dart';
import '../models/pos/order.dart';
import '../models/pos/payment.dart';
import '../models/pos/stats.dart';
import '../services/api_service.dart';

class POSProvider extends ChangeNotifier {
  final ApiService _api;

  // Terminals
  List<POSTerminal> _terminals = [];

  // Session
  POSSession? _currentSession;

  // Products & Categories
  List<Product> _products = [];
  List<ProductCategory> _categories = [];
  List<PaymentMethod> _paymentMethods = [];
  List<POSCustomer> _customers = [];

  // Cart
  final List<CartItem> _cart = [];
  POSCustomer? _selectedCustomer;
  double _orderDiscountPercent = 0;

  // Orders
  List<POSOrder> _orderHistory = [];

  // Stats
  POSStats? _stats;
  bool _statsLoading = false;

  bool _isLoading = false;
  String? _error;

  POSProvider(this._api);

  // Getters
  List<POSTerminal> get terminals => _terminals;
  POSSession? get currentSession => _currentSession;
  List<Product> get products => _products;
  List<ProductCategory> get categories => _categories;
  List<PaymentMethod> get paymentMethods => _paymentMethods;
  List<POSCustomer> get customers => _customers;
  List<CartItem> get cart => _cart;
  POSCustomer? get selectedCustomer => _selectedCustomer;
  double get orderDiscountPercent => _orderDiscountPercent;
  List<POSOrder> get orderHistory => _orderHistory;
  POSStats? get stats => _stats;
  bool get statsLoading => _statsLoading;
  bool get isLoading => _isLoading;
  String? get error => _error;

  int get cartItemCount => _cart.fold(0, (sum, item) => sum + item.quantity);

  double get cartSubtotal =>
      _cart.fold(0, (sum, item) => sum + item.subtotal);

  double get cartTax =>
      _cart.fold(0, (sum, item) => sum + item.taxAmount);

  double get cartDiscount {
    final lineDiscounts =
        _cart.fold<double>(0, (sum, item) => sum + item.discountAmount);
    final orderDiscount = cartSubtotal * _orderDiscountPercent / 100;
    return lineDiscounts + orderDiscount;
  }

  double get cartTotal => cartSubtotal - cartDiscount + cartTax;

  // Terminal operations
  Future<void> loadTerminals() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.posTerminals);
      _terminals = (response.data['terminals'] as List? ?? [])
          .map((e) => POSTerminal.fromJson(e))
          .toList();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  // Session operations
  Future<bool> openSession(int terminalId, String openingBalance) async {
    try {
      final response = await _api.post(ApiConfig.posSessionOpen, data: {
        'terminal_id': terminalId,
        'opening_balance': openingBalance,
      });
      _currentSession = POSSession.fromJson(response.data['session']);
      notifyListeners();
      return true;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return false;
    }
  }

  Future<void> loadSession(int sessionId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.posSessionDetail(sessionId));
      _currentSession = POSSession.fromJson(response.data['session']);
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> closeSession(
      int sessionId, String closingBalance, String notes) async {
    try {
      final response =
          await _api.post(ApiConfig.posSessionClose(sessionId), data: {
        'closing_balance': closingBalance,
        'notes': notes,
      });
      _currentSession = POSSession.fromJson(response.data['session']);
      notifyListeners();
      return true;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return false;
    }
  }

  // Products
  Future<void> loadProducts({String? query, int? categoryId, String? barcode}) async {
    _isLoading = true;
    notifyListeners();

    try {
      final params = <String, dynamic>{};
      if (query != null && query.isNotEmpty) params['q'] = query;
      if (categoryId != null) params['category'] = categoryId;
      if (barcode != null && barcode.isNotEmpty) params['barcode'] = barcode;

      final response =
          await _api.get(ApiConfig.posProducts, queryParams: params);
      _products = (response.data['products'] as List? ?? [])
          .map((e) => Product.fromJson(e))
          .toList();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> loadCategories() async {
    try {
      final response = await _api.get(ApiConfig.posCategories);
      _categories = (response.data['categories'] as List? ?? [])
          .map((e) => ProductCategory.fromJson(e))
          .toList();
      notifyListeners();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
    }
  }

  Future<void> loadPaymentMethods() async {
    try {
      final response = await _api.get(ApiConfig.posPaymentMethods);
      _paymentMethods = (response.data['payment_methods'] as List? ?? [])
          .map((e) => PaymentMethod.fromJson(e))
          .toList();
      notifyListeners();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
    }
  }

  Future<void> searchCustomers(String query) async {
    try {
      final response =
          await _api.get(ApiConfig.posCustomers, queryParams: {'q': query});
      _customers = (response.data['customers'] as List? ?? [])
          .map((e) => POSCustomer.fromJson(e))
          .toList();
      notifyListeners();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
    }
  }

  // Cart operations
  void addToCart(Product product) {
    final existing = _cart.indexWhere((item) => item.product.id == product.id);
    if (existing >= 0) {
      _cart[existing].quantity++;
    } else {
      _cart.add(CartItem(product: product));
    }
    notifyListeners();
  }

  void updateCartItemQuantity(int productId, int quantity) {
    final index = _cart.indexWhere((item) => item.product.id == productId);
    if (index >= 0) {
      if (quantity <= 0) {
        _cart.removeAt(index);
      } else {
        _cart[index].quantity = quantity;
      }
      notifyListeners();
    }
  }

  void removeFromCart(int productId) {
    _cart.removeWhere((item) => item.product.id == productId);
    notifyListeners();
  }

  void clearCart() {
    _cart.clear();
    _selectedCustomer = null;
    _orderDiscountPercent = 0;
    notifyListeners();
  }

  void setCustomer(POSCustomer? customer) {
    _selectedCustomer = customer;
    notifyListeners();
  }

  void setOrderDiscount(double percent) {
    _orderDiscountPercent = percent;
    notifyListeners();
  }

  // Order operations
  Future<POSOrder?> createOrder() async {
    if (_currentSession == null || _cart.isEmpty) return null;

    try {
      final items = _cart
          .map((item) => {
                'product_id': item.product.id,
                'quantity': item.quantity,
                'unit_price': item.product.price,
                'discount_percent': item.discountPercent,
              })
          .toList();

      final response = await _api.post(ApiConfig.posCreateOrder, data: {
        'session_id': _currentSession!.id,
        'items': items,
        'customer_id': _selectedCustomer?.id,
        'discount_percent': _orderDiscountPercent,
      });

      return POSOrder(
        id: response.data['order_id'],
        orderNumber: response.data['order_number'] ?? '',
        totalAmount: response.data['total_amount']?.toString() ?? '0',
        subtotal: response.data['subtotal']?.toString() ?? '0',
        taxAmount: response.data['tax_amount']?.toString() ?? '0',
        discountAmount: response.data['discount_amount']?.toString() ?? '0',
      );
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return null;
    }
  }

  Future<bool> completeOrder(
      int orderId, List<Map<String, dynamic>> payments) async {
    try {
      await _api.post(ApiConfig.posCompleteOrder, data: {
        'order_id': orderId,
        'payments': payments,
      });
      clearCart();
      return true;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return false;
    }
  }

  Future<POSReceipt?> loadReceipt(int orderId) async {
    try {
      final response = await _api.get(ApiConfig.posReceipt(orderId));
      return POSReceipt.fromJson(response.data['receipt']);
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return null;
    }
  }

  Future<void> loadOrderHistory(int sessionId) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.posOrderHistory(sessionId));
      _orderHistory = (response.data['orders'] as List? ?? [])
          .map((e) => POSOrder.fromJson(e))
          .toList();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  // Stats
  Future<void> loadStats({String period = 'today'}) async {
    _statsLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(
        ApiConfig.posStats,
        queryParams: {'period': period},
      );
      _stats = POSStats.fromJson(response.data);
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _statsLoading = false;
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
