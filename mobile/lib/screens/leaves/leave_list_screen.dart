import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/leave_provider.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/loading_indicator.dart';
import '../../widgets/empty_state.dart';

class LeaveListScreen extends StatefulWidget {
  const LeaveListScreen({super.key});

  @override
  State<LeaveListScreen> createState() => _LeaveListScreenState();
}

class _LeaveListScreenState extends State<LeaveListScreen> {
  String _statusFilter = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LeaveProvider>().loadLeaves();
    });
  }

  Color _statusColor(BuildContext context, String status) {
    switch (status) {
      case 'pending':
        return AppTheme.semantics(context).warning;
      case 'approved':
        return AppTheme.semantics(context).success;
      case 'rejected':
        return AppTheme.semantics(context).danger;
      case 'cancelled':
        return AppTheme.semantics(context).textMuted;
      default:
        return Theme.of(context).colorScheme.primary;
    }
  }

  String _statusLabel(String status, AppLocalizations l10n) {
    switch (status) {
      case 'pending':
        return l10n.pending;
      case 'approved':
        return l10n.approved;
      case 'rejected':
        return l10n.rejected;
      case 'cancelled':
        return l10n.cancelled;
      default:
        return status;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<LeaveProvider>();

    return Scaffold(
      appBar: AppBar(title: Text(l10n.leaveRequests)),
      drawer: const AppDrawer(),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          await Navigator.pushNamed(context, AppRoutes.leaveForm);
          if (mounted) provider.loadLeaves();
        },
        child: const Icon(Icons.add),
      ),
      body: provider.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : RefreshIndicator(
              onRefresh: () => provider.loadLeaves(status: _statusFilter),
              child: Column(
                children: [
                  // Leave balances
                  if (provider.balances.isNotEmpty)
                    SizedBox(
                      height: 80,
                      child: ListView.builder(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
                        itemCount: provider.balances.length,
                        itemBuilder: (context, index) {
                          final b = provider.balances[index];
                          return Container(
                            width: 130,
                            margin: const EdgeInsets.symmetric(horizontal: 4),
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.surface,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(b.name,
                                    style: const TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis),
                                const SizedBox(height: 4),
                                Text(
                                  '${b.remaining.toInt()} / ${b.daysAllowed} ${l10n.remaining}',
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: AppTheme.semantics(context).textMuted,
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),

                  // Status filter chips
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          _FilterChip(
                            label: l10n.attendance, // "All"
                            selected: _statusFilter.isEmpty,
                            onSelected: () {
                              setState(() => _statusFilter = '');
                              provider.loadLeaves();
                            },
                          ),
                          _FilterChip(
                            label: l10n.pending,
                            selected: _statusFilter == 'pending',
                            onSelected: () {
                              setState(() => _statusFilter = 'pending');
                              provider.loadLeaves(status: 'pending');
                            },
                          ),
                          _FilterChip(
                            label: l10n.approved,
                            selected: _statusFilter == 'approved',
                            onSelected: () {
                              setState(() => _statusFilter = 'approved');
                              provider.loadLeaves(status: 'approved');
                            },
                          ),
                          _FilterChip(
                            label: l10n.rejected,
                            selected: _statusFilter == 'rejected',
                            onSelected: () {
                              setState(() => _statusFilter = 'rejected');
                              provider.loadLeaves(status: 'rejected');
                            },
                          ),
                        ],
                      ),
                    ),
                  ),
                  const Divider(height: 1),

                  // Leave list
                  Expanded(
                    child: provider.leaves.isEmpty
                        ? EmptyState(
                            icon: Icons.event_note_outlined,
                            message: l10n.noData,
                          )
                        : ListView.builder(
                            itemCount: provider.leaves.length,
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            itemBuilder: (context, index) {
                              final leave = provider.leaves[index];
                              return Card(
                                margin: const EdgeInsets.symmetric(
                                    horizontal: 16, vertical: 4),
                                child: ListTile(
                                  title: Text(leave.leaveType),
                                  subtitle: Text(
                                    '${leave.startDate} - ${leave.endDate} (${leave.daysRequested.toInt()} ${l10n.daysRequested})',
                                  ),
                                  trailing: Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: _statusColor(context, leave.status)
                                          .withValues(alpha: 0.1),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      _statusLabel(leave.status, l10n),
                                      style: TextStyle(
                                        color: _statusColor(context, leave.status),
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                                  onTap: leave.isPending
                                      ? () => _showCancelDialog(
                                          context, leave.id, l10n)
                                      : null,
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

  void _showCancelDialog(
      BuildContext context, int leaveId, AppLocalizations l10n) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.cancelLeave),
        content: Text(l10n.confirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(l10n.no),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await context.read<LeaveProvider>().cancelLeave(leaveId);
            },
            child: Text(l10n.yes, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onSelected;

  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.only(end: 8),
      child: ChoiceChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) => onSelected(),
      ),
    );
  }
}
