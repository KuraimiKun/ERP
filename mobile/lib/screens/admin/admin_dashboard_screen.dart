import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../models/admin/admin_dashboard.dart';
import '../../providers/admin_dashboard_provider.dart';
import '../../providers/auth_provider.dart';
import 'admin_shell.dart';

class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AdminDashboardProvider>().loadAll();
    });
  }

  Future<void> _refresh() =>
      context.read<AdminDashboardProvider>().loadAll();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AdminShell(
      title: l10n.dashboard,
      currentIndex: 0,
      actions: [
        IconButton(
          icon: const Icon(Icons.refresh),
          tooltip: l10n.refresh,
          onPressed: _refresh,
        ),
      ],
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _DashboardContent(),
      ),
    );
  }
}

class _DashboardContent extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AdminDashboardProvider>();
    final auth = context.watch<AuthProvider>();

    if (provider.isLoading && provider.summary == null) {
      return const Center(child: CircularProgressIndicator());
    }

    if (provider.error != null && provider.summary == null) {
      return ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const SizedBox(height: 80),
          Icon(Icons.error_outline,
              size: 56, color: AppTheme.semantics(context).danger),
          const SizedBox(height: 12),
          Center(
            child: Text(
              provider.error ??
                  AppLocalizations.of(context)!.unableToLoadDashboard,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
          const SizedBox(height: 16),
          Center(
            child: FilledButton.icon(
              onPressed: () =>
                  context.read<AdminDashboardProvider>().loadAll(),
              icon: const Icon(Icons.refresh),
              label: Text(AppLocalizations.of(context)!.retry),
            ),
          ),
        ],
      );
    }

    final summary = provider.summary;
    final kpis = provider.kpis;
    final activity = provider.activity;
    final admin = auth.admin;

    return LayoutBuilder(
      builder: (context, constraints) {
        final isWide = constraints.maxWidth >= 720;
        final summaryCols = isWide ? 4 : 2;
        final kpiCols = isWide ? 4 : 2;

        return ListView(
          padding: EdgeInsets.symmetric(
            horizontal: isWide ? 32 : 16,
            vertical: 20,
          ),
          children: [
            // ── Greeting ────────────────────────────────────────
            _Greeting(
              name: admin?.firstName.isNotEmpty == true
                  ? admin!.firstName
                  : (admin?.email ?? 'Admin'),
              company: admin?.company?.name ?? '',
            ),
            const SizedBox(height: 24),

            // ── Today section ──────────────────────────────────
            _SectionTitle('Today'),
            const SizedBox(height: 12),
            _KpiGrid(
              columns: summaryCols,
              tiles: summary == null ? [] : _todayTiles(context, summary),
            ),
            const SizedBox(height: 28),

            // ── Pending approvals ──────────────────────────────
            _SectionTitle('Pending approvals'),
            const SizedBox(height: 12),
            _KpiGrid(
              columns: summaryCols,
              tiles: summary == null ? [] : _approvalTiles(context, summary),
            ),
            const SizedBox(height: 28),

            // ── Alerts ─────────────────────────────────────────
            _SectionTitle('Alerts & operations'),
            const SizedBox(height: 12),
            _KpiGrid(
              columns: summaryCols,
              tiles: summary == null ? [] : _alertTiles(context, summary),
            ),
            const SizedBox(height: 28),

            // ── 30-day KPIs ────────────────────────────────────
            _SectionTitle(
                '${kpis?.periodDays ?? 30}-day performance'),
            const SizedBox(height: 12),
            _KpiGrid(
              columns: kpiCols,
              tiles: kpis == null ? [] : _kpiTiles(context, kpis),
            ),
            const SizedBox(height: 32),

            // ── Recent activity ────────────────────────────────
            _SectionTitle('Recent activity'),
            const SizedBox(height: 12),
            _ActivityTable(entries: activity),
            const SizedBox(height: 40),
          ],
        );
      },
    );
  }

  // ── Tile factories ─────────────────────────────────────────────────

  List<_Tile> _todayTiles(BuildContext c, AdminDashboardSummary s) {
    final sem = AppTheme.semantics(c);
    final l10n = AppLocalizations.of(c)!;
    return [
      _Tile(
        label: l10n.kpiTodayRevenue,
        value: _money(s.todayRevenue),
        icon: Icons.payments_outlined,
        color: sem.success,
      ),
      _Tile(
        label: l10n.kpiCashInHand,
        value: _money(s.cashInHand),
        icon: Icons.account_balance_wallet_outlined,
        color: sem.info,
      ),
      _Tile(
        label: l10n.kpiThisMonthRevenue,
        value: _money(s.thisMonthRevenue),
        icon: Icons.trending_up_outlined,
        color: sem.accent,
      ),
      _Tile(
        label: l10n.kpiThisMonthExpenses,
        value: _money(s.thisMonthExpenses),
        icon: Icons.receipt_long_outlined,
        color: sem.warning,
      ),
    ];
  }

  List<_Tile> _approvalTiles(BuildContext c, AdminDashboardSummary s) {
    final sem = AppTheme.semantics(c);
    final l10n = AppLocalizations.of(c)!;
    return [
      _Tile(
        label: l10n.approvalsLeaves,
        value: '${s.pendingLeaveApprovals}',
        icon: Icons.event_note_outlined,
        color: sem.info,
      ),
      _Tile(
        label: l10n.approvalsExpenses,
        value: '${s.pendingExpenseApprovals}',
        icon: Icons.receipt_outlined,
        color: sem.warning,
      ),
      _Tile(
        label: l10n.kpiPurchaseOrders,
        value: '${s.pendingPoApprovals}',
        icon: Icons.shopping_cart_outlined,
        color: sem.purple,
      ),
      _Tile(
        label: l10n.kpiOverdueInvoices,
        value: _money(s.overdueInvoicesAmount),
        icon: Icons.warning_amber_outlined,
        color: sem.danger,
      ),
    ];
  }

  List<_Tile> _alertTiles(BuildContext c, AdminDashboardSummary s) {
    final sem = AppTheme.semantics(c);
    final l10n = AppLocalizations.of(c)!;
    return [
      _Tile(
        label: l10n.kpiLowStockItems,
        value: '${s.lowStockItems}',
        icon: Icons.inventory_2_outlined,
        color: sem.warning,
      ),
      _Tile(
        label: l10n.kpiOpenPosSessions,
        value: '${s.openPosSessions}',
        icon: Icons.point_of_sale_outlined,
        color: sem.info,
      ),
    ];
  }

  List<_Tile> _kpiTiles(BuildContext c, AdminDashboardKpis k) {
    final sem = AppTheme.semantics(c);
    final l10n = AppLocalizations.of(c)!;
    return [
      _Tile(
        label: l10n.kpiRevenue,
        value: _money(k.revenue),
        icon: Icons.show_chart,
        color: sem.success,
      ),
      _Tile(
        label: l10n.kpiExpenses,
        value: _money(k.expenses),
        icon: Icons.trending_down,
        color: sem.danger,
      ),
      _Tile(
        label: l10n.kpiNet,
        value: _money(k.net),
        icon: Icons.balance_outlined,
        color: sem.accent,
      ),
      _Tile(
        label: l10n.kpiPaymentsReceived,
        value: _money(k.paymentsReceived),
        icon: Icons.account_balance_outlined,
        color: sem.info,
      ),
      _Tile(
        label: l10n.kpiInvoicesIssued,
        value: '${k.invoicesIssued}',
        icon: Icons.description_outlined,
        color: sem.purple,
      ),
      _Tile(
        label: l10n.kpiNewCustomers,
        value: '${k.newCustomers}',
        icon: Icons.people_alt_outlined,
        color: sem.info,
      ),
      _Tile(
        label: l10n.kpiNewLeads,
        value: '${k.newLeads}',
        icon: Icons.person_add_alt_outlined,
        color: sem.accent,
      ),
    ];
  }

  /// Simple thousands-grouped money formatter.  Value comes in as a decimal
  /// string — we keep trailing zero-free, grouped by commas.
  String _money(String raw) {
    if (raw.isEmpty) return '0';
    final parsed = double.tryParse(raw);
    if (parsed == null) return raw;
    final sign = parsed < 0 ? '-' : '';
    final abs = parsed.abs();
    final intPart = abs.truncate();
    final frac = abs - intPart;
    final intStr = intPart
        .toString()
        .replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
    final fracStr = frac > 0 ? frac.toStringAsFixed(2).substring(1) : '';
    return '$sign$intStr$fracStr';
  }
}

