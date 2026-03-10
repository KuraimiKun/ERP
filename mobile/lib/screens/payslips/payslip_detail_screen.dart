import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/payslip_provider.dart';
import '../../widgets/loading_indicator.dart';

class PayslipDetailScreen extends StatefulWidget {
  final int payslipId;

  const PayslipDetailScreen({super.key, required this.payslipId});

  @override
  State<PayslipDetailScreen> createState() => _PayslipDetailScreenState();
}

class _PayslipDetailScreenState extends State<PayslipDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<PayslipProvider>().loadPayslipDetail(widget.payslipId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<PayslipProvider>();
    final detail = provider.currentDetail;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.payslipDetail)),
      body: provider.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : detail == null
              ? Center(child: Text(l10n.error))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Summary card
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            children: [
                              _Row(
                                  l10n.periodStart,
                                  detail.payslip.periodStart),
                              _Row(l10n.periodEnd,
                                  detail.payslip.periodEnd),
                              const Divider(),
                              _Row(l10n.basicSalary,
                                  detail.payslip.basicSalary),
                              _Row(l10n.grossSalary,
                                  detail.payslip.grossSalary),
                              _Row(l10n.totalDeductions,
                                  detail.payslip.totalDeductions,
                                  isNegative: true),
                              const Divider(),
                              _Row(l10n.netSalary,
                                  detail.payslip.netSalary,
                                  isBold: true, isPositive: true),
                              if (detail.payslip.paymentDate != null)
                                _Row(l10n.paymentDate,
                                    detail.payslip.paymentDate!),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Earnings
                      if (detail.earnings.isNotEmpty) ...[
                        Text(l10n.earnings,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        Card(
                          child: Column(
                            children: detail.earnings
                                .map((e) => ListTile(
                                      title: Text(e.type),
                                      subtitle: e.description.isNotEmpty
                                          ? Text(e.description)
                                          : null,
                                      trailing: Text(
                                        e.amount,
                                        style: TextStyle(
                                          fontWeight: FontWeight.w600,
                                          color: AppTheme.semantics(context).success,
                                        ),
                                      ),
                                    ))
                                .toList(),
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Deductions
                      if (detail.deductions.isNotEmpty) ...[
                        Text(l10n.deductions,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        Card(
                          child: Column(
                            children: detail.deductions
                                .map((e) => ListTile(
                                      title: Text(e.type),
                                      subtitle: e.description.isNotEmpty
                                          ? Text(e.description)
                                          : null,
                                      trailing: Text(
                                        '-${e.amount}',
                                        style: TextStyle(
                                          fontWeight: FontWeight.w600,
                                          color: AppTheme.semantics(context).danger,
                                        ),
                                      ),
                                    ))
                                .toList(),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final String value;
  final bool isBold;
  final bool isPositive;
  final bool isNegative;

  const _Row(
    this.label,
    this.value, {
    this.isBold = false,
    this.isPositive = false,
    this.isNegative = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(
                fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
              )),
          Text(
            isNegative ? '-$value' : value,
            style: TextStyle(
              fontWeight: isBold ? FontWeight.bold : FontWeight.w600,
              color: isPositive
                  ? AppTheme.semantics(context).success
                  : isNegative
                      ? AppTheme.semantics(context).danger
                      : null,
            ),
          ),
        ],
      ),
    );
  }
}
