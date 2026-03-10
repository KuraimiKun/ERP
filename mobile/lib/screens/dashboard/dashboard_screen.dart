import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/dashboard_provider.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/stat_card.dart';
import '../../widgets/loading_indicator.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DashboardProvider>().loadDashboard();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final dashboard = context.watch<DashboardProvider>();
    final auth = context.watch<AuthProvider>();
    final perms = auth.permissions;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.dashboard),
        actions: [
          if (dashboard.data != null && dashboard.data!.unreadNotifications > 0)
            Stack(
              children: [
                IconButton(
                  icon: const Icon(Icons.notifications_outlined),
                  onPressed: () =>
                      Navigator.pushNamed(context, AppRoutes.notifications),
                ),
                Positioned(
                  right: 8,
                  top: 8,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.error,
                      shape: BoxShape.circle,
                    ),
                    child: Text(
                      '${dashboard.data!.unreadNotifications}',
                      style: TextStyle(color: Theme.of(context).colorScheme.onError, fontSize: 10),
                    ),
                  ),
                ),
              ],
            )
          else
            IconButton(
              icon: const Icon(Icons.notifications_outlined),
              onPressed: () =>
                  Navigator.pushNamed(context, AppRoutes.notifications),
            ),
        ],
      ),
      drawer: const AppDrawer(),
      body: dashboard.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : dashboard.error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(dashboard.error!),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: () => dashboard.loadDashboard(),
                        child: Text(l10n.retry),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: () => dashboard.loadDashboard(),
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      // Today's Attendance Card
                      if (dashboard.data?.todayAttendance != null)
                        _TodayAttendanceCard(
                          attendance: dashboard.data!.todayAttendance!,
                          canScan: perms.canScanQr,
                        )
                      else if (perms.canScanQr)
                        Card(
                          child: ListTile(
                            leading: Icon(Icons.qr_code_scanner,
                                color: Theme.of(context).colorScheme.primary),
                            title: Text(l10n.notCheckedIn),
                            subtitle: Text(l10n.scanQR),
                            trailing: const Icon(Icons.arrow_forward_ios,
                                size: 16),
                            onTap: () => Navigator.pushNamed(
                                context, AppRoutes.qrScanner),
                          ),
                        ),
                      const SizedBox(height: 16),

                      // Month Stats
                      if (dashboard.data != null) ...[
                        Text(l10n.monthStats,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Expanded(
                              child: StatCard(
                                title: l10n.present,
                                value:
                                    '${dashboard.data!.monthStats.present}',
                                icon: Icons.check_circle_outline,
                                color: AppTheme.semantics(context).success,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: StatCard(
                                title: l10n.absent,
                                value:
                                    '${dashboard.data!.monthStats.absent}',
                                icon: Icons.cancel_outlined,
                                color: AppTheme.semantics(context).danger,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: StatCard(
                                title: l10n.late,
                                value:
                                    '${dashboard.data!.monthStats.late}',
                                icon: Icons.schedule,
                                color: AppTheme.semantics(context).warning,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Quick actions
                      Row(
                        children: [
                          if (perms.canManageLeaves)
                            Expanded(
                              child: StatCard(
                                title: l10n.pendingLeaves,
                                value: '${dashboard.data?.pendingLeaves ?? 0}',
                                icon: Icons.event_note_outlined,
                                color: Theme.of(context).colorScheme.tertiary,
                                onTap: () => Navigator.pushNamed(
                                    context, AppRoutes.leaves),
                              ),
                            ),
                          if (perms.canManageLeaves && perms.canViewTasks)
                            const SizedBox(width: 8),
                          if (perms.canViewTasks)
                            Expanded(
                              child: StatCard(
                                title: l10n.pendingTasks,
                                value: '${dashboard.data?.pendingTasks ?? 0}',
                                icon: Icons.task_alt_outlined,
                                color: Theme.of(context).colorScheme.secondary,
                                onTap: () => Navigator.pushNamed(
                                    context, AppRoutes.tasks),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Recent Payslips
                      if (perms.canViewPayslips &&
                          (dashboard.data?.recentPayslips.isNotEmpty ?? false)) ...[
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(l10n.recentPayslips,
                                style: Theme.of(context)
                                    .textTheme
                                    .titleMedium
                                    ?.copyWith(fontWeight: FontWeight.bold)),
                            TextButton(
                              onPressed: () => Navigator.pushNamed(
                                  context, AppRoutes.payslips),
                              child: Text(l10n.attendance),
                            ),
                          ],
                        ),
                        ...dashboard.data!.recentPayslips.map(
                          (p) => Card(
                            child: ListTile(
                              leading: Icon(Icons.receipt_long,
                                  color: AppTheme.semantics(context).success),
                              title: Text(
                                  '${p.periodStart} - ${p.periodEnd}'),
                              subtitle: Text(p.status),
                              trailing: Text(
                                p.netSalary,
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.semantics(context).success,
                                ),
                              ),
                              onTap: () => Navigator.pushNamed(
                                context,
                                AppRoutes.payslipDetail,
                                arguments: p.id,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
    );
  }
}

class _TodayAttendanceCard extends StatelessWidget {
  final dynamic attendance;
  final bool canScan;

  const _TodayAttendanceCard({
    required this.attendance,
    required this.canScan,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final semantics = AppTheme.semantics(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  l10n.todayAttendance,
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.bold),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: attendance.checkedIn
                        ? semantics.successContainer
                        : semantics.warningContainer,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    attendance.checkedIn
                        ? (attendance.checkedOut
                            ? l10n.checkedOut
                            : l10n.checkedIn)
                        : l10n.notCheckedIn,
                    style: TextStyle(
                      color: attendance.checkedIn
                          ? semantics.success
                          : semantics.warning,
                      fontWeight: FontWeight.w600,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            if (attendance.checkIn != null) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(Icons.login, size: 18, color: semantics.textMuted),
                  const SizedBox(width: 8),
                  Text('${l10n.checkIn}: ${attendance.checkIn}'),
                  if (attendance.isLate)
                    Container(
                      margin: const EdgeInsetsDirectional.only(start: 8),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: semantics.dangerContainer,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        l10n.late,
                        style: TextStyle(
                            color: semantics.danger, fontSize: 11),
                      ),
                    ),
                ],
              ),
              if (attendance.checkOut != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Row(
                    children: [
                      Icon(Icons.logout, size: 18, color: semantics.textMuted),
                      const SizedBox(width: 8),
                      Text('${l10n.checkOut}: ${attendance.checkOut}'),
                    ],
                  ),
                ),
            ],
            if (canScan && !attendance.checkedOut) ...[
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () =>
                      Navigator.pushNamed(context, AppRoutes.qrScanner),
                  icon: const Icon(Icons.qr_code_scanner),
                  label: Text(attendance.checkedIn
                      ? l10n.checkOut
                      : l10n.checkIn),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
