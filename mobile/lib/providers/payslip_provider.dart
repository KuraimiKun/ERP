import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/payslip.dart';
import '../services/api_service.dart';

class PayslipProvider extends ChangeNotifier {
  final ApiService _api;

  List<PayslipSummary> _payslips = [];
  PayslipDetail? _currentDetail;
  bool _isLoading = false;
  String? _error;

  PayslipProvider(this._api);

  List<PayslipSummary> get payslips => _payslips;
  PayslipDetail? get currentDetail => _currentDetail;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadPayslips() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.payslips);
      _payslips = (response.data['payslips'] as List? ?? [])
          .map((e) => PayslipSummary.fromJson(e))
          .toList();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> loadPayslipDetail(int id) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.payslipDetail(id));
      _currentDetail = PayslipDetail.fromJson(response.data);
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }
}
