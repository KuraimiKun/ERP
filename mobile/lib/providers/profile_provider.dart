import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/employee.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

class ProfileProvider extends ChangeNotifier {
  final ApiService _api;
  final StorageService _storage;

  Employee? _profile;
  bool _isLoading = false;
  String? _error;

  ProfileProvider(this._api, this._storage);

  Employee? get profile => _profile;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadProfile() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.profile);
      _profile = Employee.fromJson(response.data);
      await _storage.saveEmployeeData(jsonEncode(response.data));
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> updateProfile(Map<String, dynamic> fields) async {
    try {
      final response = await _api.patch(ApiConfig.profile, data: fields);
      _profile = Employee.fromJson(response.data);
      await _storage.saveEmployeeData(jsonEncode(response.data));
      notifyListeners();
      return true;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return false;
    }
  }
}
