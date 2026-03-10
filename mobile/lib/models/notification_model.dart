class AppNotification {
  final int id;
  final String type;
  final String title;
  final String message;
  final bool isRead;
  final String createdAt;
  final String actionUrl;

  AppNotification({
    required this.id,
    this.type = '',
    required this.title,
    required this.message,
    this.isRead = false,
    this.createdAt = '',
    this.actionUrl = '',
  });

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    return AppNotification(
      id: json['id'],
      type: json['type'] ?? '',
      title: json['title'] ?? '',
      message: json['message'] ?? '',
      isRead: json['is_read'] ?? false,
      createdAt: json['created_at'] ?? '',
      actionUrl: json['action_url'] ?? '',
    );
  }
}
