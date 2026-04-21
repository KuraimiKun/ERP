import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../models/attendance.dart';
import '../../providers/attendance_provider.dart';
import '../../providers/auth_provider.dart';

class AttendanceListScreen extends StatefulWidget {
  const AttendanceListScreen({super.key});

  @override
  State<AttendanceListScreen> createState() => _AttendanceListScreenState();
}

class _AttendanceListScreenState extends State<AttendanceListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AttendanceProvider>().loadAttendance();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AttendanceProvider>();
    final perms = context.watch<AuthProvider>().permissions;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? MColors.darkBg : MColors.bg;

    return Scaffold(
      backgroundColor: bg,
      body: SafeArea(
        child: Column(
          children: [
            // Top bar
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
                  Text('Attendance',
                      style: TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w700,
                        color: isDark ? MColors.darkText : MColors.text,
                      )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),

            // Month nav
            _MonthSelector(provider: provider),

            // Stat chips
            if (provider.stats != null)
              _StatChips(stats: provider.stats!),

            const SizedBox(height: 4),

            // List
            Expanded(
              child: provider.isLoading
                  ? const _Shimmer()
                  : provider.attendances.isEmpty
                      ? const _Empty()
                      : RefreshIndicator(
                          onRefresh: () => provider.loadAttendance(),
                          color: isDark ? MColors.darkPrimary : MColors.primary,
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 100),
                            itemCount: provider.attendances.length,
                            itemBuilder: (ctx, i) => _AttendanceTile(
                              record: provider.attendances[i],
                            ),
                          ),
                        ),
            ),
          ],
        ),
      ),
      floatingActionButton: perms.canScanQr
          ? FloatingActionButton(
              onPressed: () => Navigator.pushNamed(context, AppRoutes.qrScanner),
              child: const Icon(Icons.qr_code_scanner_rounded),
            )
          : null,
    );
  }
}

// ── Month selector ───────────────────────────────────────────────────────────

class _MonthSelector extends StatelessWidget {
  final AttendanceProvider provider;
  const _MonthSelector({required this.provider});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final surface = isDark ? MColors.darkSurface : MColors.surface;
    final border = isDark ? MColors.darkBorder : MColors.border;
    final text = isDark ? MColors.darkText : MColors.text;
    final textMid = isDark ? MColors.darkTextMid : MColors.textMid;

    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    final now = DateTime.now();
    final displayMonth = '${months[now.month - 1]} ${now.year}';

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _NavBtn(
            icon: Icons.chevron_left_rounded,
            onTap: () => provider.loadAttendance(),
            surface: surface, border: border, textMid: textMid,
          ),
          const SizedBox(width: 12),
          Text(
            displayMonth,
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: text),
          ),
          const SizedBox(width: 12),
          _NavBtn(
            icon: Icons.chevron_right_rounded,
            onTap: () => provider.loadAttendance(),
            surface: surface, border: border, textMid: textMid,
          ),
        ],
      ),
    );
  }
}

class _NavBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  final Color surface, border, textMid;

  const _NavBtn({
    required this.icon, required this.onTap,
    required this.surface, required this.border, required this.textMid,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 32, height: 32,
        decoration: BoxDecoration(
          color: surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: border, width: 0.5),
        ),
        child: Icon(icon, size: 16, color: textMid),
      ),
    );
  }
}

// ── Stat chips ───────────────────────────────────────────────────────────────

class _StatChips extends StatelessWidget {
  final AttendanceStats stats;
  const _StatChips({required this.stats});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Row(
        children: [
          _Chip(label: 'Present', value: stats.present, col: sem.success, bg: sem.successContainer),
          const SizedBox(width: 8),
          _Chip(label: 'Absent', value: stats.absent, col: sem.danger, bg: sem.dangerContainer),
          const SizedBox(width: 8),
          _Chip(label: 'Late', value: stats.late, col: sem.warning, bg: sem.warningContainer),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final int value;
  final Color col, bg;
  const _Chip({required this.label, required this.value, required this.col, required this.bg});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: col, letterSpacing: 0.4)),
            Text('$value', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: col, letterSpacing: -0.3)),
          ],
        ),
      ),
    );
  }
}

