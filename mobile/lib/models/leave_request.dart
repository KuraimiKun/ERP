class LeaveType {
  final int id;
  final String name;
  final String nameAr;
  final int daysAllowed;

  LeaveType({
    required this.id,
    required this.name,
    this.nameAr = '',
    this.daysAllowed = 0,
  });

  factory LeaveType.fromJson(Map<String, dynamic> json) {
    return LeaveType(
      id: json['id'],
      name: json['name'] ?? '',
      nameAr: json['name_ar'] ?? '',
      daysAllowed: json['days_allowed'] ?? 0,
    );
  }
}

class LeaveBalance {
  final int leaveTypeId;
  final String name;
  final String nameAr;
  final int daysAllowed;
  final double used;
  final double remaining;
  final String color;

  LeaveBalance({
    required this.leaveTypeId,
    required this.name,
    this.nameAr = '',
    this.daysAllowed = 0,
    this.used = 0,
    this.remaining = 0,
    this.color = '#0F2644',
  });

  factory LeaveBalance.fromJson(Map<String, dynamic> json) {
    return LeaveBalance(
      leaveTypeId: json['leave_type_id'],
      name: json['name'] ?? '',
      nameAr: json['name_ar'] ?? '',
      daysAllowed: json['days_allowed'] ?? 0,
      used: (json['used'] ?? 0).toDouble(),
      remaining: (json['remaining'] ?? 0).toDouble(),
      color: json['color'] ?? '#0F2644',
    );
  }
}

class LeaveRequest {
  final int id;
  final String leaveType;
  final String leaveTypeAr;
  final String startDate;
  final String endDate;
  final double daysRequested;
  final String reason;
  final String status;
  final String createdAt;

  LeaveRequest({
    required this.id,
    required this.leaveType,
    this.leaveTypeAr = '',
    required this.startDate,
    required this.endDate,
    this.daysRequested = 0,
    this.reason = '',
    required this.status,
    this.createdAt = '',
  });

  factory LeaveRequest.fromJson(Map<String, dynamic> json) {
    return LeaveRequest(
      id: json['id'],
      leaveType: json['leave_type'] ?? '',
      leaveTypeAr: json['leave_type_ar'] ?? '',
      startDate: json['start_date'] ?? '',
      endDate: json['end_date'] ?? '',
      daysRequested: (json['days_requested'] ?? 0).toDouble(),
      reason: json['reason'] ?? '',
      status: json['status'] ?? '',
      createdAt: json['created_at'] ?? '',
    );
  }

  bool get isPending => status == 'pending';
  bool get isApproved => status == 'approved';
  bool get isRejected => status == 'rejected';
  bool get isCancelled => status == 'cancelled';
}
