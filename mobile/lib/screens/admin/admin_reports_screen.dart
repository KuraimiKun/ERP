import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/api_config.dart';
import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../services/admin_api_service.dart';
import '../../services/api_service.dart';
import 'admin_shell.dart';

/// Reports hub — one tab per report endpoint.
///
/// Reports are JSON only; we render them as key/value trees.
class AdminReportsScreen extends StatefulWidget {
  const AdminReportsScreen({super.key});

  @override
  State<AdminReportsScreen> createState() => _AdminReportsScreenState();
}

class _AdminReportsScreenState extends State<AdminReportsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tab;

  static const _reports = <_ReportDef>[
    _ReportDef('trialBalance', ApiConfig.adminReportTrialBalance),
    _ReportDef('profitAndLoss', ApiConfig.adminReportProfitAndLoss),
    _ReportDef('balanceSheet', ApiConfig.adminReportBalanceSheet),
    _ReportDef('cashFlow', ApiConfig.adminReportCashFlow),
    _ReportDef('salesSummary', ApiConfig.adminReportSalesSummary),
    _ReportDef('topProducts', ApiConfig.adminReportTopProducts),
    _ReportDef('topCustomers', ApiConfig.adminReportTopCustomers),
    _ReportDef('arAging', ApiConfig.adminReportAgingReceivables),
    _ReportDef('apAging', ApiConfig.adminReportAgingPayables),
  ];

  String _titleFor(_ReportDef r, AppLocalizations l10n) {
    switch (r.titleKey) {
      case 'trialBalance':
        return l10n.reportTrialBalance;
      case 'profitAndLoss':
        return l10n.reportProfitLoss;
      case 'balanceSheet':
        return l10n.reportBalanceSheet;
      case 'cashFlow':
        return l10n.reportCashFlow;
      case 'salesSummary':
        return l10n.reportSalesSummary;
      case 'topProducts':
        return l10n.reportTopProducts;
      case 'topCustomers':
        return l10n.reportTopCustomers;
      case 'arAging':
        return l10n.reportArAging;
      case 'apAging':
        return l10n.reportApAging;
    }
    return r.titleKey;
  }

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: _reports.length, vsync: this);
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
      title: l10n.reports,
      currentIndex: -1,
      body: Column(
        children: [
          Material(
            color: Theme.of(context).colorScheme.surface,
            child: TabBar(
              controller: _tab,
              isScrollable: true,
              tabs: [for (final r in _reports) Tab(text: _titleFor(r, l10n))],
            ),
          ),
          Expanded(
            child: TabBarView(
              controller: _tab,
              children: [for (final r in _reports) _ReportPane(def: r)],
            ),
          ),
        ],
      ),
    );
  }
}

class _ReportDef {
  final String titleKey;
  final String endpoint;
  const _ReportDef(this.titleKey, this.endpoint);
}

class _ReportPane extends StatefulWidget {
  final _ReportDef def;
  const _ReportPane({required this.def});

  @override
  State<_ReportPane> createState() => _ReportPaneState();
}

class _ReportPaneState extends State<_ReportPane>
    with AutomaticKeepAliveClientMixin {
  dynamic _data;
  bool _loading = false;
  String? _error;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = AdminApiService(context.read<ApiService>());
      final data = await api.getRaw(widget.def.endpoint);
      if (!mounted) return;
      setState(() => _data = data);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = AdminApiService.extractError(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final sem = AppTheme.semantics(context);
    if (_loading && _data == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _data == null) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 48, color: sem.danger),
            const SizedBox(height: 12),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _load,
              icon: const Icon(Icons.refresh),
              label: Text(AppLocalizations.of(context)?.retry ?? 'Retry'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [_renderNode(context, _data, 0)],
      ),
    );
  }

  Widget _renderNode(BuildContext context, dynamic node, int depth) {
    if (node == null) return const Text('—');
    if (node is Map) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final entry in node.entries)
            _KvRow(
              label: entry.key.toString(),
              depth: depth,
              child: _renderNode(context, entry.value, depth + 1),
            ),
        ],
      );
    }
    if (node is List) {
      if (node.isEmpty) return const Text('—');
      // List of scalars → comma join.
      if (node.first is! Map && node.first is! List) {
        return Text(node.map((e) => e.toString()).join(', '));
      }
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < node.length; i++)
            Card(
              margin: const EdgeInsets.symmetric(vertical: 4),
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: _renderNode(context, node[i], depth + 1),
              ),
            ),
        ],
      );
    }
    return SelectableText(node.toString());
  }
}

class _KvRow extends StatelessWidget {
  final String label;
  final Widget child;
  final int depth;

  const _KvRow({required this.label, required this.child, required this.depth});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    return Padding(
      padding: EdgeInsets.only(left: depth * 4.0, top: 4, bottom: 4, right: 0),
      child: LayoutBuilder(
        builder: (context, constraints) {
          // Cap label column at ~40% of the available width (and no more
          // than 160) so deeply-nested rows never blow past their parent.
          final labelWidth = constraints.maxWidth * 0.4 > 160
              ? 160.0
              : constraints.maxWidth * 0.4;
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: labelWidth,
                child: Text(
                  _humanize(label),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: sem.textFaint,
                    fontWeight: FontWeight.w600,
                  ),
                  softWrap: true,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(child: child),
            ],
          );
        },
      ),
    );
  }

  static String _humanize(String k) => k
      .replaceAll('_', ' ')
      .split(' ')
      .where((p) => p.isNotEmpty)
      .map((p) => p[0].toUpperCase() + p.substring(1))
      .join(' ');
}