// ──────────────────────────────────────────────────────────────────────
// Building blocks
// ──────────────────────────────────────────────────────────────────────

class _Greeting extends StatelessWidget {
  final String name;
  final String company;

  const _Greeting({required this.name, required this.company});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final greeting = _timeBasedGreeting(context);

    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: theme.colorScheme.primary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Icon(
            Icons.waving_hand_outlined,
            color: theme.colorScheme.primary,
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$greeting, $name',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              if (company.isNotEmpty)
                Text(
                  company,
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: sem.textSub),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
            ],
          ),
        ),
      ],
    );
  }

  String _timeBasedGreeting(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final h = DateTime.now().hour;
    if (h < 12) return l10n.goodMorning;
    if (h < 18) return l10n.goodAfternoon;
    return l10n.goodEvening;
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context).textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.w700,
            letterSpacing: 0.2,
          ),
    );
  }
}

class _Tile {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _Tile({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });
}

class _KpiGrid extends StatelessWidget {
  final int columns;
  final List<_Tile> tiles;

  const _KpiGrid({required this.columns, required this.tiles});

  @override
  Widget build(BuildContext context) {
    if (tiles.isEmpty) {
      return const SizedBox.shrink();
    }
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: tiles.length,
      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: columns,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 1.55,
      ),
      itemBuilder: (_, i) {
        final t = tiles[i];
        return _KpiTile(tile: t);
      },
    );
  }
}

