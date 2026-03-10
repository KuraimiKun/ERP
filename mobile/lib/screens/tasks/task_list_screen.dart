import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/task_provider.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/loading_indicator.dart';
import '../../widgets/empty_state.dart';

class TaskListScreen extends StatefulWidget {
  const TaskListScreen({super.key});

  @override
  State<TaskListScreen> createState() => _TaskListScreenState();
}

class _TaskListScreenState extends State<TaskListScreen> {
  String _statusFilter = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TaskProvider>().loadTasks();
    });
  }

  Color _priorityColor(BuildContext context, String priority) {
    switch (priority) {
      case 'urgent':
        return AppTheme.semantics(context).danger;
      case 'high':
        return AppTheme.semantics(context).warning;
      case 'medium':
        return Theme.of(context).colorScheme.primary;
      case 'low':
        return AppTheme.semantics(context).textMuted;
      default:
        return Theme.of(context).colorScheme.primary;
    }
  }

  String _priorityLabel(String priority, AppLocalizations l10n) {
    switch (priority) {
      case 'urgent':
        return l10n.urgent;
      case 'high':
        return l10n.high;
      case 'medium':
        return l10n.medium;
      case 'low':
        return l10n.low;
      default:
        return priority;
    }
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'todo':
        return Icons.radio_button_unchecked;
      case 'in_progress':
        return Icons.pending;
      case 'completed':
        return Icons.check_circle;
      case 'on_hold':
        return Icons.pause_circle;
      default:
        return Icons.circle_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<TaskProvider>();

    return Scaffold(
      appBar: AppBar(title: Text(l10n.tasks)),
      drawer: const AppDrawer(),
      body: provider.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : RefreshIndicator(
              onRefresh: () => provider.loadTasks(status: _statusFilter),
              child: Column(
                children: [
                  // Count chips
                  Container(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _CountChip(
                          label: l10n.todo,
                          count: provider.counts.todo,
                          color: AppTheme.semantics(context).textMuted,
                          selected: _statusFilter == 'todo',
                          onTap: () {
                            setState(() => _statusFilter =
                                _statusFilter == 'todo' ? '' : 'todo');
                            provider.loadTasks(status: _statusFilter);
                          },
                        ),
                        _CountChip(
                          label: l10n.inProgress,
                          count: provider.counts.inProgress,
                          color: Theme.of(context).colorScheme.primary,
                          selected: _statusFilter == 'in_progress',
                          onTap: () {
                            setState(() => _statusFilter =
                                _statusFilter == 'in_progress'
                                    ? ''
                                    : 'in_progress');
                            provider.loadTasks(status: _statusFilter);
                          },
                        ),
                        _CountChip(
                          label: l10n.completed,
                          count: provider.counts.completed,
                          color: AppTheme.semantics(context).success,
                          selected: _statusFilter == 'completed',
                          onTap: () {
                            setState(() => _statusFilter =
                                _statusFilter == 'completed'
                                    ? ''
                                    : 'completed');
                            provider.loadTasks(status: _statusFilter);
                          },
                        ),
                      ],
                    ),
                  ),
                  const Divider(height: 1),
                  Expanded(
                    child: provider.tasks.isEmpty
                        ? EmptyState(
                            icon: Icons.task_alt_outlined,
                            message: l10n.noData,
                          )
                        : ListView.builder(
                            itemCount: provider.tasks.length,
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            itemBuilder: (context, index) {
                              final task = provider.tasks[index];
                              return Card(
                                margin: const EdgeInsets.symmetric(
                                    horizontal: 16, vertical: 4),
                                child: ListTile(
                                  leading: Icon(
                                    _statusIcon(task.status),
                                    color: task.status == 'completed'
                                        ? AppTheme.semantics(context).success
                                        : Theme.of(context).colorScheme.primary,
                                  ),
                                  title: Text(
                                    task.title,
                                    style: TextStyle(
                                      decoration:
                                          task.status == 'completed'
                                              ? TextDecoration.lineThrough
                                              : null,
                                    ),
                                  ),
                                  subtitle: Row(
                                    children: [
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: _priorityColor(context, task.priority)
                                              .withValues(alpha: 0.1),
                                          borderRadius:
                                              BorderRadius.circular(4),
                                        ),
                                        child: Text(
                                          _priorityLabel(
                                              task.priority, l10n),
                                          style: TextStyle(
                                            fontSize: 11,
                                            color: _priorityColor(
                                                context, task.priority),
                                          ),
                                        ),
                                      ),
                                      if (task.dueDate != null) ...[
                                        const SizedBox(width: 8),
                                        Icon(Icons.schedule,
                                            size: 14,
                                            color: task.isOverdue
                                                ? AppTheme.semantics(context).danger
                                                : AppTheme.semantics(context).textMuted),
                                        const SizedBox(width: 2),
                                        Text(
                                          task.dueDate!,
                                          style: TextStyle(
                                            fontSize: 11,
                                            color: task.isOverdue
                                                ? AppTheme.semantics(context).danger
                                                : AppTheme.semantics(context).textMuted,
                                          ),
                                        ),
                                      ],
                                    ],
                                  ),
                                  trailing: task.commentCount > 0
                                      ? Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Icon(Icons.comment_outlined,
                                                size: 14, color: AppTheme.semantics(context).textMuted),
                                            const SizedBox(width: 2),
                                            Text('${task.commentCount}',
                                                style: const TextStyle(
                                                    fontSize: 12)),
                                          ],
                                        )
                                      : null,
                                  onTap: () async {
                                    await Navigator.pushNamed(
                                      context,
                                      AppRoutes.taskDetail,
                                      arguments: task.id,
                                    );
                                    if (mounted) {
                                      provider.loadTasks(
                                          status: _statusFilter);
                                    }
                                  },
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

class _CountChip extends StatelessWidget {
  final String label;
  final int count;
  final Color color;
  final bool selected;
  final VoidCallback onTap;

  const _CountChip({
    required this.label,
    required this.count,
    required this.color,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? color.withValues(alpha: 0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected ? color : Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('$count',
                style: TextStyle(
                    fontWeight: FontWeight.bold, color: color)),
            const SizedBox(width: 4),
            Text(label,
                style: TextStyle(fontSize: 12, color: AppTheme.semantics(context).textMuted)),
          ],
        ),
      ),
    );
  }
}
