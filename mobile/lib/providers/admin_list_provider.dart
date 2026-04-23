import 'package:flutter/foundation.dart';

import '../services/admin_api_service.dart';

/// Generic list provider for any DRF-paginated admin-mobile endpoint.
///
/// Handles: initial load, search query, filters, pagination, pull-to-refresh.
/// Records are exposed as `Map<String, dynamic>` so a single provider serves
/// every admin section (employees, customers, invoices, …).
class AdminListProvider extends ChangeNotifier {
  final AdminApiService _api;
  final String endpoint;

  /// Extra filters that come from the calling screen (e.g. `status=pending`).
  Map<String, dynamic> baseQuery;

  List<Map<String, dynamic>> _items = [];
  int _count = 0;
  int _page = 1;
  bool _hasMore = false;
  bool _isLoading = false;
  bool _isLoadingMore = false;
  String? _error;
  String _search = '';

  AdminListProvider(
    this._api, {
    required this.endpoint,
    this.baseQuery = const {},
  });

  List<Map<String, dynamic>> get items => _items;
  int get count => _count;
  bool get isLoading => _isLoading;
  bool get isLoadingMore => _isLoadingMore;
  bool get hasMore => _hasMore;
  String? get error => _error;
  String get search => _search;

  Map<String, dynamic> _buildQuery({required int page}) {
    final q = <String, dynamic>{...baseQuery, 'page': page};
    if (_search.trim().isNotEmpty) q['search'] = _search.trim();
    return q;
  }

  Future<void> load({bool reset = true}) async {
    if (reset) {
      _page = 1;
      _items = [];
      _hasMore = false;
    }
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final res = await _api.list(endpoint, query: _buildQuery(page: _page));
      _items = [..._items, ...res.results];
      _count = res.count;
      _hasMore = res.hasMore;
    } catch (e) {
      _error = AdminApiService.extractError(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> loadMore() async {
    if (!_hasMore || _isLoadingMore || _isLoading) return;
    _isLoadingMore = true;
    _page += 1;
    notifyListeners();

    try {
      final res = await _api.list(endpoint, query: _buildQuery(page: _page));
      _items = [..._items, ...res.results];
      _count = res.count;
      _hasMore = res.hasMore;
    } catch (e) {
      _error = AdminApiService.extractError(e);
      _page -= 1;
    }

    _isLoadingMore = false;
    notifyListeners();
  }

  Future<void> refresh() => load(reset: true);

  Future<void> setSearch(String value) async {
    if (value == _search) return;
    _search = value;
    await load(reset: true);
  }

  Future<void> setBaseQuery(Map<String, dynamic> q) async {
    baseQuery = q;
    await load(reset: true);
  }

  /// Remove an item locally after an approve/reject/delete so the UI reacts
  /// immediately without a full round-trip.
  void removeById(int id) {
    _items = _items.where((m) => (m['id'] as num?)?.toInt() != id).toList();
    if (_count > 0) _count -= 1;
    notifyListeners();
  }

  /// Replace an item in place after an edit.
  void replace(Map<String, dynamic> updated) {
    final id = (updated['id'] as num?)?.toInt();
    if (id == null) return;
    _items = [
      for (final it in _items)
        if ((it['id'] as num?)?.toInt() == id) updated else it,
    ];
    notifyListeners();
  }
}
