import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../models/payslip.dart';
import '../../providers/payslip_provider.dart';
import '../../widgets/status_badge.dart';

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
    final provider = context.watch<PayslipProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? MColors.darkBg : MColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => Navigator.pop(context),
                    child: Icon(Icons.arrow_back_ios_new_rounded, size: 20,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const Spacer(),
                  Text('Payslip', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  Icon(Icons.share_outlined, size: 18,
                      color: isDark ? MColors.darkText : MColors.text),
                ],
              ),
            ),
            Expanded(
              child: provider.isLoading
                  ? const _Shimmer()
                  : provider.currentDetail == null
                      ? const _Error()
                      : _DetailBody(detail: provider.currentDetail!),
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailBody extends StatelessWidget {
  final PayslipDetail detail;
  const _DetailBody({required this.detail});

  @override
  Widget build(BuildContext context) {
    final p = detail.payslip;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primary = isDark ? MColors.darkPrimary : MColors.primary;
    final primaryDeep = isDark ? MColors.darkPrimaryDeep : MColors.primaryDeep;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
      children: [
        // Header card
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: isDark ? MColors.darkSurface : MColors.surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
          ),
          child: Stack(
            children: [
              Positioned(
                top: 0, right: 0,
                child: Container(
                  width: 120, height: 120,
                  decoration: BoxDecoration(
                    gradient: RadialGradient(
                      colors: [
                        (isDark ? MColors.darkPrimarySoft : MColors.primarySoft).withValues(alpha: 0.8),
                        Colors.transparent,
                      ],
                    ),
                    borderRadius: BorderRadius.circular(60),
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Pay period', style: TextStyle(
                            fontSize: 11, fontWeight: FontWeight.w600,
                            color: isDark ? MColors.darkTextSub : MColors.textSub,
                          )),
                          const SizedBox(height: 4),
                          Text(p.periodStart, style: TextStyle(
                            fontSize: 20, fontWeight: FontWeight.w700,
                            letterSpacing: -0.4,
                            color: isDark ? MColors.darkText : MColors.text,
                          )),
                        ],
                      ),
                      StatusBadge(kind: statusToBadge(p.status)),
                    ],
                  ),
                  Divider(height: 28, color: isDark ? MColors.darkBorder : MColors.border),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _HeaderInfo(label: 'Basic salary', value: p.basicSalary),
                      if (p.paymentDate != null)
                        _HeaderInfo(label: 'Paid on', value: p.paymentDate!, align: TextAlign.right),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),

        const SizedBox(height: 14),

        // Earnings
        _PayGroup(
          label: 'Earnings',
          total: p.grossSalary,
          items: detail.earnings,
          isPositive: true,
        ),

        const SizedBox(height: 10),

        // Deductions
        _PayGroup(
          label: 'Deductions',
          total: p.totalDeductions,
          items: detail.deductions,
          isPositive: false,
        ),

        const SizedBox(height: 14),

        // Net salary
        Container(
          padding: const EdgeInsets.all(22),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [primary, primaryDeep],
            ),
            borderRadius: BorderRadius.circular(18),
          ),
          child: Stack(
            children: [
              Positioned(
                bottom: -40, right: -40,
                child: Container(
                  width: 160, height: 160,
                  decoration: const BoxDecoration(
                    color: Color(0x14FFFFFF), shape: BoxShape.circle,
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('NET SALARY',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                          color: Color(0xCCFFFFFF), letterSpacing: 0.8)),
                  const SizedBox(height: 6),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(p.netSalary,
                          style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w700,
                              color: Colors.white, letterSpacing: -0.8)),
                      const SizedBox(width: 8),
                      const Text('SAR',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600,
                              color: Color(0xCCFFFFFF))),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),

        const SizedBox(height: 14),

        Row(
          children: [
            Expanded(child: _ActionBtn(icon: Icons.download_outlined, label: 'Download PDF')),
            const SizedBox(width: 10),
            Expanded(child: _ActionBtn(icon: Icons.print_outlined, label: 'Print')),
          ],
        ),
      ],
    );
  }
}

class _HeaderInfo extends StatelessWidget {
  final String label, value;
  final TextAlign align;
  const _HeaderInfo({required this.label, required this.value, this.align = TextAlign.left});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Column(
      crossAxisAlignment: align == TextAlign.right
          ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(fontSize: 11, color: isDark ? MColors.darkTextSub : MColors.textSub)),
        const SizedBox(height: 2),
        Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
            color: isDark ? MColors.darkText : MColors.text)),
      ],
    );
  }
}

class _PayGroup extends StatelessWidget {
  final String label, total;
  final List<PayslipLine> items;
  final bool isPositive;
  const _PayGroup({required this.label, required this.total, required this.items, required this.isPositive});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final col = isPositive ? sem.success : sem.danger;
    final bg = isPositive ? sem.successContainer : sem.dangerContainer;

    return Container(
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Container(
            color: bg,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(children: [
                  Container(width: 6, height: 6, decoration: BoxDecoration(color: col, shape: BoxShape.circle)),
                  const SizedBox(width: 8),
                  Text(label.toUpperCase(), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700,
                      color: col, letterSpacing: 0.4)),
                ]),
                Text('${isPositive ? '+' : '−'} $total SAR',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: col)),
              ],
            ),
          ),
          ...items.asMap().entries.map((e) {
            final i = e.key; final item = e.value;
            return Container(
              decoration: BoxDecoration(
                border: i > 0 ? Border(top: BorderSide(
                    color: isDark ? MColors.darkBorder : MColors.borderSoft, width: 0.5)) : null,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(item.description, style: TextStyle(fontSize: 13,
                      color: isDark ? MColors.darkTextMid : MColors.textMid)),
                  Text(item.amount, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
                      color: isDark ? MColors.darkText : MColors.text)),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}

class _ActionBtn extends StatelessWidget {
  final IconData icon;
  final String label;
  const _ActionBtn({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      height: 48,
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 16, color: isDark ? MColors.darkTextMid : MColors.textMid),
          const SizedBox(width: 8),
          Text(label, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
              color: isDark ? MColors.darkText : MColors.text)),
        ],
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
      child: Column(children: [
        Container(height: 140, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(18))),
        const SizedBox(height: 14),
        Container(height: 120, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(16))),
        const SizedBox(height: 10),
        Container(height: 100, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(16))),
      ]),
    );
  }
}

class _Error extends StatelessWidget {
  const _Error();
  @override
  Widget build(BuildContext context) => Center(
    child: Text('Could not load payslip',
        style: TextStyle(color: AppTheme.semantics(context).textSub)),
  );
}