// ── Attendance tile ──────────────────────────────────────────────────────────

class _AttendanceTile extends StatelessWidget {
  final Attendance record;
  const _AttendanceTile({required this.record});

  String _fmtTime(String? dt) {
    if (dt == null) return '—';
    try {
      final t = DateTime.parse(dt).toLocal();
      final h = t.hour % 12 == 0 ? 12 : t.hour % 12;
      final m = t.minute.toString().padLeft(2, '0');
      return '$h:$m ${t.hour < 12 ? 'AM' : 'PM'}';
    } catch (_) {
      return dt;
    }
  }

  String _dayName(String date) {
    try {
      final d = DateTime.parse(date);
      const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
      return days[d.weekday - 1];
    } catch (_) { return ''; }
  }

  int _dayNum(String date) {
    try { return DateTime.parse(date).day; } catch (_) { return 0; }
  }

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final surface = isDark ? MColors.darkSurface : MColors.surface;
    final border = isDark ? MColors.darkBorder : MColors.border;
    final text = isDark ? MColors.darkText : MColors.text;
    final textSub = isDark ? MColors.darkTextSub : MColors.textSub;

    Color statusColor;
    if (!record.isPresent) {
      statusColor = sem.danger;
    } else if (record.isLate) {
      statusColor = sem.warning;
    } else {
      statusColor = sem.success;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: border, width: 0.5),
      ),
      child: IntrinsicHeight(
        child: Row(
          children: [
            // Status strip
            Container(
              width: 3,
              decoration: BoxDecoration(
                color: statusColor,
                borderRadius: const BorderRadius.horizontal(left: Radius.circular(14)),
              ),
            ),
            // Date
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 14, 12, 14),
              child: SizedBox(
                width: 40,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      '${_dayNum(record.date)}',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: text, height: 1),
                    ),
                    const SizedBox(height: 3),
                    Text(_dayName(record.date),
                        style: TextStyle(fontSize: 11, color: textSub, fontWeight: FontWeight.w500)),
                  ],
                ),
              ),
            ),
            // Times
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 14),
                child: record.isPresent && record.checkIn != null
                    ? Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Row(
                            children: [
                              Container(width: 6, height: 6,
                                  decoration: BoxDecoration(color: sem.success, shape: BoxShape.circle)),
                              const SizedBox(width: 6),
                              Text(_fmtTime(record.checkIn),
                                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: text)),
                              Text('  →  ', style: TextStyle(color: isDark ? MColors.darkTextFaint : MColors.textFaint)),
                              Text(
                                record.checkOut != null ? _fmtTime(record.checkOut) : 'In',
                                style: TextStyle(
                                  fontSize: 13, fontWeight: FontWeight.w600,
                                  color: record.checkOut != null ? text : sem.warning,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 3),
                          Text(
                            record.checkOut != null ? '${record.hoursWorked}h worked' : 'Still working',
                            style: TextStyle(fontSize: 11, color: textSub),
                          ),
                        ],
                      )
                    : Text('No record', style: TextStyle(fontSize: 13, color: textSub, fontWeight: FontWeight.w500)),
              ),
            ),
            // Badge
            Padding(
              padding: const EdgeInsets.only(right: 14),
              child: record.isLate
                  ? Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: sem.warningContainer,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text('LATE',
                          style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: sem.warning, letterSpacing: 0.4)),
                    )
                  : const SizedBox.shrink(),
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
    final c = Theme.of(context).brightness == Brightness.dark ? const Color(0xFF1F2937) : const Color(0xFFE2E8F0);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: List.generate(6, (_) => Container(
          height: 68, margin: const EdgeInsets.only(bottom: 8),
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
          Icon(Icons.calendar_month_outlined, size: 56, color: AppTheme.semantics(context).textFaint),
          const SizedBox(height: 12),
          Text('No attendance records', style: TextStyle(color: AppTheme.semantics(context).textSub)),
        ],
      ),
    );
  }
}
