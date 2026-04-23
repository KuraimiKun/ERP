import 'dart:convert';
import 'package:dio/dio.dart';
import '../config/api_config.dart';
import '../models/employee.dart';
import '../models/admin/admin_user.dart';
import 'api_service.dart';
import 'storage_service.dart';

class AuthService {
  final ApiService _api;
  final StorageService _storage;

  AuthService(this._api, this._storage);

  /// Employee login.
  Future<LoginResult> login(String email, String password) async {
    try {
      final response = await _api.post(ApiConfig.login, data: {
        'email': email,
        'password': password,
      });

      final data = response.data;
      await _storage.saveToken(data['token']);
      await _storage.saveTenantDb(data['tenant_db']);

      final employee = Employee.fromJson(data['employee']);
      final company = CompanyInfo.fromJson(data['company']);
      await _storage.saveEmployeeData(jsonEncode(data['employee']));

      return LoginResult(
        employee: employee,
        company: company,
        tenantDb: data['tenant_db'],
      );
    } on DioException catch (e) {
      throw AuthException(ApiService.getErrorMessage(e));
    }
  }

  /// Employee logout.
  Future<void> logout() async {
    try {
      await _api.post(ApiConfig.logout);
    } catch (_) {
      // ignore
    }
    await _storage.clearAll();
  }

  /// Admin logout.
  Future<void> adminLogout() async {
    try {
      await _api.post(ApiConfig.adminLogout);
    } catch (_) {
      // ignore
    }
    await _storage.clearAll();
  }

  /// Try admin login first; on 403 (non-admin) fall back to employee login.
  /// Returns either an [AdminLoginResult] or a [LoginResult].
  Future<Object> loginWithRoleDetection(
    String email,
    String password,
  ) async {
    // â”€â”€ Try admin endpoint first â”€â”€
    try {
      final response = await _api.post(
        ApiConfig.adminLogin,
        data: {'email': email, 'password': password},
      );
      final data = response.data as Map<String, dynamic>;

      await _storage.saveToken(data['token']);
      await _storage.saveTenantDb(data['tenant_db']);
      await _storage.saveUserRole(data['role'] ?? 'admin');

      final admin = AdminUser.fromLoginJson(data);
      await _storage.saveAdminUser(jsonEncode(admin.toJson()));

      return AdminLoginResult(admin: admin, tenantDb: data['tenant_db']);
    } on DioException catch (e) {
      // 403 = not an admin; fall through. Any other error is surfaced.
      final status = e.response?.statusCode;
      if (status != 403) {
        throw AuthException(ApiService.getErrorMessage(e));
      }
    }

    // â”€â”€ Fallback: employee login â”€â”€
    final employeeResult = await login(email, password);
    await _storage.saveUserRole('employee');
    return employeeResult;
  }

  /// Stored admin user (if any).
  AdminUser? getStoredAdminUser() {
    final json = _storage.getAdminUser();
    if (json == null) return null;
    try {
      return AdminUser.fromStoredJson(jsonDecode(json));
    } catch (_) {
      return null;
    }
  }

  /// Current stored role (`admin`, `owner`, `employee`, or null).
  String? getStoredRole() => _storage.getUserRole();

  /// Check if user has a stored token.
  Future<bool> isLoggedIn() async {
    final token = await _storage.getToken();
    return token != null && token.isNotEmpty;
  }

  /// Get stored employee from local storage.
  Employee? getStoredEmployee() {
    final json = _storage.getEmployeeData();
    if (json == null) return null;
    try {
      return Employee.fromJson(jsonDecode(json));
    } catch (_) {
      return null;
    }
  }

  /// Change password.
  Future<String> changePassword({
    required String currentPassword,
    required String newPassword,
    required String confirmPassword,
  }) async {
    try {
      final response = await _api.post(ApiConfig.changePassword, data: {
        'current_password': currentPassword,
        'new_password': newPassword,
        'confirm_password': confirmPassword,
      });

      final newToken = response.data['token'];
      await _storage.saveToken(newToken);
      return newToken;
    } on DioException catch (e) {
      throw AuthException(ApiService.getErrorMessage(e));
    }
  }
}

class LoginResult {
  final Employee employee;
  final CompanyInfo company;
  final String tenantDb;

  LoginResult({
    required this.employee,
    required this.company,
    required this.tenantDb,
  });
}

class AdminLoginResult {
  final AdminUser admin;
  final String tenantDb;

  AdminLoginResult({required this.admin, required this.tenantDb});
}

class CompanyInfo {
  final int id;
  final String name;
  final String nameAr;
  final String logoUrl;

  CompanyInfo({
    required this.id,
    required this.name,
    required this.nameAr,
    required this.logoUrl,
  });

  factory CompanyInfo.fromJson(Map<String, dynamic> json) {
    return CompanyInfo(
      id: json['id'],
      name: json['name'] ?? '',
      nameAr: json['name_ar'] ?? '',
      logoUrl: json['logo_url'] ?? '',
    );
  }
}

class AuthException implements Exception {
  final String message;
  AuthException(this.message);

  @override
  String toString() => message;
}
