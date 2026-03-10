import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../config/api_config.dart';
import '../models/notification_model.dart';
import '../services/api_service.dart';

class NotificationProvider extends ChangeNotifier {
  final ApiService _api;

  List<AppNotification> _notifications = [];
  int _unreadCount = 0;
  bool _isLoading = false;
  String? _error;

  NotificationProvider(this._api);

  List<AppNotification> get notifications => _notifications;
  int get unreadCount => _unreadCount;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadNotifications() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _api.get(ApiConfig.notifications);
      final data = response.data;

      _notifications = (data['notifications'] as List? ?? [])
          .map((e) => AppNotification.fromJson(e))
          .toList();
      _unreadCount = data['unread_count'] ?? 0;
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> markAllRead() async {
    try {
      await _api.post(ApiConfig.notificationsRead, data: {'all': true});
      for (var i = 0; i < _notifications.length; i++) {
        final n = _notifications[i];
        if (!n.isRead) {
          _notifications[i] = AppNotification(
            id: n.id,
            type: n.type,
            title: n.title,
            message: n.message,
            isRead: true,
            createdAt: n.createdAt,
            actionUrl: n.actionUrl,
          );
        }
      }
      _unreadCount = 0;
      notifyListeners();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
    }
  }

  Future<void> markRead(List<int> ids) async {
    try {
      await _api.post(ApiConfig.notificationsRead, data: {'ids': ids});
      for (var i = 0; i < _notifications.length; i++) {
        final n = _notifications[i];
        if (ids.contains(n.id) && !n.isRead) {
          _notifications[i] = AppNotification(
            id: n.id,
            type: n.type,
            title: n.title,
            message: n.message,
            isRead: true,
            createdAt: n.createdAt,
            actionUrl: n.actionUrl,
          );
          _unreadCount--;
        }
      }
      notifyListeners();
    } on DioException catch (e) {
      _error = ApiService.getErrorMessage(e);
      notifyListeners();
    }
  }
}
