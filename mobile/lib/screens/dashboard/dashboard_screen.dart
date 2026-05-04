import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/dashboard_provider.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/avatar_widget.dart';
import '../../widgets/icon_tile.dart';
import '../../widgets/section_header.dart';
import '../../widgets/status_badge.dart';

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
    final dashboard = context.watch<DashboardProvider>();
    final auth = context.watch<AuthProvider>();
    final perms = auth.permissions;
    final employee = auth.employee;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? MColors.darkBg : MColors.bg;

    return Scaffold(
      backgroundColor: bg,
      drawer: const AppDrawer(),
      body: SafeArea(
        child: dashboard.isLoading
            ? const _DashboardShimmer()
            : dashboard.error != null
            ? _ErrorState(
                error: dashboard.error!,
                onRetry: () => dashboard.loadDashboard(),
              )
            : RefreshIndicator(
                onRefresh: () => dashboard.loadDashboard(),
                color: isDark ? MColors.darkPrimary : MColors.primary,
                child: CustomScrollView(
                  slivers: [
                    SliverToBoxAdapter(
                      child: _Header(
                        employee: employee,
                        unread: dashboard.data?.unreadNotifications ?? 0,
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: _AttendanceCard(
                          data: dashboard.data,
                          canScan: perms.canScanQr,
                        ),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                        child: _MonthStatRow(data: dashboard.data),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: SectionHeader(title: 'Quick actions'),
                    ),
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: _QuickActionsGrid(
                          perms: perms,
                          data: dashboard.data,
                        ),
                      ),
                    ),
                    if (perms.canViewPayslips &&
                        (dashboard.data?.recentPayslips.isNotEmpty ??
                            false)) ...[
                      SliverToBoxAdapter(
                        child: SectionHeader(
                          title: 'Recent payslips',
                          actionLabel: 'See all',
                          onAction: () =>
                              Navigator.pushNamed(context, AppRoutes.payslips),
                        ),
                      ),
                      SliverToBoxAdapter(
                        child: _PayslipRow(
                          payslips: dashboard.data!.recentPayslips,
                        ),
                      ),
                    ],
                    const SliverToBoxAdapter(child: SizedBox(height: 32)),
                  ],
                ),
              ),
      ),
    );
  }
}

// ── Header ───────────────────────────────────────────────────────────────────

class _Header extends StatelessWidget {
  final dynamic employee;
  final int unread;

  const _Header({this.employee, required this.unread});

