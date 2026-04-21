import 'dart:math';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../models/pos/stats.dart';
import '../../providers/pos_provider.dart';

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
    final pos = context.watch<POSProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final stats = pos.stats;

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
                    onTap: () => Navigator.maybePop(context),
                    child: Icon(Icons.arrow_back_ios_new_rounded, size: 20,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const Spacer(),
                  Text('My Performance', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),
            Expanded(
              child: pos.statsLoading
                  ? const Center(child: CircularProgressIndicator())
                  : stats == null
                      ? Center(child: Text('No data',
                          style: TextStyle(color: AppTheme.semantics(context).textSub)))
                      : RefreshIndicator(
                          onRefresh: () => pos.loadStats(period: _period),
                          color: isDark ? MColors.darkPrimary : MColors.primary,
                          child: ListView(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                            children: [
                              // Period tabs
                              Row(children: [
                                _periodChip('Today', 'today', _period, isDark,
                                    () => _changePeriod('today')),
                                const SizedBox(width: 8),
                                _periodChip('Week', 'week', _period, isDark,
                                    () => _changePeriod('week')),
                                const SizedBox(width: 8),
                                _periodChip('Month', 'month', _period, isDark,
                                    () => _changePeriod('month')),
                              ]),
                              const SizedBox(height: 16),

                              // Summary KPIs
                              _SummaryGrid(summary: stats.summary, isDark: isDark),
                              const SizedBox(height: 16),

                              // Hourly chart
                              if (stats.hourlySales.isNotEmpty) ...[
                                _SectionTitle('Hourly Sales', isDark: isDark),
                                const SizedBox(height: 8),
                                _HourlyChart(data: stats.hourlySales, isDark: isDark),
                                const SizedBox(height: 16),
                              ],

                              // Payment breakdown
                              if (stats.paymentBreakdown.isNotEmpty) ...[
                                _SectionTitle('Payment Breakdown', isDark: isDark),
                                const SizedBox(height: 8),
                                _PaymentBreakdown(data: stats.paymentBreakdown, isDark: isDark),
                                const SizedBox(height: 16),
                              ],

                              // Top products
                              if (stats.topProducts.isNotEmpty) ...[
                                _SectionTitle('Top Products', isDark: isDark),
                                const SizedBox(height: 8),
                                _TopProducts(products: stats.topProducts, isDark: isDark),
                                const SizedBox(height: 16),
                              ],

                              // Recent sessions
                              if (stats.recentSessions.isNotEmpty) ...[
                                _SectionTitle('Recent Sessions', isDark: isDark),
                                const SizedBox(height: 8),
                                ...stats.recentSessions.map((s) =>
                                    _SessionCard(session: s, isDark: isDark)),
                              ],
                            ],
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

Widget _periodChip(String label, String value, String current, bool isDark, VoidCallback onTap) {
  final sel = current == value;
  return GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: sel ? (isDark ? MColors.darkPrimary : MColors.primary) : Colors.transparent,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: sel ? (isDark ? MColors.darkPrimary : MColors.primary)
              : (isDark ? MColors.darkBorder : MColors.border),
          width: 0.5,
        ),
      ),
      child: Text(label, style: TextStyle(
          fontSize: 12.5, fontWeight: FontWeight.w600,
          color: sel ? Colors.white : (isDark ? MColors.darkTextMid : MColors.textMid))),
    ),
  );
}

class _SummaryGrid extends StatelessWidget {
  final SalesSummary summary;
  final bool isDark;
  const _SummaryGrid({required this.summary, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final items = [
      ('Total Sales', summary.totalSales, Icons.attach_money_rounded, const Color(0xFF10B981)),
      ('Orders', summary.totalOrders.toString(), Icons.receipt_long_outlined, const Color(0xFF3B82F6)),
      ('Avg Order', summary.averageOrder, Icons.trending_up_rounded, const Color(0xFFF59E0B)),
      ('Items Sold', summary.totalItemsSold, Icons.inventory_2_outlined, const Color(0xFF8B5CF6)),
    ];
    return GridView.count(
      crossAxisCount: 2, crossAxisSpacing: 10, mainAxisSpacing: 10,
      childAspectRatio: 1.6, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
      children: items.map((e) => _KpiCard(
          label: e.$1, value: e.$2, icon: e.$3, color: e.$4, isDark: isDark)).toList(),
    );
  }
}

class _KpiCard extends StatelessWidget {
  final String label, value;
  final IconData icon;
  final Color color;
  final bool isDark;
  const _KpiCard({required this.label, required this.value, required this.icon,
      required this.color, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(fontSize: 11,
                color: isDark ? MColors.darkTextSub : MColors.textSub)),
          ]),
          const Spacer(),
          Text(value, style: TextStyle(
              fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: -0.4,
              color: isDark ? MColors.darkText : MColors.text)),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final bool isDark;
  const _SectionTitle(this.title, {required this.isDark});

  @override
  Widget build(BuildContext context) => Text(title, style: TextStyle(
      fontSize: 13, fontWeight: FontWeight.w700,
      color: isDark ? MColors.darkText : MColors.text));
}

