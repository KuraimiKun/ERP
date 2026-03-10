import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/attendance.dart';
import '../models/payslip.dart';
import '../services/api_service.dart';

class DashboardData {
  final TodayAttendance? todayAttendance;
  final MonthStats monthStats;
  final int pendingLeaves;
  final int pendingTasks;
  final int unreadNotifications;
  final List<PayslipSummary> recentPayslips;

  DashboardData({
    this.todayAttendance,
    required this.monthStats,
    this.pendingLeaves = 0,
    this.pendingTasks = 0,
    this.unreadNotifications = 0,
    this.recentPayslips = const [],
  });
}

class MonthStats {
  final int totalDays;
  final int present;
  final int absent;
  final int late;

  MonthStats({
    this.totalDays = 0,
    this.present = 0,
    this.absent = 0,
    this.late = 0,
  });

  factory MonthStats.fromJson(Map<String, dynamic> json) {
    return MonthStats(
      totalDays: json['total_days'] ?? 0,
      present: json['present'] ?? 0,
      absent: json['absent'] ?? 0,
      late: json['late'] ?? 0,
    );
  }
}

class DashboardProvider extends ChangeNotifier {
  final ApiService _api;

  DashboardData? _data;
  bool _isLoading = false;
  String? _error;

  DashboardProvider(this._api);

  DashboardData? get data => _data;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadDashboard() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.dashboard);
      final d = response.data;

      _data = DashboardData(
        todayAttendance: d['today_attendance'] != null
            ? TodayAttendance.fromJson(d['today_attendance'])
            : null,
        monthStats: MonthStats.fromJson(d['month_stats'] ?? {}),
        pendingLeaves: d['pending_leaves'] ?? 0,
        pendingTasks: d['pending_tasks'] ?? 0,
        unreadNotifications: d['unread_notifications'] ?? 0,
        recentPayslips: (d['recent_payslips'] as List? ?? [])
            .map((e) => PayslipSummary.fromJson(e))
            .toList(),
      );
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }
}
