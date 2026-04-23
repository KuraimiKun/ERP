import 'package:dio/dio.dart';

import 'api_service.dart';

/// Result of a paginated list endpoint.
///
/// Django REST Framework returns `{count, next, previous, results}`.
class PagedResult {
  final int count;
  final String? next;
  final String? previous;
  final List<Map<String, dynamic>> results;

  PagedResult({
    required this.count,
    required this.results,
    this.next,
    this.previous,
  });

  bool get hasMore => next != null;

  factory PagedResult.fromJson(dynamic raw) {
    if (raw is List) {
      return PagedResult(
        count: raw.length,
        results: raw
            .whereType<Map>()
            .map((m) => Map<String, dynamic>.from(m))
            .toList(),
      );
    }
    final map = Map<String, dynamic>.from(raw as Map);
    final results = (map['results'] as List? ?? const [])
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();
    return PagedResult(
      count: (map['count'] as num?)?.toInt() ?? results.length,
      next: map['next'] as String?,
      previous: map['previous'] as String?,
      results: results,
    );
  }
}

/// Generic REST client for the admin-mobile API.
///
/// Every admin-mobile ViewSet follows the same shape (DRF router +
/// `AdminMobileBaseViewSet`). This wrapper exposes CRUD + extra actions
/// so individual screens don't need their own services.
class AdminApiService {
  final ApiService _api;

  AdminApiService(this._api);

  Future<PagedResult> list(
    String endpoint, {
    Map<String, dynamic>? query,
  }) async {
    final response = await _api.get(endpoint, queryParams: query);
    return PagedResult.fromJson(response.data);
  }

  Future<Map<String, dynamic>> retrieve(String endpoint, int id) async {
    final response = await _api.get(_join(endpoint, '$id/'));
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> create(
    String endpoint,
    Map<String, dynamic> data,
  ) async {
    final response = await _api.post(endpoint, data: data);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> update(
    String endpoint,
    int id,
    Map<String, dynamic> data,
  ) async {
    final response = await _api.patch(_join(endpoint, '$id/'), data: data);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> delete(String endpoint, int id) async {
    await _api.delete(_join(endpoint, '$id/'));
  }

  /// Call a detail-level action like `POST /leaves/pending/7/approve/`.
  Future<Map<String, dynamic>> action(
    String endpoint,
    int id,
    String action, {
    Map<String, dynamic>? data,
  }) async {
    final response = await _api.post(
      _join(endpoint, '$id/$action/'),
      data: data ?? const {},
    );
    final raw = response.data;
    return raw is Map
        ? Map<String, dynamic>.from(raw)
        : <String, dynamic>{};
  }

  /// Call a list-level action like `POST /notifications/read/`.
  Future<Map<String, dynamic>> collectionAction(
    String endpoint,
    String action, {
    Map<String, dynamic>? data,
  }) async {
    final response = await _api.post(
      _join(endpoint, '$action/'),
      data: data ?? const {},
    );
    final raw = response.data;
    return raw is Map
        ? Map<String, dynamic>.from(raw)
        : <String, dynamic>{};
  }

  /// GET an arbitrary non-collection path (reports, search, etc.).
  Future<dynamic> getRaw(
    String endpoint, {
    Map<String, dynamic>? query,
  }) async {
    final response = await _api.get(endpoint, queryParams: query);
    return response.data;
  }

  /// Surface DRF validation errors as a readable string.
  static String extractError(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map) {
        if (data['detail'] is String) return data['detail'] as String;
        if (data['error'] is String) return data['error'] as String;
        // Collect per-field errors.
        final parts = <String>[];
        data.forEach((k, v) {
          if (v is List && v.isNotEmpty) {
            parts.add('$k: ${v.first}');
          } else if (v is String) {
            parts.add('$k: $v');
          }
        });
        if (parts.isNotEmpty) return parts.join('\n');
      }
      return ApiService.getErrorMessage(error);
    }
    return error.toString();
  }

  String _join(String endpoint, String tail) {
    if (endpoint.endsWith('/')) return '$endpoint$tail';
    return '$endpoint/$tail';
  }
}
