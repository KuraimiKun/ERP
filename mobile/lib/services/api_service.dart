import 'package:dio/dio.dart';

import 'storage_service.dart';

class ApiService {
  late Dio _dio;
  final StorageService _storage;

  ApiService(this._storage) {
    _dio = Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 15),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        // Add auth token
        final token = await _storage.getToken();
        if (token != null) {
          options.headers['Authorization'] = 'Token $token';
        }

        // Add tenant DB header
        final tenantDb = _storage.getTenantDb();
        if (tenantDb != null) {
          options.headers['X-Tenant-DB'] = tenantDb;
        }

        // Add locale
        options.headers['Accept-Language'] = _storage.getLocale();

        handler.next(options);
      },
      onError: (error, handler) {
        handler.next(error);
      },
    ));
  }

  Dio get dio => _dio;

  Future<Response> get(String url, {Map<String, dynamic>? queryParams}) {
    return _dio.get(url, queryParameters: queryParams);
  }

  Future<Response> post(String url, {dynamic data}) {
    return _dio.post(url, data: data);
  }

  Future<Response> patch(String url, {dynamic data}) {
    return _dio.patch(url, data: data);
  }

  Future<Response> delete(String url) {
    return _dio.delete(url);
  }

  /// Update token after password change
  void updateToken(String newToken) {
    _storage.saveToken(newToken);
  }

  /// Check if error is 401 (unauthorized)
  static bool isUnauthorized(DioException e) {
    return e.response?.statusCode == 401;
  }

  /// Extract error message from API response
  static String getErrorMessage(DioException e) {
    if (e.response?.data is Map && e.response?.data['error'] != null) {
      return e.response!.data['error'];
    }
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return 'Connection timeout. Please check your internet.';
    }
    if (e.type == DioExceptionType.connectionError) {
      return 'Cannot connect to server. Please check your internet.';
    }
    return 'An unexpected error occurred.';
  }
}
