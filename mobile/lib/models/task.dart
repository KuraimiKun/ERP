class Task {
  final int id;
  final String title;
  final String description;
  final String priority;
  final String status;
  final String? dueDate;
  final String? completedDate;
  final String createdAt;
  final int commentCount;

  Task({
    required this.id,
    required this.title,
    this.description = '',
    this.priority = 'medium',
    this.status = 'todo',
    this.dueDate,
    this.completedDate,
    this.createdAt = '',
    this.commentCount = 0,
  });

  factory Task.fromJson(Map<String, dynamic> json) {
    return Task(
      id: json['id'],
      title: json['title'] ?? '',
      description: json['description'] ?? '',
      priority: json['priority'] ?? 'medium',
      status: json['status'] ?? 'todo',
      dueDate: json['due_date'],
      completedDate: json['completed_date'],
      createdAt: json['created_at'] ?? '',
      commentCount: json['comment_count'] ?? 0,
    );
  }

  bool get isOverdue {
    if (dueDate == null || status == 'completed') return false;
    try {
      return DateTime.parse(dueDate!).isBefore(DateTime.now());
    } catch (_) {
      return false;
    }
  }
}

class TaskComment {
  final int id;
  final String author;
  final String content;
  final String createdAt;

  TaskComment({
    required this.id,
    required this.author,
    required this.content,
    this.createdAt = '',
  });

  factory TaskComment.fromJson(Map<String, dynamic> json) {
    return TaskComment(
      id: json['id'],
      author: json['author'] ?? '',
      content: json['content'] ?? '',
      createdAt: json['created_at'] ?? '',
    );
  }
}

class TaskCounts {
  final int total;
  final int todo;
  final int inProgress;
  final int completed;

  TaskCounts({
    this.total = 0,
    this.todo = 0,
    this.inProgress = 0,
    this.completed = 0,
  });

  factory TaskCounts.fromJson(Map<String, dynamic> json) {
    return TaskCounts(
      total: json['total'] ?? 0,
      todo: json['todo'] ?? 0,
      inProgress: json['in_progress'] ?? 0,
      completed: json['completed'] ?? 0,
    );
  }
}

class TaskStatus {
  final String value;
  final String label;

  TaskStatus({required this.value, required this.label});

  factory TaskStatus.fromJson(Map<String, dynamic> json) {
    return TaskStatus(
      value: json['value'] ?? '',
      label: json['label'] ?? '',
    );
  }
}
