import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/attendance_provider.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/loading_indicator.dart';
import '../../widgets/empty_state.dart';

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
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<AttendanceProvider>();

    return Scaffold(
      appBar: AppBar(title: Text(l10n.attendanceHistory)),
      drawer: const AppDrawer(),
      body: provider.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : RefreshIndicator(
              onRefresh: () => provider.loadAttendance(),
              child: Column(
                children: [
                  // Stats bar
                  if (provider.stats != null)
                    Container(
                      padding: const EdgeInsets.all(16),
                      color: Theme.of(context).primaryColor.withValues(alpha: 0.05),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceAround,
                        children: [
                          _StatChip(
                            label: l10n.present,
                            value: '${provider.stats!.present}',
                            color: AppTheme.semantics(context).success,
                          ),
                          _StatChip(
                            label: l10n.absent,
                            value: '${provider.stats!.absent}',
                            color: AppTheme.semantics(context).danger,
                          ),
                          _StatChip(
                            label: l10n.late,
                            value: '${provider.stats!.late}',
                            color: AppTheme.semantics(context).warning,
                          ),
                        ],
                      ),
                    ),
                  // Attendance list
                  Expanded(
                    child: provider.attendances.isEmpty
                        ? EmptyState(
                            icon: Icons.access_time_outlined,
                            message: l10n.noData,
                          )
                        : ListView.builder(
                            itemCount: provider.attendances.length,
                            itemBuilder: (context, index) {
                              final a = provider.attendances[index];
                              return Card(
                                margin: const EdgeInsets.symmetric(
                                    horizontal: 16, vertical: 4),
                                child: ListTile(
                                  leading: CircleAvatar(
                                    backgroundColor: a.isPresent
                                        ? AppTheme.semantics(context).successContainer
                                        : AppTheme.semantics(context).dangerContainer,
                                    child: Icon(
                                      a.isPresent
                                          ? Icons.check
                                          : Icons.close,
                                      color: a.isPresent
                                          ? AppTheme.semantics(context).success
                                          : AppTheme.semantics(context).danger,
                                    ),
                                  ),
                                  title: Text(a.date),
                                  subtitle: Text(
                                    a.checkIn != null
                                        ? '${l10n.checkIn}: ${a.checkIn}${a.checkOut != null ? '  |  ${l10n.checkOut}: ${a.checkOut}' : ''}'
                                        : l10n.absent,
                                  ),
                                  trailing: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    crossAxisAlignment: CrossAxisAlignment.end,
                                    children: [
                                      Text('${a.hoursWorked}h',
                                          style: const TextStyle(
                                              fontWeight: FontWeight.bold)),
                                      if (a.isLate)
                                        Text(
                                          '${a.lateMinutes} ${l10n.lateMinutes}',
                                          style: TextStyle(
                                            fontSize: 11,
                                            color: AppTheme.semantics(context).danger,
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatChip({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        const SizedBox(height: 2),
        Text(label,
            style: TextStyle(fontSize: 12, color: AppTheme.semantics(context).textMuted)),
      ],
    );
  }
}
