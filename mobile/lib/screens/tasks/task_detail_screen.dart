import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../models/task.dart';
import '../../providers/task_provider.dart';
import '../../widgets/status_badge.dart';

class TaskDetailScreen extends StatefulWidget {
  final int taskId;
  const TaskDetailScreen({super.key, required this.taskId});

  @override
  State<TaskDetailScreen> createState() => _TaskDetailScreenState();
}

class _TaskDetailScreenState extends State<TaskDetailScreen> {
  final _commentCtrl = TextEditingController();
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TaskProvider>().loadTaskDetail(widget.taskId);
    });
  }

  @override
  void dispose() {
    _commentCtrl.dispose();
    super.dispose();
  }

  Color _priorityColor(String priority) {
    switch (priority) {
      case 'urgent':
      case 'high': return const Color(0xFFEF4444);
      case 'medium': return const Color(0xFFF59E0B);
      case 'low': return const Color(0xFF3B82F6);
      default: return const Color(0xFF6B7280);
    }
  }

  Future<void> _sendComment() async {
    final text = _commentCtrl.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() => _sending = true);
    final ok = await context.read<TaskProvider>().addComment(widget.taskId, text);
    if (!mounted) return;
    setState(() => _sending = false);
    if (ok) _commentCtrl.clear();
  }

  void _showStatusSheet(BuildContext context, Task task, TaskProvider provider) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        decoration: BoxDecoration(
          color: isDark ? MColors.darkSurface : MColors.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 36, height: 4,
              decoration: BoxDecoration(
                color: isDark ? MColors.darkBorder : MColors.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 16),
            Text('Change Status', style: TextStyle(
                fontSize: 15, fontWeight: FontWeight.w700,
                color: isDark ? MColors.darkText : MColors.text)),
            const SizedBox(height: 16),
            ...provider.statuses.map((s) {
              final isCurrent = s.value == task.status;
              final badge = _taskStatusBadge(s.value);
              return GestureDetector(
                onTap: () async {
                  Navigator.pop(context);
                  await provider.updateStatus(widget.taskId, s.value);
                },
                child: Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: isCurrent
                        ? (isDark ? MColors.darkPrimarySoft : MColors.primarySoft)
                        : (isDark ? MColors.darkSurfaceAlt : MColors.surfaceAlt),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: isCurrent
                          ? (isDark ? MColors.darkPrimary : MColors.primary)
                          : Colors.transparent,
                      width: 1.5,
                    ),
                  ),
                  child: Row(
                    children: [
                      StatusBadge(kind: badge),
                      const SizedBox(width: 10),
                      Text(s.label, style: TextStyle(
                          fontSize: 14, fontWeight: FontWeight.w500,
                          color: isDark ? MColors.darkText : MColors.text)),
                      const Spacer(),
                      if (isCurrent) Icon(Icons.check_rounded, size: 16,
                          color: isDark ? MColors.darkPrimary : MColors.primary),
                    ],
                  ),
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TaskProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final task = provider.currentTask;

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
                    onTap: () => Navigator.pop(context),
                    child: Icon(Icons.arrow_back_ios_new_rounded, size: 20,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const Spacer(),
                  Text('Task Detail', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),
            Expanded(
              child: provider.isLoading
                  ? const _Shimmer()
                  : task == null
                      ? _Error(isDark: isDark)
                      : _DetailBody(
                          task: task,
                          provider: provider,
                          isDark: isDark,
                          priorityColor: _priorityColor(task.priority),
                          onStatusTap: () => _showStatusSheet(context, task, provider),
                        ),
            ),
            // Comment bar
            if (!provider.isLoading && task != null)
              Container(
                padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
                decoration: BoxDecoration(
                  color: isDark ? MColors.darkSurface : MColors.surface,
                  border: Border(
                    top: BorderSide(
                        color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
                  ),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Container(
                        height: 42,
                        decoration: BoxDecoration(
                          color: isDark ? MColors.darkSurfaceAlt : MColors.surfaceAlt,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                              color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
                        ),
                        child: TextField(
                          controller: _commentCtrl,
                          style: TextStyle(
                              fontSize: 13,
                              color: isDark ? MColors.darkText : MColors.text),
                          decoration: InputDecoration(
                            hintText: 'Add a comment…',
                            hintStyle: TextStyle(
                                fontSize: 13,
                                color: isDark ? MColors.darkTextFaint : MColors.textFaint),
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(
                                horizontal: 14, vertical: 11),
                          ),
                          textInputAction: TextInputAction.send,
                          onSubmitted: (_) => _sendComment(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    GestureDetector(
                      onTap: _sendComment,
                      child: Container(
                        width: 42, height: 42,
                        decoration: BoxDecoration(
                          color: isDark ? MColors.darkPrimary : MColors.primary,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: _sending
                            ? const Padding(
                                padding: EdgeInsets.all(11),
                                child: CircularProgressIndicator(
                                    strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.send_rounded, size: 18, color: Colors.white),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _DetailBody extends StatelessWidget {
  final Task task;
  final TaskProvider provider;
  final bool isDark;
  final Color priorityColor;
  final VoidCallback onStatusTap;
  const _DetailBody({
    required this.task, required this.provider, required this.isDark,
    required this.priorityColor, required this.onStatusTap,
  });

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
      children: [
        // Info card
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: isDark ? MColors.darkSurface : MColors.surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
                color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(task.title, style: TextStyle(
                fontSize: 17, fontWeight: FontWeight.w700,
                color: isDark ? MColors.darkText : MColors.text,
                letterSpacing: -0.3,
                decoration: task.status == 'completed' ? TextDecoration.lineThrough : null,
              )),
              const SizedBox(height: 12),
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: priorityColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(7),
                    ),
                    child: Text(task.priority.toUpperCase(),
                        style: TextStyle(
                            fontSize: 11, fontWeight: FontWeight.w700,
                            color: priorityColor, letterSpacing: 0.5)),
                  ),
                  const SizedBox(width: 10),
                  GestureDetector(
                    onTap: onStatusTap,
                    child: Row(children: [
                      StatusBadge(kind: _taskStatusBadge(task.status)),
                      const SizedBox(width: 4),
                      Icon(Icons.expand_more_rounded, size: 14,
                          color: isDark ? MColors.darkTextSub : MColors.textSub),
                    ]),
                  ),
                ],
              ),
              if (task.dueDate != null) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    Icon(Icons.schedule_outlined, size: 14,
                        color: task.isOverdue ? sem.danger
                            : (isDark ? MColors.darkTextSub : MColors.textSub)),
                    const SizedBox(width: 6),
                    Text('Due ${task.dueDate!}', style: TextStyle(
                      fontSize: 12,
                      color: task.isOverdue ? sem.danger
                          : (isDark ? MColors.darkTextSub : MColors.textSub),
                      fontWeight: task.isOverdue ? FontWeight.w600 : FontWeight.normal,
                    )),
                    if (task.isOverdue) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: sem.dangerContainer,
                          borderRadius: BorderRadius.circular(5),
                        ),
                        child: Text('Overdue', style: TextStyle(
                            fontSize: 10, fontWeight: FontWeight.w700, color: sem.danger)),
                      ),
                    ],
                  ],
                ),
              ],
            ],
          ),
        ),

        // Description
        if (task.description.isNotEmpty) ...[
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: isDark ? MColors.darkSurface : MColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                  color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Description', style: TextStyle(
                    fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.2,
                    color: isDark ? MColors.darkTextSub : MColors.textSub)),
                const SizedBox(height: 8),
                Text(task.description, style: TextStyle(
                    fontSize: 14, height: 1.5,
                    color: isDark ? MColors.darkTextMid : MColors.textMid)),
              ],
            ),
          ),
        ],

        const SizedBox(height: 14),

        // Comments header
        Row(
          children: [
            Text('Comments', style: TextStyle(
                fontSize: 13, fontWeight: FontWeight.w700,
                color: isDark ? MColors.darkText : MColors.text)),
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
                borderRadius: BorderRadius.circular(99),
              ),
              child: Text('${provider.comments.length}', style: TextStyle(
                  fontSize: 11, fontWeight: FontWeight.w700,
                  color: isDark ? MColors.darkPrimary : MColors.primary)),
            ),
          ],
        ),

        const SizedBox(height: 10),

        if (provider.comments.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child: Center(
              child: Text('No comments yet',
                  style: TextStyle(
                      fontSize: 13,
                      color: isDark ? MColors.darkTextFaint : MColors.textFaint)),
            ),
          )
        else
          ...provider.comments.map((c) => _CommentTile(comment: c, isDark: isDark)),
      ],
    );
  }
}

