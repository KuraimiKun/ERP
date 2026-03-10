class EmployeePermissions {
  final bool canScanQr;
  final bool canViewAttendance;
  final bool canManageLeaves;
  final bool canViewPayslips;
  final bool canEditProfile;
  final bool canViewTasks;
  final bool canUsePOS;

  EmployeePermissions({
    this.canScanQr = false,
    this.canViewAttendance = false,
    this.canManageLeaves = false,
    this.canViewPayslips = false,
    this.canEditProfile = false,
    this.canViewTasks = false,
    this.canUsePOS = false,
  });

  factory EmployeePermissions.fromJson(Map<String, dynamic> json) {
    return EmployeePermissions(
      canScanQr: json['can_scan_qr'] ?? false,
      canViewAttendance: json['can_view_attendance'] ?? false,
      canManageLeaves: json['can_manage_leaves'] ?? false,
      canViewPayslips: json['can_view_payslips'] ?? false,
      canEditProfile: json['can_edit_profile'] ?? false,
      canViewTasks: json['can_view_tasks'] ?? false,
      canUsePOS: json['can_use_pos'] ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'can_scan_qr': canScanQr,
        'can_view_attendance': canViewAttendance,
        'can_manage_leaves': canManageLeaves,
        'can_view_payslips': canViewPayslips,
        'can_edit_profile': canEditProfile,
        'can_view_tasks': canViewTasks,
        'can_use_pos': canUsePOS,
      };
}

class Employee {
  final int id;
  final String employeeId;
  final String firstName;
  final String lastName;
  final String firstNameAr;
  final String lastNameAr;
  final String email;
  final String phone;
  final String department;
  final String departmentAr;
  final String jobTitle;
  final String photoUrl;
  final EmployeePermissions permissions;

  // Extended profile fields
  final String? gender;
  final String? dateOfBirth;
  final String? nationality;
  final String? emergencyContactName;
  final String? emergencyContactPhone;
  final String? address;
  final String? city;
  final String? country;
  final String? hireDate;
  final String? employmentType;
  final String? employmentStatus;
  final String? branch;

  Employee({
    required this.id,
    required this.employeeId,
    required this.firstName,
    required this.lastName,
    this.firstNameAr = '',
    this.lastNameAr = '',
    required this.email,
    this.phone = '',
    this.department = '',
    this.departmentAr = '',
    this.jobTitle = '',
    this.photoUrl = '',
    required this.permissions,
    this.gender,
    this.dateOfBirth,
    this.nationality,
    this.emergencyContactName,
    this.emergencyContactPhone,
    this.address,
    this.city,
    this.country,
    this.hireDate,
    this.employmentType,
    this.employmentStatus,
    this.branch,
  });

  String get fullName => '$firstName $lastName';
  String get fullNameAr =>
      firstNameAr.isNotEmpty ? '$firstNameAr $lastNameAr' : fullName;

  factory Employee.fromJson(Map<String, dynamic> json) {
    return Employee(
      id: json['id'],
      employeeId: json['employee_id'] ?? '',
      firstName: json['first_name'] ?? '',
      lastName: json['last_name'] ?? '',
      firstNameAr: json['first_name_ar'] ?? '',
      lastNameAr: json['last_name_ar'] ?? '',
      email: json['email'] ?? '',
      phone: json['phone'] ?? '',
      department: json['department'] ?? '',
      departmentAr: json['department_ar'] ?? '',
      jobTitle: json['job_title'] ?? '',
      photoUrl: json['photo_url'] ?? '',
      permissions: EmployeePermissions.fromJson(json['permissions'] ?? {}),
      gender: json['gender'],
      dateOfBirth: json['date_of_birth'],
      nationality: json['nationality'],
      emergencyContactName: json['emergency_contact_name'],
      emergencyContactPhone: json['emergency_contact_phone'],
      address: json['address'],
      city: json['city'],
      country: json['country'],
      hireDate: json['hire_date'],
      employmentType: json['employment_type'],
      employmentStatus: json['employment_status'],
      branch: json['branch'],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'employee_id': employeeId,
        'first_name': firstName,
        'last_name': lastName,
        'first_name_ar': firstNameAr,
        'last_name_ar': lastNameAr,
        'email': email,
        'phone': phone,
        'department': department,
        'department_ar': departmentAr,
        'job_title': jobTitle,
        'photo_url': photoUrl,
        'permissions': permissions.toJson(),
      };
}