class _KpiTile extends StatelessWidget {
  final _Tile tile;

  const _KpiTile({required this.tile});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: tile.color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(tile.icon, color: tile.color, size: 20),
            ),
            const Spacer(),
            Text(
              tile.value,
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w800,
                color: tile.color,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 2),
            Text(
              tile.label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: sem.textMuted,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

class _ActivityTable extends StatelessWidget {
  final List<AdminActivityEntry> entries;

  const _ActivityTable({required this.entries});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);

    if (entries.isEmpty) {
      return Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: Text(
              'No recent activity',
              style:
                  theme.textTheme.bodyMedium?.copyWith(color: sem.textMuted),
            ),
          ),
        ),
      );
    }

    final visible = entries.take(15).toList();

    return Card(
      margin: EdgeInsets.zero,
      child: Column(
        children: [
          for (var i = 0; i < visible.length; i++) ...[
            _ActivityRow(entry: visible[i]),
            if (i != visible.length - 1)
              Divider(height: 1, color: sem.borderSoft),
          ],
        ],
      ),
    );
  }
}

class _ActivityRow extends StatelessWidget {
  final AdminActivityEntry entry;

  const _ActivityRow({required this.entry});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: theme.colorScheme.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              Icons.history,
              size: 18,
              color: theme.colorScheme.primary,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.description.isNotEmpty
                      ? entry.description
                      : entry.action,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  [
                    entry.actorName,
                    if (entry.contentType != null &&
                        entry.contentType!.isNotEmpty)
                      entry.contentType,
                    _formatDate(entry.createdAt),
                  ].where((s) => s != null && s.isNotEmpty).join(' • '),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: sem.textFaint,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(String raw) {
    if (raw.isEmpty) return '';
    final dt = DateTime.tryParse(raw);
    if (dt == null) return raw;
    final local = dt.toLocal();
    final now = DateTime.now();
    final diff = now.difference(local);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inDays < 1) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')}';
  }
}
