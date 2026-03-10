import 'dart:math';

import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../providers/pos_provider.dart';
import '../../models/pos/stats.dart';
import '../../widgets/loading_indicator.dart';

class POSStatsScreen extends StatefulWidget {
  const POSStatsScreen({super.key});

  @override
  State<POSStatsScreen> createState() => _POSStatsScreenState();
}

class _POSStatsScreenState extends State<POSStatsScreen> {
  String _period = 'today';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<POSProvider>().loadStats(period: _period);
    });
  }

  void _changePeriod(String period) {
    setState(() => _period = period);
    context.read<POSProvider>().loadStats(period: period);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final pos = context.watch<POSProvider>();
    final stats = pos.stats;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.myPerformance),
      ),
      body: pos.statsLoading
          ? LoadingIndicator(message: l10n.loading)
          : stats == null
              ? Center(child: Text(l10n.noData))
              : RefreshIndicator(
                  onRefresh: () => pos.loadStats(period: _period),
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      // Period toggle
                      _buildPeriodChips(l10n),
                      const SizedBox(height: 16),

                      // Summary cards
                      _buildSummaryCards(l10n, stats.summary),
                      const SizedBox(height: 20),

                      // Hourly sales chart
                      if (stats.hourlySales.isNotEmpty) ...[
                        _buildSectionTitle(l10n.hourlySalesTitle),
                        const SizedBox(height: 8),
                        _buildHourlyChart(stats.hourlySales),
                        const SizedBox(height: 20),
                      ],

                      // Payment breakdown
                      if (stats.paymentBreakdown.isNotEmpty) ...[
                        _buildSectionTitle(l10n.paymentBreakdown),
                        const SizedBox(height: 8),
                        _buildPaymentBreakdown(stats.paymentBreakdown),
                        const SizedBox(height: 20),
                      ],

                      // Top products
                      if (stats.topProducts.isNotEmpty) ...[
                        _buildSectionTitle(l10n.topProducts),
                        const SizedBox(height: 8),
                        _buildTopProducts(stats.topProducts),
                        const SizedBox(height: 20),
                      ],

                      // Recent sessions
                      if (stats.recentSessions.isNotEmpty) ...[
                        _buildSectionTitle(l10n.recentSessions),
                        const SizedBox(height: 8),
                        _buildRecentSessions(l10n, stats.recentSessions),
                      ],
                    ],
                  ),
                ),
    );
  }

  Widget _buildPeriodChips(AppLocalizations l10n) {
    return Row(
      children: [
        _periodChip(l10n.periodToday, 'today'),
        const SizedBox(width: 8),
        _periodChip(l10n.periodWeek, 'week'),
        const SizedBox(width: 8),
        _periodChip(l10n.periodMonth, 'month'),
      ],
    );
  }

  Widget _periodChip(String label, String value) {
    final selected = _period == value;
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => _changePeriod(value),
    );
  }

  Widget _buildSummaryCards(AppLocalizations l10n, SalesSummary summary) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _statCard(
                l10n.totalSalesLabel,
                summary.totalSales,
                Icons.attach_money,
                Colors.green,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _statCard(
                l10n.totalOrdersLabel,
                summary.totalOrders.toString(),
                Icons.receipt_long,
                Colors.blue,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _statCard(
                l10n.avgOrderLabel,
                summary.averageOrder,
                Icons.trending_up,
                Colors.orange,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _statCard(
                l10n.itemsSoldLabel,
                summary.totalItemsSold,
                Icons.inventory_2,
                Colors.purple,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _statCard(String label, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    label,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey[600],
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.bold,
      ),
    );
  }

  Widget _buildHourlyChart(List<HourlySales> hourlySales) {
    final maxTotal = hourlySales
        .map((h) => double.tryParse(h.total) ?? 0)
        .reduce(max);
    final chartMax = maxTotal > 0 ? maxTotal : 1.0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: SizedBox(
          height: 160,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: hourlySales.map((h) {
              final value = double.tryParse(h.total) ?? 0;
              final fraction = value / chartMax;
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Text(
                        h.count.toString(),
                        style: const TextStyle(fontSize: 10),
                      ),
                      const SizedBox(height: 4),
                      Flexible(
                        child: FractionallySizedBox(
                          heightFactor: fraction.clamp(0.05, 1.0),
                          child: Container(
                            decoration: BoxDecoration(
                              color: Theme.of(context).primaryColor,
                              borderRadius:
                                  const BorderRadius.vertical(top: Radius.circular(4)),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${h.hour}',
                        style: TextStyle(
                          fontSize: 10,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ),
      ),
    );
  }

  Widget _buildPaymentBreakdown(List<PaymentBreakdown> payments) {
    final totalAll = payments.fold<double>(
        0, (sum, p) => sum + (double.tryParse(p.total) ?? 0));

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: payments.map((p) {
            final amount = double.tryParse(p.total) ?? 0;
            final fraction = totalAll > 0 ? amount / totalAll : 0.0;
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        p.method,
                        style: const TextStyle(fontWeight: FontWeight.w500),
                      ),
                      Text(
                        '${p.total} (${p.count})',
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: fraction,
                      minHeight: 8,
                      backgroundColor: Colors.grey[200],
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildTopProducts(List<TopProduct> products) {
    return Card(
      child: Column(
        children: products.asMap().entries.map((entry) {
          final i = entry.key;
          final p = entry.value;
          return ListTile(
            leading: CircleAvatar(
              backgroundColor: Theme.of(context).primaryColor.withAlpha(30),
              child: Text(
                '${i + 1}',
                style: TextStyle(
                  color: Theme.of(context).primaryColor,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            title: Text(p.name, maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: Text(p.sku),
            trailing: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  p.total,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                Text(
                  '${p.quantity} pcs',
                  style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildRecentSessions(
      AppLocalizations l10n, List<RecentSession> sessions) {
    return Column(
      children: sessions.map((s) {
        final diff = double.tryParse(s.cashDifference) ?? 0;
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      s.sessionNumber,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    Chip(
                      label: Text(
                        s.status,
                        style: const TextStyle(fontSize: 11),
                      ),
                      visualDensity: VisualDensity.compact,
                      backgroundColor: s.status == 'closed'
                          ? Colors.grey[200]
                          : Colors.green[100],
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  s.terminalName,
                  style: TextStyle(color: Colors.grey[600], fontSize: 13),
                ),
                const Divider(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _sessionStat(l10n.totalSalesLabel, s.totalSales),
                    _sessionStat(l10n.totalOrdersLabel, s.totalOrders.toString()),
                    _sessionStat(
                      l10n.cashDifference,
                      diff >= 0 ? '+${s.cashDifference}' : s.cashDifference,
                      color: diff < 0 ? Colors.red : Colors.green,
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _sessionStat(String label, String value, {Color? color}) {
    return Column(
      children: [
        Text(
          label,
          style: TextStyle(fontSize: 11, color: Colors.grey[600]),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            fontSize: 13,
            color: color,
          ),
        ),
      ],
    );
  }
}