  String _greeting() {
    final h = DateTime.now().hour;
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  String _dateStr() {
    final now = DateTime.now();
    const days = [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ];
    const months = [
      'January',
      'February',
      'March',
      'April',
      'May',
      'June',
      'July',
      'August',
      'September',
      'October',
      'November',
      'December',
    ];
    return '${days[now.weekday - 1]}, ${now.day} ${months[now.month - 1]} ${now.year}';
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final name = employee?.fullName ?? employee?.firstName ?? 'Employee';
    final initials = initialsFromName(name);

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _greeting(),
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: isDark ? MColors.darkTextSub : MColors.textSub,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  name,
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.4,
                    color: isDark ? MColors.darkText : MColors.text,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _dateStr(),
                  style: TextStyle(
                    fontSize: 12,
                    color: isDark ? MColors.darkTextFaint : MColors.textFaint,
                  ),
                ),
              ],
            ),
          ),
          Builder(
            builder: (ctx) => GestureDetector(
              onTap: () => Scaffold.of(ctx).openDrawer(),
              child: Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isDark ? MColors.darkBorder : MColors.border,
                  ),
                  color: isDark ? MColors.darkSurface : MColors.surface,
                ),
                child: const Icon(Icons.menu, size: 20),
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: () => Navigator.pushNamed(context, AppRoutes.notifications),
            child: Stack(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: isDark ? MColors.darkBorder : MColors.border,
                    ),
                    color: isDark ? MColors.darkSurface : MColors.surface,
                  ),
                  child: const Icon(Icons.notifications_outlined, size: 18),
                ),
                if (unread > 0)
                  Positioned(
                    top: 8,
                    right: 10,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: isDark ? MColors.darkError : MColors.error,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: isDark ? MColors.darkSurface : MColors.surface,
                          width: 1.5,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: () => Navigator.pushNamed(context, AppRoutes.profile),
            child: AvatarWidget(
              initials: initials,
              bg: isDark ? MColors.darkAccent : MColors.accent,
              size: 42,
              photoUrl: employee?.photoUrl,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Attendance card ──────────────────────────────────────────────────────────

class _AttendanceCard extends StatelessWidget {
  final dynamic data;
  final bool canScan;

  const _AttendanceCard({this.data, required this.canScan});

  @override
  Widget build(BuildContext context) {
    final att = data?.todayAttendance;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primary = isDark ? MColors.darkPrimary : MColors.primary;
    final primaryDeep = isDark ? MColors.darkPrimaryDeep : MColors.primaryDeep;

    final bool checkedIn = att?.checkedIn == true;
    final bool checkedOut = att?.checkedOut == true;

    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [primary, primaryDeep],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      padding: const EdgeInsets.all(20),
      child: Stack(
        children: [
          Positioned(
            top: -30,
            right: -30,
            child: Container(
              width: 140,
              height: 140,
              decoration: const BoxDecoration(
                color: Color(0x14FFFFFF),
                shape: BoxShape.circle,
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    decoration: BoxDecoration(
                      color: checkedIn
                          ? const Color(0xFF34D399)
                          : Colors.white54,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    checkedIn
                        ? (checkedOut ? 'Checked out' : 'Checked in')
                        : 'Not checked in',
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xCCFFFFFF),
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.8,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              if (att?.checkIn != null) ...[
                Text(
                  _formatTime(att.checkIn.toString()),
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                    letterSpacing: -0.6,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  checkedOut
                      ? 'Checked out at ${_formatTime(att.checkOut.toString())}'
                      : 'Working now',
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xCCFFFFFF),
                  ),
                ),
              ] else
                const Text(
                  'Tap below to check in',
                  style: TextStyle(
                    fontSize: 16,
                    color: Color(0xB3FFFFFF),
                    fontWeight: FontWeight.w500,
                  ),
                ),
              if (canScan && !checkedOut) ...[
                const SizedBox(height: 18),
                GestureDetector(
                  onTap: () =>
                      Navigator.pushNamed(context, AppRoutes.qrScanner),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0x26FFFFFF),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0x26FFFFFF)),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.qr_code_rounded,
                          size: 18,
                          color: Colors.white,
                        ),
                        const SizedBox(width: 10),
                        Text(
                          checkedIn ? 'Scan to check out' : 'Scan to check in',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                        const Spacer(),
                        const Icon(
                          Icons.arrow_forward_rounded,
                          size: 16,
                          color: Colors.white,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  String _formatTime(String dt) {
    try {
      final t = DateTime.parse(dt).toLocal();
      final h = t.hour % 12 == 0 ? 12 : t.hour % 12;
      final m = t.minute.toString().padLeft(2, '0');
      final suffix = t.hour < 12 ? 'AM' : 'PM';
      return '$h:$m $suffix';
    } catch (_) {
      return dt;
    }
  }
}

// ── Month stats row ──────────────────────────────────────────────────────────

class _MonthStatRow extends StatelessWidget {
  final dynamic data;
  const _MonthStatRow({this.data});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final surface = isDark ? MColors.darkSurface : MColors.surface;
    final border = isDark ? MColors.darkBorder : MColors.border;

    final present = data?.monthStats?.present ?? 0;
    final absent = data?.monthStats?.absent ?? 0;
    final late = data?.monthStats?.late ?? 0;

    final stats = [
      {
        'v': present,
        'l': 'Present',
        'icon': Icons.check_circle_outline_rounded,
        'col': sem.success,
        'bg': sem.successContainer,
      },
      {
        'v': absent,
        'l': 'Absent',
        'icon': Icons.cancel_outlined,
        'col': sem.danger,
        'bg': sem.dangerContainer,
      },
      {
        'v': late,
        'l': 'Late',
        'icon': Icons.schedule_rounded,
        'col': sem.warning,
        'bg': sem.warningContainer,
      },
    ];

    return Row(
      children: stats.map((s) {
        final idx = stats.indexOf(s);
        return Expanded(
          child: Container(
            margin: EdgeInsets.only(left: idx == 0 ? 0 : 10),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: border, width: 0.5),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                IconTile(
                  icon: s['icon'] as IconData,
                  bg: s['bg'] as Color,
                  color: s['col'] as Color,
                  size: 30,
                  iconSize: 16,
                  radius: 8,
                ),
                const SizedBox(height: 10),
                Text(
                  '${s['v']}',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.4,
                    color: isDark ? MColors.darkText : MColors.text,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  '${s['l']}',
                  style: TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w500,
                    color: isDark ? MColors.darkTextSub : MColors.textSub,
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

// ── Quick actions grid ───────────────────────────────────────────────────────

class _QuickActionsGrid extends StatelessWidget {
  final dynamic perms;
  final dynamic data;

  const _QuickActionsGrid({required this.perms, this.data});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);

    final actions = [
      if (perms.canManageLeaves)
        _ActionItem(
          title: 'Leave requests',
          sub: '${data?.pendingLeaves ?? 0} pending',
          icon: Icons.event_note_outlined,
          iconBg: sem.successContainer,
          iconColor: sem.success,
          badge: data?.pendingLeaves,
          badgeColor: sem.warning,
          route: AppRoutes.leaves,
        ),
      if (perms.canViewTasks)
        _ActionItem(
          title: 'My tasks',
          sub: '${data?.pendingTasks ?? 0} open',
          icon: Icons.task_alt_outlined,
          iconBg: sem.infoContainer,
          iconColor: sem.info,
          badge: data?.pendingTasks,
          badgeColor: sem.info,
          route: AppRoutes.tasks,
        ),
      _ActionItem(
        title: 'Notifications',
        sub: '${data?.unreadNotifications ?? 0} unread',
        icon: Icons.notifications_outlined,
        iconBg: sem.purpleContainer,
        iconColor: sem.purple,
        badge: data?.unreadNotifications,
        badgeColor: sem.danger,
        route: AppRoutes.notifications,
      ),
      if (perms.canViewPayslips)
        _ActionItem(
          title: 'Latest payslip',
          sub: data?.recentPayslips?.isNotEmpty == true
              ? data!.recentPayslips.first.netSalary
              : '—',
          icon: Icons.receipt_long_outlined,
          iconBg: sem.accentContainer,
          iconColor: sem.accent,
          route: AppRoutes.payslips,
        ),
    ];

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: actions.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
        childAspectRatio: 1.4,
      ),
      itemBuilder: (ctx, i) => _QuickActionCard(item: actions[i]),
    );
  }
}

class _ActionItem {
  final String title;
  final String sub;
  final IconData icon;
  final Color iconBg;
  final Color iconColor;
  final int? badge;
  final Color? badgeColor;
  final String route;

  const _ActionItem({
    required this.title,
    required this.sub,
    required this.icon,
    required this.iconBg,
    required this.iconColor,
    this.badge,
    this.badgeColor,
    required this.route,
  });
}

class _QuickActionCard extends StatelessWidget {
  final _ActionItem item;
  const _QuickActionCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final surface = isDark ? MColors.darkSurface : MColors.surface;
    final border = isDark ? MColors.darkBorder : MColors.border;

    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, item.route),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: border, width: 0.5),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                IconTile(
                  icon: item.icon,
                  bg: item.iconBg,
                  color: item.iconColor,
                  size: 32,
                  iconSize: 17,
                ),
                const Spacer(),
                if ((item.badge ?? 0) > 0)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: item.badgeColor,
                      borderRadius: BorderRadius.circular(11),
                    ),
                    child: Text(
                      '${item.badge}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
              ],
            ),
            const Spacer(),
            Text(
              item.title,
              style: TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
                color: isDark ? MColors.darkText : MColors.text,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              item.sub,
              style: TextStyle(
                fontSize: 11.5,
                color: isDark ? MColors.darkTextSub : MColors.textSub,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Recent payslips row ──────────────────────────────────────────────────────

class _PayslipRow extends StatelessWidget {
  final List<dynamic> payslips;
  const _PayslipRow({required this.payslips});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final surface = isDark ? MColors.darkSurface : MColors.surface;
    final border = isDark ? MColors.darkBorder : MColors.border;

    return SizedBox(
      height: 110,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        scrollDirection: Axis.horizontal,
        itemCount: payslips.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (ctx, i) {
          final p = payslips[i];
          return GestureDetector(
            onTap: () => Navigator.pushNamed(
              ctx,
              AppRoutes.payslipDetail,
              arguments: p.id,
            ),
            child: Container(
              width: 180,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: surface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: border, width: 0.5),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${p.periodStart ?? ''} ${p.periodEnd ?? ''}'.trim(),
                    style: TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                      color: isDark ? MColors.darkTextSub : MColors.textSub,
                      letterSpacing: 0.4,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    p.netSalary ?? '—',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.3,
                      color: isDark ? MColors.darkText : MColors.text,
                    ),
                  ),
                  const SizedBox(height: 10),
                  StatusBadge(
                    kind: statusToBadge(p.status ?? 'draft'),
                    small: true,
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

// ── Loading shimmer ──────────────────────────────────────────────────────────

class _DashboardShimmer extends StatelessWidget {
  const _DashboardShimmer();

  @override
  Widget build(BuildContext context) {
    final shimmerColor = Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF1F2937)
        : const Color(0xFFE2E8F0);

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Container(
            height: 44,
            decoration: BoxDecoration(
              color: shimmerColor,
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          const SizedBox(height: 16),
          Container(
            height: 120,
            decoration: BoxDecoration(
              color: shimmerColor,
              borderRadius: BorderRadius.circular(20),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: List.generate(
              3,
              (_) => Expanded(
                child: Container(
                  height: 90,
                  margin: const EdgeInsets.only(right: 10),
                  decoration: BoxDecoration(
                    color: shimmerColor,
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Error state ──────────────────────────────────────────────────────────────

class _ErrorState extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;
  const _ErrorState({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off_outlined,
              size: 56,
              color: AppTheme.semantics(context).textMuted,
            ),
            const SizedBox(height: 16),
            Text(error, textAlign: TextAlign.center),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
