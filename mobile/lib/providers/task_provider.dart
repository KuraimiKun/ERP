import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/task.dart';
import '../services/api_service.dart';

class TaskProvider extends ChangeNotifier {
  final ApiService _api;

  List<Task> _tasks = [];
  TaskCounts _counts = TaskCounts();
  List<TaskStatus> _statuses = [];
  Task? _currentTask;
  List<TaskComment> _comments = [];
  bool _isLoading = false;
  String? _error;

  TaskProvider(this._api);

  List<Task> get tasks => _tasks;
  TaskCounts get counts => _counts;
  List<TaskStatus> get statuses => _statuses;
  Task? get currentTask => _currentTask;
  List<TaskComment> get comments => _comments;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadTasks({String? status}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final params = <String, dynamic>{};
      if (status != null && status.isNotEmpty) params['status'] = status;

      final response = await _api.get(ApiConfig.tasks, queryParams: params);
      final data = response.data;

      _tasks = (data['tasks'] as List? ?? [])
          .map((e) => Task.fromJson(e))
          .toList();
      _counts = TaskCounts.fromJson(data['counts'] ?? {});
      _statuses = (data['statuses'] as List? ?? [])
          .map((e) => TaskStatus.fromJson(e))
          .toList();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> loadTaskDetail(int id) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.taskDetail(id));
      final data = response.data;

      _currentTask = Task.fromJson(data['task']);
      _comments = (data['comments'] as List? ?? [])
          .map((e) => TaskComment.fromJson(e))
          .toList();
      _statuses = (data['statuses'] as List? ?? [])
          .map((e) => TaskStatus.fromJson(e))
          .toList();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> updateStatus(int taskId, String newStatus) async {
    try {
      await _api.post(
        ApiConfig.taskStatus(taskId),
        data: {'status': newStatus},
      );
      await loadTaskDetail(taskId);
      return true;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return false;
    }
  }

  Future<bool> addComment(int taskId, String content) async {
    try {
      await _api.post(
        ApiConfig.taskComment(taskId),
        data: {'content': content},
      );
      await loadTaskDetail(taskId);
      return true;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
      return false;
    }
  }
}
