import 'package:flutter/material.dart';
import '../models/employee.dart';
import '../models/admin/admin_user.dart';
import '../services/auth_service.dart';
import '../services/storage_service.dart';

/// Unified auth provider supporting both the employee portal and the
/// admin portal. The role is determined at login by trying the admin
/// endpoint first; on 403 it falls back to the employee endpoint.
class AuthProvider extends ChangeNotifier {
  final AuthService _authService;
  final StorageService _storage;

  Employee? _employee;
  CompanyInfo? _company;
  AdminUser? _admin;
  String? _role; // 'admin' | 'owner' | 'employee'

  bool _isLoading = false;
  bool _isLoggedIn = false;
  String? _error;

  AuthProvider(this._authService, this._storage);

  // â”€â”€ Employee-portal getters (kept for existing screens) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  Employee? get employee => _employee;
  CompanyInfo? get company => _company;
  EmployeePermissions get permissions =>
      _employee?.permissions ?? EmployeePermissions();

  // â”€â”€ Admin-portal getters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  AdminUser? get admin => _admin;
  String? get role => _role;
  bool get isAdmin => _role == 'admin' || _role == 'owner';
  bool get isEmployee => _role == 'employee';

  // â”€â”€ Shared â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  StorageService get storage => _storage;
  AuthService get authService => _authService;
  bool get isLoading => _isLoading;
  bool get isLoggedIn => _isLoggedIn;
  String? get error => _error;

  /// Check stored auth on app startup
  Future<void> checkAuth() async {
    final loggedIn = await _authService.isLoggedIn();
    if (!loggedIn) {
      notifyListeners();
      return;
    }

    _role = _authService.getStoredRole();
    if (_role == 'admin' || _role == 'owner') {
      _admin = _authService.getStoredAdminUser();
      _isLoggedIn = _admin != null;
    } else {
      _employee = _authService.getStoredEmployee();
      _isLoggedIn = _employee != null;
      if (_isLoggedIn) _role = 'employee';
    }
    notifyListeners();
  }

  /// Unified login â€” tries admin endpoint first, falls back to employee.
  Future<bool> login(String email, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final result =
          await _authService.loginWithRoleDetection(email, password);
      if (result is AdminLoginResult) {
        _admin = result.admin;
        _role = result.admin.role;
        _employee = null;
        _company = null;
      } else if (result is LoginResult) {
        _employee = result.employee;
        _company = result.company;
        _admin = null;
        _role = 'employee';
      }
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

  /// Logout â€” uses whichever endpoint matches the stored role.
  Future<void> logout() async {
    if (isAdmin) {
      await _authService.adminLogout();
    } else {
      await _authService.logout();
    }
    _employee = null;
    _company = null;
    _admin = null;
    _role = null;
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
