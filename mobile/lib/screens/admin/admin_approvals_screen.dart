import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/api_config.dart';
import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../providers/admin_list_provider.dart';
import '../../services/admin_api_service.dart';
import '../../services/api_service.dart';
import 'admin_shell.dart';

/// Unified approvals hub — one tab per pending queue.
class AdminApprovalsScreen extends StatefulWidget {
  const AdminApprovalsScreen({super.key});

  @override
  State<AdminApprovalsScreen> createState() => _AdminApprovalsScreenState();
}

class _AdminApprovalsScreenState extends State<AdminApprovalsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tab;

  static const _tabs = <_ApprovalTab>[
    _ApprovalTab(
      labelKey: 'leaves',
      endpoint: ApiConfig.adminPendingLeaves,
      titleKey: 'employee_name',
      subtitleKey: 'leave_type_name',
      icon: Icons.beach_access,
    ),
    _ApprovalTab(
      labelKey: 'expenses',
      endpoint: ApiConfig.adminPendingExpenses,
      titleKey: 'expense_number',
      subtitleKey: 'category_name',
      amountKey: 'total_amount',
      icon: Icons.receipt_long,
    ),
    _ApprovalTab(
      labelKey: 'pos',
      endpoint: ApiConfig.adminPendingPurchaseOrders,
      titleKey: 'po_number',
      subtitleKey: 'supplier_name',
      amountKey: 'total_amount',
      icon: Icons.shopping_cart,
    ),
    _ApprovalTab(
      labelKey: 'quotes',
      endpoint: ApiConfig.adminPendingQuotes,
      titleKey: 'quote_number',
      subtitleKey: 'customer_name',
      amountKey: 'total_amount',
      icon: Icons.request_quote,
    ),
    _ApprovalTab(
      labelKey: 'supplierInvoices',
      endpoint: ApiConfig.adminPendingSupplierInvoices,
      titleKey: 'invoice_number',
      subtitleKey: 'supplier_name',
      amountKey: 'total_amount',
      icon: Icons.receipt,
    ),
  ];

  String _tabLabel(_ApprovalTab t, AppLocalizations l10n) {
    switch (t.labelKey) {
      case 'leaves':
        return l10n.approvalsLeaves;
      case 'expenses':
        return l10n.approvalsExpenses;
      case 'pos':
        return l10n.approvalsPos;
      case 'quotes':
        return l10n.approvalsQuotes;
      case 'supplierInvoices':
        return l10n.approvalsSupplierInvoices;
    }
    return t.labelKey;
  }

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: _tabs.length, vsync: this);
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AdminShell(
      title: l10n.approvals,
      currentIndex: -1,
      body: Column(
        children: [
          Material(
            color: Theme.of(context).colorScheme.surface,
            child: TabBar(
              controller: _tab,
              isScrollable: true,
              tabs: [
                for (final t in _tabs)
                  Tab(icon: Icon(t.icon), text: _tabLabel(t, l10n)),
              ],
            ),
          ),
          Expanded(
            child: TabBarView(
              controller: _tab,
              children: [
                for (final t in _tabs) _ApprovalQueue(tab: t),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ApprovalTab {
  final String labelKey;
  final String endpoint;
  final String titleKey;
  final String subtitleKey;
  final String? amountKey;
  final IconData icon;

  const _ApprovalTab({
    required this.labelKey,
    required this.endpoint,
    required this.titleKey,
    required this.subtitleKey,
    this.amountKey,
    required this.icon,
  });
}

class _ApprovalQueue extends StatefulWidget {
  final _ApprovalTab tab;
  const _ApprovalQueue({required this.tab});

  @override
  State<_ApprovalQueue> createState() => _ApprovalQueueState();
}

class _ApprovalQueueState extends State<_ApprovalQueue>
    with AutomaticKeepAliveClientMixin {
  late final AdminListProvider _provider;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _provider = AdminListProvider(
      AdminApiService(context.read<ApiService>()),
      endpoint: widget.tab.endpoint,
    );
    WidgetsBinding.instance
        .addPostFrameCallback((_) => _provider.load(reset: true));
  }

  @override
  void dispose() {
    _provider.dispose();
    super.dispose();
  }

  Future<void> _action(int id, String actionName) async {
    final notes = actionName == 'reject'
        ? await _askReason(context)
        : null;
    if (actionName == 'reject' && notes == null) return;
    if (!mounted) return;

    final api = AdminApiService(context.read<ApiService>());
    try {
      await api.action(
        widget.tab.endpoint,
        id,
        actionName,
        data: actionName == 'reject' ? {'reason': notes ?? ''} : null,
      );
      _provider.removeById(id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(actionName == 'approve'
              ? (AppLocalizations.of(context)?.approved ?? 'Approved')
              : (AppLocalizations.of(context)?.rejected ?? 'Rejected')),
          backgroundColor: actionName == 'approve'
              ? AppTheme.semantics(context).success
              : AppTheme.semantics(context).warning,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AdminApiService.extractError(e)),
          backgroundColor: AppTheme.semantics(context).danger,
        ),
      );
    }
  }

  Future<String?> _askReason(BuildContext context) async {
    final ctrl = TextEditingController();
    final l10n = AppLocalizations.of(context);
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n?.rejectionReason ?? 'Rejection reason'),
        content: TextField(
          controller: ctrl,
          maxLines: 3,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(l10n?.cancel ?? 'Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, ctrl.text),
            child: Text(l10n?.reject ?? 'Reject'),
          ),
        ],
      ),
    );
    return result;
  }

  String _money(dynamic v) {
    if (v == null) return '';
    final d = double.tryParse(v.toString());
    if (d == null) return v.toString();
    return d.toStringAsFixed(2).replaceAllMapped(
        RegExp(r'\B(?=(\d{3})+(?=\.))'), (m) => ',');
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final sem = AppTheme.semantics(context);
    return ChangeNotifierProvider.value(
      value: _provider,
      child: Consumer<AdminListProvider>(
        builder: (context, p, _) {
          if (p.isLoading && p.items.isEmpty) {
            return const Center(child: CircularProgressIndicator());
          }
          if (p.error != null && p.items.isEmpty) {
            return Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.error_outline, size: 48, color: sem.danger),
                  const SizedBox(height: 12),
                  Text(p.error!, textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: () => p.load(reset: true),
                    icon: const Icon(Icons.refresh),
                    label: Text(AppLocalizations.of(context)?.retry ?? 'Retry'),
                  ),
                ],
              ),
            );
          }
          if (p.items.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.check_circle_outline,
                      size: 48, color: sem.success),
                  const SizedBox(height: 12),
                  Text(AppLocalizations.of(context)?.nothingToApprove ??
                      'Nothing to approve'),
                ],
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: p.refresh,
            child: ListView.separated(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: p.items.length,
              separatorBuilder: (_, __) =>
                  Divider(height: 1, color: sem.borderSoft),
              itemBuilder: (ctx, i) {
                final row = p.items[i];
                return _ApprovalCard(
                  title: (row[widget.tab.titleKey] ?? '—').toString(),
                  subtitle: (row[widget.tab.subtitleKey] ?? '').toString(),
                  amount: widget.tab.amountKey != null
                      ? _money(row[widget.tab.amountKey!])
                      : null,
                  onApprove: () =>
                      _action((row['id'] as num).toInt(), 'approve'),
                  onReject: () =>
                      _action((row['id'] as num).toInt(), 'reject'),
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _ApprovalCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final String? amount;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  const _ApprovalCard({
    required this.title,
    required this.subtitle,
    required this.onApprove,
    required this.onReject,
    this.amount,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: theme.textTheme.bodyLarge?.copyWith(
                            fontWeight: FontWeight.w600)),
                    if (subtitle.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(
                          subtitle,
                          style: theme.textTheme.bodySmall
                              ?.copyWith(color: sem.textSub),
                        ),
                      ),
                  ],
                ),
              ),
              if (amount != null)
                Text(
                  amount!,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: sem.textMuted,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onReject,
                  icon: Icon(Icons.close, color: sem.danger),
                  label: Text(
                    AppLocalizations.of(context)?.reject ?? 'Reject',
                    style: TextStyle(color: sem.danger),
                  ),
                  style: OutlinedButton.styleFrom(
                    side: BorderSide(color: sem.danger.withValues(alpha: 0.5)),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  onPressed: onApprove,
                  icon: const Icon(Icons.check),
                  label: Text(
                      AppLocalizations.of(context)?.approve ?? 'Approve'),
                  style: FilledButton.styleFrom(
                    backgroundColor: sem.success,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
