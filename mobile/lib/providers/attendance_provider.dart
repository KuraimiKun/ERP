import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/attendance.dart';
import '../services/api_service.dart';

class AttendanceProvider extends ChangeNotifier {
  final ApiService _api;

  List<Attendance> _attendances = [];
  AttendanceStats? _stats;
  bool _isLoading = false;
  String? _error;

  AttendanceProvider(this._api);

  List<Attendance> get attendances => _attendances;
  AttendanceStats? get stats => _stats;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadAttendance({String? startDate, String? endDate}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final params = <String, dynamic>{};
      if (startDate != null) params['start_date'] = startDate;
      if (endDate != null) params['end_date'] = endDate;

      final response =
          await _api.get(ApiConfig.attendance, queryParams: params);
      final data = response.data;

      _attendances = (data['attendances'] as List? ?? [])
          .map((e) => Attendance.fromJson(e))
          .toList();
      _stats = AttendanceStats.fromJson(data['stats'] ?? {});
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<ScanResult?> scanQR(String qrData) async {
    try {
      final response = await _api.post(
        ApiConfig.attendanceScan,
        data: {'qr_data': qrData},
      );
      return ScanResult.fromJson(response.data);
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return null;
    }
  }
}
