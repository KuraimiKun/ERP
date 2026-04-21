import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/task_provider.dart';
import '../../widgets/status_badge.dart';

class TaskListScreen extends StatefulWidget {
  const TaskListScreen({super.key});

  @override
  State<TaskListScreen> createState() => _TaskListScreenState();
}

class _TaskListScreenState extends State<TaskListScreen> {
  int _tabIndex = 0;
  static const _tabs = ['All', 'To Do', 'In Progress', 'Done'];
  static const _statusFilters = ['', 'todo', 'in_progress', 'completed'];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TaskProvider>().loadTasks();
    });
  }

  Color _priorityColor(String priority) {
    switch (priority) {
      case 'urgent':
      case 'high':
        return const Color(0xFFEF4444);
      case 'medium':
        return const Color(0xFFF59E0B);
      case 'low':
        return const Color(0xFF3B82F6);
      default:
        return const Color(0xFF6B7280);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TaskProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final filtered = _statusFilters[_tabIndex].isEmpty
        ? provider.tasks
        : provider.tasks.where((t) => t.status == _statusFilters[_tabIndex]).toList();

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
                  Text('Tasks', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),

            // Stat chips
            if (!provider.isLoading)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Row(
                  children: [
                    _StatChip(count: provider.counts.todo, label: 'To Do',
                        color: const Color(0xFF6B7280), isDark: isDark),
                    const SizedBox(width: 8),
                    _StatChip(count: provider.counts.inProgress, label: 'In Progress',
                        color: isDark ? MColors.darkPrimary : MColors.primary, isDark: isDark),
                    const SizedBox(width: 8),
                    _StatChip(count: provider.counts.completed, label: 'Done',
                        color: isDark ? MColors.darkSuccess : MColors.success, isDark: isDark),
                  ],
                ),
              ),

            // Filter tabs
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: List.generate(_tabs.length, (i) => Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: GestureDetector(
                      onTap: () {
                        setState(() => _tabIndex = i);
                        provider.loadTasks(status: _statusFilters[i]);
                      },
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
                          onRefresh: () => provider.loadTasks(
                              status: _statusFilters[_tabIndex]),
                          color: isDark ? MColors.darkPrimary : MColors.primary,
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                            itemCount: filtered.length,
                            itemBuilder: (ctx, i) => _TaskTile(
                              task: filtered[i],
                              priorityColor: _priorityColor(filtered[i].priority),
                              onTap: () async {
                                final p = context.read<TaskProvider>();
                                await Navigator.pushNamed(ctx, AppRoutes.taskDetail,
                                    arguments: filtered[i].id);
                                if (mounted) p.loadTasks(status: _statusFilters[_tabIndex]);
                              },
                            ),
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final int count;
  final String label;
  final Color color;
  final bool isDark;
  const _StatChip({required this.count, required this.label,
      required this.color, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$count', style: TextStyle(
              fontSize: 13, fontWeight: FontWeight.w700, color: color)),
          const SizedBox(width: 5),
          Text(label, style: TextStyle(
              fontSize: 11, fontWeight: FontWeight.w500, color: color)),
        ],
      ),
    );
  }
}

class _TaskTile extends StatelessWidget {
  final dynamic task;
  final Color priorityColor;
  final VoidCallback onTap;
  const _TaskTile({required this.task, required this.priorityColor, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final sem = AppTheme.semantics(context);

    return GestureDetector(
      onTap: onTap,
      child: Container(
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
                  color: priorityColor,
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
                            child: Text(task.title,
                                style: TextStyle(
                                  fontSize: 14, fontWeight: FontWeight.w700,
                                  color: isDark ? MColors.darkText : MColors.text,
                                  decoration: task.status == 'completed'
                                      ? TextDecoration.lineThrough : null,
                                )),
                          ),
                          StatusBadge(kind: _taskStatusBadge(task.status), small: true),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                            decoration: BoxDecoration(
                              color: priorityColor.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(task.priority.toUpperCase(),
                                style: TextStyle(
                                    fontSize: 10, fontWeight: FontWeight.w700,
                                    color: priorityColor, letterSpacing: 0.4)),
                          ),
                          if (task.dueDate != null) ...[
                            const SizedBox(width: 10),
                            Icon(Icons.schedule_outlined, size: 12,
                                color: task.isOverdue ? sem.danger
                                    : (isDark ? MColors.darkTextSub : MColors.textSub)),
                            const SizedBox(width: 4),
                            Text(task.dueDate!,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: task.isOverdue ? sem.danger
                                      : (isDark ? MColors.darkTextSub : MColors.textSub),
                                  fontWeight: task.isOverdue ? FontWeight.w600 : FontWeight.normal,
                                )),
                          ],
                          const Spacer(),
                          if (task.commentCount > 0) ...[
                            Icon(Icons.chat_bubble_outline_rounded, size: 12,
                                color: isDark ? MColors.darkTextFaint : MColors.textFaint),
                            const SizedBox(width: 3),
                            Text('${task.commentCount}',
                                style: TextStyle(fontSize: 11,
                                    color: isDark ? MColors.darkTextSub : MColors.textSub)),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

BadgeKind _taskStatusBadge(String status) {
  switch (status) {
    case 'todo': return BadgeKind.todo;
    case 'in_progress': return BadgeKind.inProgress;
    case 'completed': return BadgeKind.done;
    default: return BadgeKind.todo;
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
        children: List.generate(5, (_) => Container(
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
  Widget build(BuildContext context) => Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.task_alt_outlined, size: 56,
          color: AppTheme.semantics(context).textFaint),
      const SizedBox(height: 12),
      Text('No tasks', style: TextStyle(
          color: AppTheme.semantics(context).textSub)),
      const SizedBox(height: 6),
      Text('All caught up!', style: TextStyle(
          fontSize: 12, color: AppTheme.semantics(context).textFaint)),
    ]),
  );
}
