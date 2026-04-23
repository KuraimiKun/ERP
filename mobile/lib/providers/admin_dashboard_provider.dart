import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../config/api_config.dart';
import '../models/admin/admin_dashboard.dart';
import '../services/api_service.dart';

class AdminDashboardProvider extends ChangeNotifier {
  final ApiService _api;

  AdminDashboardSummary? _summary;
  AdminDashboardKpis? _kpis;
  List<AdminActivityEntry> _activity = const [];
  bool _isLoading = false;
  String? _error;

  AdminDashboardProvider(this._api);

  AdminDashboardSummary? get summary => _summary;
  AdminDashboardKpis? get kpis => _kpis;
  List<AdminActivityEntry> get activity => _activity;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadAll() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final responses = await Future.wait([
        _api.get(ApiConfig.adminDashboard),
        _api.get(ApiConfig.adminDashboardKpis),
        _api.get(ApiConfig.adminDashboardActivity),
      ]);

      _summary = AdminDashboardSummary.fromJson(
        Map<String, dynamic>.from(responses[0].data as Map),
      );
      _kpis = AdminDashboardKpis.fromJson(
        Map<String, dynamic>.from(responses[1].data as Map),
      );

      final rawActivity = responses[2].data;
      final list = rawActivity is List ? rawActivity : <dynamic>[];
      _activity = list
          .whereType<Map>()
          .map((m) => AdminActivityEntry.fromJson(
              Map<String, dynamic>.from(m)))
          .toList();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  void clear() {
    _summary = null;
    _kpis = null;
    _activity = const [];
    _error = null;
    notifyListeners();
  }
}
