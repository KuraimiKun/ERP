class PayslipSummary {
  final int id;
  final String periodStart;
  final String periodEnd;
  final String basicSalary;
  final String grossSalary;
  final String totalDeductions;
  final String netSalary;
  final String status;
  final String? paymentDate;

  PayslipSummary({
    required this.id,
    required this.periodStart,
    required this.periodEnd,
    this.basicSalary = '0',
    this.grossSalary = '0',
    this.totalDeductions = '0',
    this.netSalary = '0',
    this.status = '',
    this.paymentDate,
  });

  factory PayslipSummary.fromJson(Map<String, dynamic> json) {
    return PayslipSummary(
      id: json['id'],
      periodStart: json['period_start'] ?? '',
      periodEnd: json['period_end'] ?? '',
      basicSalary: json['basic_salary']?.toString() ?? '0',
      grossSalary: json['gross_salary']?.toString() ?? '0',
      totalDeductions: json['total_deductions']?.toString() ?? '0',
      netSalary: json['net_salary']?.toString() ?? '0',
      status: json['status'] ?? '',
      paymentDate: json['payment_date'],
    );
  }
}

class PayslipDetail {
  final PayslipSummary payslip;
  final List<PayslipLine> earnings;
  final List<PayslipLine> deductions;

  PayslipDetail({
    required this.payslip,
    required this.earnings,
    required this.deductions,
  });

  factory PayslipDetail.fromJson(Map<String, dynamic> json) {
    return PayslipDetail(
      payslip: PayslipSummary.fromJson(json['payslip']),
      earnings: (json['earnings'] as List? ?? [])
          .map((e) => PayslipLine.fromJson(e))
          .toList(),
      deductions: (json['deductions'] as List? ?? [])
          .map((e) => PayslipLine.fromJson(e))
          .toList(),
    );
  }
}

class PayslipLine {
  final String type;
  final String description;
  final String amount;

  PayslipLine({
    required this.type,
    this.description = '',
    required this.amount,
  });

  factory PayslipLine.fromJson(Map<String, dynamic> json) {
    return PayslipLine(
      type: json['type'] ?? '',
      description: json['description'] ?? '',
      amount: json['amount']?.toString() ?? '0',
    );
  }
}