class _CommentTile extends StatelessWidget {
  final TaskComment comment;
  final bool isDark;
  const _CommentTile({required this.comment, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final initials = comment.author.isNotEmpty
        ? comment.author.trim().split(' ').map((w) => w[0]).take(2).join().toUpperCase()
        : '?';
    final dateStr = comment.createdAt.contains('T')
        ? comment.createdAt.split('T')[0] : comment.createdAt;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 32, height: 32,
            decoration: BoxDecoration(
              color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
              shape: BoxShape.circle,
            ),
            child: Center(child: Text(initials, style: TextStyle(
                fontSize: 11, fontWeight: FontWeight.w700,
                color: isDark ? MColors.darkPrimary : MColors.primary))),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isDark ? MColors.darkSurface : MColors.surface,
                borderRadius: const BorderRadius.only(
                  topRight: Radius.circular(14),
                  bottomLeft: Radius.circular(14),
                  bottomRight: Radius.circular(14),
                ),
                border: Border.all(
                    color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(comment.author, style: TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w700,
                          color: isDark ? MColors.darkText : MColors.text))),
                      Text(dateStr, style: TextStyle(
                          fontSize: 10,
                          color: isDark ? MColors.darkTextFaint : MColors.textFaint)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(comment.content, style: TextStyle(
                      fontSize: 13, height: 1.4,
                      color: isDark ? MColors.darkTextMid : MColors.textMid)),
                ],
              ),
            ),
          ),
        ],
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
      child: Column(children: [
        Container(height: 120, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(18))),
        const SizedBox(height: 12),
        Container(height: 80, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(16))),
        const SizedBox(height: 12),
        Container(height: 60, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(14))),
        const SizedBox(height: 12),
        Container(height: 60, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(14))),
      ]),
    );
  }
}

class _Error extends StatelessWidget {
  final bool isDark;
  const _Error({required this.isDark});
  @override
  Widget build(BuildContext context) => Center(
    child: Text('Could not load task',
        style: TextStyle(color: AppTheme.semantics(context).textSub)),
  );
}
