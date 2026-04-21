import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../models/payslip.dart';
import '../../providers/payslip_provider.dart';
import '../../widgets/status_badge.dart';

class PayslipListScreen extends StatefulWidget {
  const PayslipListScreen({super.key});

  @override
  State<PayslipListScreen> createState() => _PayslipListScreenState();
}

class _PayslipListScreenState extends State<PayslipListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<PayslipProvider>().loadPayslips();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<PayslipProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? MColors.darkBg : MColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => Navigator.maybePop(context),
                    child: Icon(Icons.arrow_back_ios_new_rounded, size: 20,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const Spacer(),
                  Text('Payslips', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),
            Expanded(
              child: provider.isLoading
                  ? const _Shimmer()
                  : provider.payslips.isEmpty
                      ? const _Empty()
                      : RefreshIndicator(
                          onRefresh: () => provider.loadPayslips(),
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                            itemCount: provider.payslips.length,
                            itemBuilder: (ctx, i) => _PayslipTile(
                              payslip: provider.payslips[i],
                            ),
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PayslipTile extends StatelessWidget {
  final PayslipSummary payslip;
  const _PayslipTile({required this.payslip});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, AppRoutes.payslipDetail, arguments: payslip.id),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isDark ? MColors.darkSurface : MColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    payslip.periodStart,
                    style: TextStyle(
                      fontSize: 11.5, fontWeight: FontWeight.w600,
                      color: isDark ? MColors.darkTextSub : MColors.textSub,
                      letterSpacing: 0.4,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    payslip.netSalary,
                    style: TextStyle(
                      fontSize: 20, fontWeight: FontWeight.w700,
                      letterSpacing: -0.3,
                      color: isDark ? MColors.darkText : MColors.text,
                    ),
                  ),
                  const SizedBox(height: 10),
                  StatusBadge(kind: statusToBadge(payslip.status), small: true),
                ],
              ),
            ),
            Icon(Icons.chevron_right_rounded, size: 18,
                color: isDark ? MColors.darkTextFaint : MColors.textFaint),
          ],
        ),
      ),
    );
  }
}

class _Shimmer extends StatelessWidget {
  const _Shimmer();
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF1F2937) : const Color(0xFFE2E8F0);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(children: List.generate(5, (_) => Container(
        height: 90, margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(16)),
      ))),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty();
  @override
  Widget build(BuildContext context) => Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.receipt_long_outlined, size: 56, color: AppTheme.semantics(context).textFaint),
      const SizedBox(height: 12),
      Text('No payslips yet', style: TextStyle(color: AppTheme.semantics(context).textSub)),
    ]),
  );
}
