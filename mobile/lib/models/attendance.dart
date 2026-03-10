class Attendance {
  final int id;
  final String date;
  final String? checkIn;
  final String? checkOut;
  final String hoursWorked;
  final String overtimeHours;
  final bool isPresent;
  final bool isLate;
  final int lateMinutes;

  Attendance({
    required this.id,
    required this.date,
    this.checkIn,
    this.checkOut,
    this.hoursWorked = '0',
    this.overtimeHours = '0',
    this.isPresent = false,
    this.isLate = false,
    this.lateMinutes = 0,
  });

  factory Attendance.fromJson(Map<String, dynamic> json) {
    return Attendance(
      id: json['id'],
      date: json['date'] ?? '',
      checkIn: json['check_in'],
      checkOut: json['check_out'],
      hoursWorked: json['hours_worked']?.toString() ?? '0',
      overtimeHours: json['overtime_hours']?.toString() ?? '0',
      isPresent: json['is_present'] ?? false,
      isLate: json['is_late'] ?? false,
      lateMinutes: json['late_minutes'] ?? 0,
    );
  }
}

class AttendanceStats {
  final int present;
  final int late;
  final int absent;

  AttendanceStats({
    this.present = 0,
    this.late = 0,
    this.absent = 0,
  });

  factory AttendanceStats.fromJson(Map<String, dynamic> json) {
    return AttendanceStats(
      present: json['present'] ?? 0,
      late: json['late'] ?? 0,
      absent: json['absent'] ?? 0,
    );
  }
}

class TodayAttendance {
  final bool checkedIn;
  final bool checkedOut;
  final String? checkIn;
  final String? checkOut;
  final bool isLate;

  TodayAttendance({
    this.checkedIn = false,
    this.checkedOut = false,
    this.checkIn,
    this.checkOut,
    this.isLate = false,
  });

  factory TodayAttendance.fromJson(Map<String, dynamic> json) {
    return TodayAttendance(
      checkedIn: json['checked_in'] ?? false,
      checkedOut: json['checked_out'] ?? false,
      checkIn: json['check_in'],
      checkOut: json['check_out'],
      isLate: json['is_late'] ?? false,
    );
  }
}

class ScanResult {
  final bool success;
  final String action;
  final Attendance attendance;

  ScanResult({
    required this.success,
    required this.action,
    required this.attendance,
  });

  factory ScanResult.fromJson(Map<String, dynamic> json) {
    return ScanResult(
      success: json['success'] ?? false,
      action: json['action'] ?? '',
      attendance: Attendance.fromJson(json['attendance']),
    );
  }
}
