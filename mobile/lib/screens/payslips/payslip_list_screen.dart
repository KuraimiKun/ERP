import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/payslip_provider.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/loading_indicator.dart';
import '../../widgets/empty_state.dart';

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
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<PayslipProvider>();

    return Scaffold(
      appBar: AppBar(title: Text(l10n.payslips)),
      drawer: const AppDrawer(),
      body: provider.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : RefreshIndicator(
              onRefresh: () => provider.loadPayslips(),
              child: provider.payslips.isEmpty
                  ? EmptyState(
                      icon: Icons.receipt_long_outlined,
                      message: l10n.noData,
                    )
                  : ListView.builder(
                      itemCount: provider.payslips.length,
                      padding: const EdgeInsets.all(16),
                      itemBuilder: (context, index) {
                        final p = provider.payslips[index];
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: AppTheme.semantics(context).successContainer,
                              child: Icon(Icons.receipt_long,
                                  color: AppTheme.semantics(context).success),
                            ),
                            title: Text(
                                '${p.periodStart} - ${p.periodEnd}'),
                            subtitle: Text(
                              '${l10n.netSalary}: ${p.netSalary}',
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600),
                            ),
                            trailing: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: p.status == 'paid'
                                    ? AppTheme.semantics(context).successContainer
                                    : Theme.of(context).colorScheme.primaryContainer,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                p.status,
                                style: TextStyle(
                                  color: p.status == 'paid'
                                      ? AppTheme.semantics(context).success
                                      : Theme.of(context).colorScheme.primary,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                            onTap: () => Navigator.pushNamed(
                              context,
                              AppRoutes.payslipDetail,
                              arguments: p.id,
                            ),
                          ),
                        );
                      },
                    ),
            ),
    );
  }
}
