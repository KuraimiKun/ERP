import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../models/leave_request.dart';
import '../../providers/leave_provider.dart';
import '../../widgets/status_badge.dart';

class LeaveListScreen extends StatefulWidget {
  const LeaveListScreen({super.key});

  @override
  State<LeaveListScreen> createState() => _LeaveListScreenState();
}

class _LeaveListScreenState extends State<LeaveListScreen> {
  int _tabIndex = 0;
  static const _tabs = ['All', 'Pending', 'Approved', 'Rejected'];
  static const _statusFilters = ['', 'pending', 'approved', 'rejected'];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LeaveProvider>().loadLeaves();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<LeaveProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? MColors.darkBg : MColors.bg;

    final filtered = _statusFilters[_tabIndex].isEmpty
        ? provider.leaves
        : provider.leaves.where((l) => l.status == _statusFilters[_tabIndex]).toList();

    return Scaffold(
      backgroundColor: bg,
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
                  Text('Leaves', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),

            if (provider.balances.isNotEmpty)
              SizedBox(
                height: 120,
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  scrollDirection: Axis.horizontal,
                  itemCount: provider.balances.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 10),
                  itemBuilder: (ctx, i) => _BalanceCard(balance: provider.balances[i]),
                ),
              ),

            const SizedBox(height: 12),

            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: List.generate(_tabs.length, (i) => Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: GestureDetector(
                      onTap: () => setState(() => _tabIndex = i),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          color: _tabIndex == i
                              ? (isDark ? MColors.darkPrimary : MColors.primary)
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(999),
                          border: Border.all(
                            color: _tabIndex == i
                                ? (isDark ? MColors.darkPrimary : MColors.primary)
                                : (isDark ? MColors.darkBorder : MColors.border),
                            width: 0.5,
                          ),
                        ),
                        child: Text(
                          _tabs[i],
                          style: TextStyle(
                            fontSize: 12.5, fontWeight: FontWeight.w600,
                            color: _tabIndex == i ? Colors.white
                                : (isDark ? MColors.darkTextMid : MColors.textMid),
                          ),
                        ),
                      ),
                    ),
                  )),
                ),
              ),
            ),

            Expanded(
              child: provider.isLoading
                  ? const _Shimmer()
                  : filtered.isEmpty
                      ? const _Empty()
                      : RefreshIndicator(
                          onRefresh: () => provider.loadLeaves(),
                          color: isDark ? MColors.darkPrimary : MColors.primary,
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 100),
                            itemCount: filtered.length,
                            itemBuilder: (ctx, i) => _LeaveTile(request: filtered[i]),
                          ),
                        ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final provider = context.read<LeaveProvider>();
          await Navigator.pushNamed(context, AppRoutes.leaveForm);
          if (mounted) provider.loadLeaves();
        },
        icon: const Icon(Icons.add_rounded),
        label: const Text('New request', style: TextStyle(fontWeight: FontWeight.w600)),
      ),
    );
  }
}

class _BalanceCard extends StatelessWidget {
  final LeaveBalance balance;
  const _BalanceCard({required this.balance});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primary = isDark ? MColors.darkPrimary : MColors.primary;
    final pct = balance.daysAllowed > 0 ? balance.used / balance.daysAllowed : 0.0;

    return Container(
      width: 165,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(balance.name,
                    style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600,
                        color: isDark ? MColors.darkText : MColors.text),
                    maxLines: 1, overflow: TextOverflow.ellipsis),
              ),
              Container(width: 8, height: 8,
                  decoration: BoxDecoration(color: primary, shape: BoxShape.circle)),
            ],
          ),
          const Spacer(),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(balance.remaining.toStringAsFixed(0),
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700,
                      color: isDark ? MColors.darkText : MColors.text, letterSpacing: -0.4)),
              const SizedBox(width: 4),
              Text('/ ${balance.daysAllowed} days',
                  style: TextStyle(fontSize: 11, color: isDark ? MColors.darkTextSub : MColors.textSub)),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: pct.clamp(0.0, 1.0),
              minHeight: 5,
              backgroundColor: isDark ? MColors.darkBorder : MColors.border,
              valueColor: AlwaysStoppedAnimation(primary),
            ),
          ),
          const SizedBox(height: 4),
          Text('${balance.used.toStringAsFixed(0)} taken · ${balance.remaining.toStringAsFixed(0)} left',
              style: TextStyle(fontSize: 10.5,
                  color: isDark ? MColors.darkTextSub : MColors.textSub,
                  fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

class _LeaveTile extends StatelessWidget {
  final LeaveRequest request;
  const _LeaveTile({required this.request});

  Color _statusColor(BuildContext context) {
    final sem = AppTheme.semantics(context);
    switch (request.status) {
      case 'approved': return sem.success;
      case 'rejected': return sem.danger;
      case 'cancelled': return sem.textSub;
      default: return sem.warning;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      child: IntrinsicHeight(
        child: Row(
          children: [
            Container(
              width: 3,
              decoration: BoxDecoration(
                color: _statusColor(context),
                borderRadius: const BorderRadius.horizontal(left: Radius.circular(14)),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 14, 14, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(request.leaveType,
                              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700,
                                  color: isDark ? MColors.darkText : MColors.text)),
                        ),
                        StatusBadge(kind: statusToBadge(request.status), small: true),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Icon(Icons.calendar_today_outlined, size: 12,
                            color: isDark ? MColors.darkTextSub : MColors.textSub),
                        const SizedBox(width: 6),
                        Text('${request.startDate} — ${request.endDate}',
                            style: TextStyle(fontSize: 12,
                                color: isDark ? MColors.darkTextSub : MColors.textSub)),
                        const SizedBox(width: 6),
                        Text(
                          '· ${request.daysRequested.toStringAsFixed(0)} ${request.daysRequested == 1 ? 'day' : 'days'}',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                              color: isDark ? MColors.darkTextMid : MColors.textMid),
                        ),
                      ],
                    ),
                    if (request.reason.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(request.reason,
                          style: TextStyle(fontSize: 12,
                              color: isDark ? MColors.darkTextSub : MColors.textSub),
                          maxLines: 1, overflow: TextOverflow.ellipsis),
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

class _Shimmer extends StatelessWidget {
  const _Shimmer();
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF1F2937) : const Color(0xFFE2E8F0);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: List.generate(4, (_) => Container(
          height: 80, margin: const EdgeInsets.only(bottom: 10),
          decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(14)),
        )),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.event_note_outlined, size: 56,
              color: AppTheme.semantics(context).textFaint),
          const SizedBox(height: 12),
          Text('No leave requests',
              style: TextStyle(color: AppTheme.semantics(context).textSub)),
          const SizedBox(height: 8),
          Text('Tap + to apply for leave',
              style: TextStyle(fontSize: 12, color: AppTheme.semantics(context).textFaint)),
        ],
      ),
    );
  }
}
