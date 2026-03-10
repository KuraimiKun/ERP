class POSTerminal {
  final int id;
  final String code;
  final String name;
  final String nameAr;
  final String location;
  final bool hasOpenSession;
  final int? openSessionId;
  final String? openSessionNumber;

  POSTerminal({
    required this.id,
    required this.code,
    required this.name,
    this.nameAr = '',
    this.location = '',
    this.hasOpenSession = false,
    this.openSessionId,
    this.openSessionNumber,
  });

  factory POSTerminal.fromJson(Map<String, dynamic> json) {
    return POSTerminal(
      id: json['id'],
      code: json['code'] ?? '',
      name: json['name'] ?? '',
      nameAr: json['name_ar'] ?? '',
      location: json['location'] ?? '',
      hasOpenSession: json['has_open_session'] ?? false,
      openSessionId: json['open_session_id'],
      openSessionNumber: json['open_session_number'],
    );
  }
}
