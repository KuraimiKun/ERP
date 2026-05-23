import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class StorageService {
  static const _tokenKey = 'auth_token';
  static const _tenantDbKey = 'tenant_db';
  static const _employeeKey = 'employee_data';
  static const _adminUserKey = 'admin_user_data';
  static const _userRoleKey = 'user_role'; // 'admin' | 'owner' | 'employee'
  static const _localeKey = 'app_locale';
  static const _themeModeKey = 'theme_mode';

  final FlutterSecureStorage _secure = const FlutterSecureStorage();
  late SharedPreferences _prefs;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  // Token
  Future<void> saveToken(String token) async {
    await _secure.write(key: _tokenKey, value: token);
  }

  Future<String?> getToken() async {
    return await _secure.read(key: _tokenKey);
  }

  Future<void> deleteToken() async {
    await _secure.delete(key: _tokenKey);
  }

  // Tenant DB
  Future<void> saveTenantDb(String db) async {
    await _prefs.setString(_tenantDbKey, db);
  }

  String? getTenantDb() {
    return _prefs.getString(_tenantDbKey);
  }

  Future<void> deleteTenantDb() async {
    await _prefs.remove(_tenantDbKey);
  }

  // Employee data (JSON string)
  Future<void> saveEmployeeData(String json) async {
    await _prefs.setString(_employeeKey, json);
  }

  String? getEmployeeData() {
    return _prefs.getString(_employeeKey);
  }

  Future<void> deleteEmployeeData() async {
    await _prefs.remove(_employeeKey);
  }

  // Admin user (JSON string)
  Future<void> saveAdminUser(String json) async {
    await _prefs.setString(_adminUserKey, json);
  }

  String? getAdminUser() {
    return _prefs.getString(_adminUserKey);
  }

  Future<void> deleteAdminUser() async {
    await _prefs.remove(_adminUserKey);
  }

  // User role
  Future<void> saveUserRole(String role) async {
    await _prefs.setString(_userRoleKey, role);
  }

  String? getUserRole() {
    return _prefs.getString(_userRoleKey);
  }

  Future<void> deleteUserRole() async {
    await _prefs.remove(_adminUserKey);
    await _prefs.remove(_userRoleKey);
  }

  // Locale
  Future<void> saveLocale(String locale) async {
    await _prefs.setString(_localeKey, locale);
  }

  String getLocale() {
    return _prefs.getString(_localeKey) ?? 'ar';
  }

  // Theme mode
  Future<void> saveThemeMode(String mode) async {
    await _prefs.setString(_themeModeKey, mode);
  }

  String getThemeMode() {
    return _prefs.getString(_themeModeKey) ?? 'system';
  }

  // Clear all
  Future<void> clearAll() async {
    await _secure.deleteAll();
    await _prefs.remove(_tenantDbKey);
    await _prefs.remove(_employeeKey);
    await _prefs.remove(_adminUserKey);
    await _prefs.remove(_userRoleKey);
  }
}
