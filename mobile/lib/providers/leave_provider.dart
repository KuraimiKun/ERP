import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/leave_request.dart';
import '../services/api_service.dart';

class LeaveProvider extends ChangeNotifier {
  final ApiService _api;

  List<LeaveRequest> _leaves = [];
  List<LeaveBalance> _balances = [];
  List<LeaveType> _leaveTypes = [];
  bool _isLoading = false;
  String? _error;

  LeaveProvider(this._api);

  List<LeaveRequest> get leaves => _leaves;
  List<LeaveBalance> get balances => _balances;
  List<LeaveType> get leaveTypes => _leaveTypes;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadLeaves({String? status}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final params = <String, dynamic>{};
      if (status != null && status.isNotEmpty) params['status'] = status;

      final response = await _api.get(ApiConfig.leaves, queryParams: params);
      final data = response.data;

      _leaves = (data['leaves'] as List? ?? [])
          .map((e) => LeaveRequest.fromJson(e))
          .toList();
      _balances = (data['balances'] as List? ?? [])
          .map((e) => LeaveBalance.fromJson(e))
          .toList();
      _leaveTypes = (data['leave_types'] as List? ?? [])
          .map((e) => LeaveType.fromJson(e))
          .toList();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> createLeave({
    required int leaveTypeId,
    required String startDate,
    required String endDate,
    String reason = '',
  }) async {
    try {
      await _api.post(ApiConfig.leaves, data: {
        'leave_type_id': leaveTypeId,
        'start_date': startDate,
        'end_date': endDate,
        'reason': reason,
      });
      await loadLeaves();
      return true;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return false;
    }
  }

  Future<bool> cancelLeave(int leaveId) async {
    try {
      await _api.post(ApiConfig.leaveCancel(leaveId));
      await loadLeaves();
      return true;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return false;
    }
  }
}
