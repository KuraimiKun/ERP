import 'package:flutter/material.dart';
import '../models/employee.dart';
import '../services/auth_service.dart';
import '../services/storage_service.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _authService;
  final StorageService _storage;

  Employee? _employee;
  CompanyInfo? _company;
  bool _isLoading = false;
  bool _isLoggedIn = false;
  String? _error;

  AuthProvider(this._authService, this._storage);

  Employee? get employee => _employee;
  CompanyInfo? get company => _company;
  StorageService get storage => _storage;
  AuthService get authService => _authService;
  EmployeePermissions get permissions =>
      _employee?.permissions ?? EmployeePermissions();
  bool get isLoading => _isLoading;
  bool get isLoggedIn => _isLoggedIn;
  String? get error => _error;

  /// Check stored auth on app startup
  Future<void> checkAuth() async {
    final loggedIn = await _authService.isLoggedIn();
    if (loggedIn) {
      _employee = _authService.getStoredEmployee();
      _isLoggedIn = _employee != null;
    }
    notifyListeners();
  }

  /// Login
  Future<bool> login(String email, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _authService.login(email, password);
      _employee = result.employee;
      _company = result.company;
      _isLoggedIn = true;
      _isLoading = false;
      notifyListeners();
      return true;
    } on AuthException catch (e) {
      _error = e.message;
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Logout
  Future<void> logout() async {
    await _authService.logout();
    _employee = null;
    _company = null;
    _isLoggedIn = false;
    notifyListeners();
  }

  /// Update employee after profile refresh
  void updateEmployee(Employee emp) {
    _employee = emp;
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