class _HourlyChart extends StatelessWidget {
  final List<HourlySales> data;
  final bool isDark;
  const _HourlyChart({required this.data, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final maxVal = data.map((h) => double.tryParse(h.total) ?? 0).reduce(max);
    final chartMax = maxVal > 0 ? maxVal : 1.0;
    final primary = isDark ? MColors.darkPrimary : MColors.primary;

    return Container(
      height: 150,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: data.map((h) {
          final val = double.tryParse(h.total) ?? 0;
          final frac = val / chartMax;
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 1.5),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  if (h.count > 0)
                    Text('${h.count}', style: TextStyle(fontSize: 8,
                        color: isDark ? MColors.darkTextFaint : MColors.textFaint)),
                  const SizedBox(height: 2),
                  Flexible(child: FractionallySizedBox(
                    heightFactor: frac.clamp(0.05, 1.0),
                    child: Container(
                      decoration: BoxDecoration(
                        color: primary,
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(3)),
                      ),
                    ),
                  )),
                  const SizedBox(height: 3),
                  Text('${h.hour}', style: TextStyle(fontSize: 8,
                      color: isDark ? MColors.darkTextFaint : MColors.textFaint)),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _PaymentBreakdown extends StatelessWidget {
  final List<PaymentBreakdown> data;
  final bool isDark;
  const _PaymentBreakdown({required this.data, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final total = data.fold<double>(0, (s, p) => s + (double.tryParse(p.total) ?? 0));
    final primary = isDark ? MColors.darkPrimary : MColors.primary;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      child: Column(
        children: data.map((p) {
          final amt = double.tryParse(p.total) ?? 0;
          final frac = total > 0 ? amt / total : 0.0;
          return Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(p.method, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500,
                        color: isDark ? MColors.darkText : MColors.text)),
                    Text('${p.total} (${p.count})', style: TextStyle(
                        fontSize: 12, fontWeight: FontWeight.w600,
                        color: isDark ? MColors.darkText : MColors.text)),
                  ],
                ),
                const SizedBox(height: 6),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: frac.clamp(0.0, 1.0),
                    minHeight: 6,
                    backgroundColor: isDark ? MColors.darkBorder : MColors.border,
                    valueColor: AlwaysStoppedAnimation(primary),
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _TopProducts extends StatelessWidget {
  final List<TopProduct> products;
  final bool isDark;
  const _TopProducts({required this.products, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: products.asMap().entries.map((e) {
          final i = e.key; final p = e.value;
          return Container(
            decoration: BoxDecoration(
              border: i > 0 ? Border(top: BorderSide(
                  color: isDark ? MColors.darkBorder : MColors.borderSoft, width: 0.5)) : null,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              children: [
                Container(
                  width: 28, height: 28,
                  decoration: BoxDecoration(
                    color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Center(child: Text('${i + 1}', style: TextStyle(
                      fontSize: 12, fontWeight: FontWeight.w700,
                      color: isDark ? MColors.darkPrimary : MColors.primary))),
                ),
                const SizedBox(width: 10),
                Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(p.name, maxLines: 1, overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
                            color: isDark ? MColors.darkText : MColors.text)),
                    Text(p.sku, style: TextStyle(fontSize: 11,
                        color: isDark ? MColors.darkTextSub : MColors.textSub)),
                  ],
                )),
                Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Text(p.total, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700,
                      color: isDark ? MColors.darkText : MColors.text)),
                  Text('${p.quantity} pcs', style: TextStyle(fontSize: 11,
                      color: isDark ? MColors.darkTextSub : MColors.textSub)),
                ]),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _SessionCard extends StatelessWidget {
  final RecentSession session;
  final bool isDark;
  const _SessionCard({required this.session, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final diff = double.tryParse(session.cashDifference) ?? 0;
    final isClosed = session.status == 'closed';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: Text(session.sessionNumber, style: TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w700,
                  color: isDark ? MColors.darkText : MColors.text))),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(
                  color: isClosed
                      ? (isDark ? MColors.darkBorder : MColors.border)
                      : sem.successContainer,
                  borderRadius: BorderRadius.circular(7),
                ),
                child: Text(session.status, style: TextStyle(
                    fontSize: 11, fontWeight: FontWeight.w600,
                    color: isClosed
                        ? (isDark ? MColors.darkTextSub : MColors.textSub)
                        : sem.success)),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Align(alignment: Alignment.centerLeft,
              child: Text(session.terminalName, style: TextStyle(
                  fontSize: 12, color: isDark ? MColors.darkTextSub : MColors.textSub))),
          Divider(height: 14, color: isDark ? MColors.darkBorder : MColors.border),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _SessionStat('Sales', session.totalSales, isDark: isDark),
              _SessionStat('Orders', '${session.totalOrders}', isDark: isDark),
              _SessionStat('Cash diff',
                  diff >= 0 ? '+${session.cashDifference}' : session.cashDifference,
                  isDark: isDark,
                  color: diff < 0 ? sem.danger : sem.success),
            ],
          ),
        ],
      ),
    );
  }
}

class _SessionStat extends StatelessWidget {
  final String label, value;
  final bool isDark;
  final Color? color;
  const _SessionStat(this.label, this.value, {required this.isDark, this.color});

  @override
  Widget build(BuildContext context) => Column(children: [
    Text(label, style: TextStyle(fontSize: 11,
        color: isDark ? MColors.darkTextSub : MColors.textSub)),
    const SizedBox(height: 2),
    Text(value, style: TextStyle(
        fontSize: 13, fontWeight: FontWeight.w700,
        color: color ?? (isDark ? MColors.darkText : MColors.text))),
  ]);
}
