// Models for the admin-mobile portal (consumes /api/mobile/admin/v1/*).

class AdminUser {
  final int id;
  final String email;
  final String firstName;
  final String lastName;
  final bool isSuperuser;
  final String role; // 'owner' | 'admin'
  final AdminCompany? company;
  final AdminEmployeeProfile? employee;
  final Map<String, dynamic> featureFlags;

  const AdminUser({
    required this.id,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.isSuperuser,
    required this.role,
    this.company,
    this.employee,
    this.featureFlags = const {},
  });

  String get fullName =>
      [firstName, lastName].where((s) => s.isNotEmpty).join(' ');

  String get initials {
    final f = firstName.isNotEmpty ? firstName[0] : '';
    final l = lastName.isNotEmpty ? lastName[0] : '';
    final s = (f + l).toUpperCase();
    return s.isEmpty ? '?' : s;
  }

  /// Build from /auth/login/ response (no `user` envelope).
  factory AdminUser.fromLoginJson(Map<String, dynamic> json) {
    final emp = json['employee'] as Map<String, dynamic>?;
    return AdminUser(
      id: emp?['id'] ?? 0,
      email: emp?['email'] ?? '',
      firstName: emp?['first_name'] ?? '',
      lastName: emp?['last_name'] ?? '',
      isSuperuser: false,
      role: json['role'] ?? 'admin',
      company: json['company'] != null
          ? AdminCompany.fromJson(json['company'])
          : null,
      employee: emp != null ? AdminEmployeeProfile.fromJson(emp) : null,
      featureFlags: Map<String, dynamic>.from(json['feature_flags'] ?? {}),
    );
  }

  /// Build from /auth/me/ response (has `user` envelope).
  factory AdminUser.fromMeJson(Map<String, dynamic> json) {
    final u = json['user'] as Map<String, dynamic>? ?? {};
    final emp = json['employee'] as Map<String, dynamic>?;
    return AdminUser(
      id: u['id'] ?? 0,
      email: u['email'] ?? '',
      firstName: u['first_name'] ?? '',
      lastName: u['last_name'] ?? '',
      isSuperuser: u['is_superuser'] ?? false,
      role: json['role'] ?? 'admin',
      company: json['company'] != null
          ? AdminCompany.fromJson(json['company'])
          : null,
      employee: emp != null ? AdminEmployeeProfile.fromJson(emp) : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'first_name': firstName,
        'last_name': lastName,
        'is_superuser': isSuperuser,
        'role': role,
        if (company != null) 'company': company!.toJson(),
        if (employee != null) 'employee': employee!.toJson(),
        'feature_flags': featureFlags,
      };

  factory AdminUser.fromStoredJson(Map<String, dynamic> json) => AdminUser(
        id: json['id'] ?? 0,
        email: json['email'] ?? '',
        firstName: json['first_name'] ?? '',
        lastName: json['last_name'] ?? '',
        isSuperuser: json['is_superuser'] ?? false,
        role: json['role'] ?? 'admin',
        company: json['company'] != null
            ? AdminCompany.fromJson(json['company'])
            : null,
        employee: json['employee'] != null
            ? AdminEmployeeProfile.fromJson(json['employee'])
            : null,
        featureFlags: Map<String, dynamic>.from(json['feature_flags'] ?? {}),
      );
}

class AdminCompany {
  final int id;
  final String name;
  final String nameAr;
  final bool aiEnabled;

  const AdminCompany({
    required this.id,
    required this.name,
    required this.nameAr,
    this.aiEnabled = false,
  });

  factory AdminCompany.fromJson(Map<String, dynamic> json) => AdminCompany(
        id: json['id'] ?? 0,
        name: json['name'] ?? '',
        nameAr: json['name_ar'] ?? '',
        aiEnabled: json['ai_enabled'] ?? false,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'name_ar': nameAr,
        'ai_enabled': aiEnabled,
      };
}

class AdminEmployeeProfile {
  final int id;
  final String employeeId;
  final String firstName;
  final String lastName;
  final String email;
  final String jobTitle;

  const AdminEmployeeProfile({
    required this.id,
    required this.employeeId,
    required this.firstName,
    required this.lastName,
    required this.email,
    this.jobTitle = '',
  });

  factory AdminEmployeeProfile.fromJson(Map<String, dynamic> json) =>
      AdminEmployeeProfile(
        id: json['id'] ?? 0,
        employeeId: json['employee_id'] ?? '',
        firstName: json['first_name'] ?? '',
        lastName: json['last_name'] ?? '',
        email: json['email'] ?? '',
        jobTitle: json['job_title'] ?? '',
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'employee_id': employeeId,
        'first_name': firstName,
        'last_name': lastName,
        'email': email,
        'job_title': jobTitle,
      };
}
