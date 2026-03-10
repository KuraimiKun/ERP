import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/task_provider.dart';
import '../../widgets/loading_indicator.dart';

class TaskDetailScreen extends StatefulWidget {
  final int taskId;

  const TaskDetailScreen({super.key, required this.taskId});

  @override
  State<TaskDetailScreen> createState() => _TaskDetailScreenState();
}

class _TaskDetailScreenState extends State<TaskDetailScreen> {
  final _commentController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TaskProvider>().loadTaskDetail(widget.taskId);
    });
  }

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<TaskProvider>();
    final task = provider.currentTask;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.taskDetail)),
      body: provider.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : task == null
              ? Center(child: Text(l10n.error))
              : Column(
                  children: [
                    Expanded(
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Title
                            Text(
                              task.title,
                              style: Theme.of(context)
                                  .textTheme
                                  .titleLarge
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 12),

                            // Status & Priority
                            Row(
                              children: [
                                // Status dropdown
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 4),
                                  decoration: BoxDecoration(
                                    border: Border.all(
                                        color: Theme.of(context).colorScheme.outlineVariant),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: DropdownButton<String>(
                                    value: task.status,
                                    underline: const SizedBox(),
                                    isDense: true,
                                    items: provider.statuses
                                        .map((s) => DropdownMenuItem(
                                              value: s.value,
                                              child: Text(s.label),
                                            ))
                                        .toList(),
                                    onChanged: (v) {
                                      if (v != null) {
                                        provider.updateStatus(
                                            widget.taskId, v);
                                      }
                                    },
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: _priorityColor(context, task.priority)
                                        .withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    task.priority.toUpperCase(),
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color:
                                          _priorityColor(context, task.priority),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),

                            // Due date
                            if (task.dueDate != null)
                              Row(
                                children: [
                                  Icon(Icons.schedule,
                                      size: 16,
                                      color: task.isOverdue
                                          ? AppTheme.semantics(context).danger
                                          : AppTheme.semantics(context).textMuted),
                                  const SizedBox(width: 4),
                                  Text(
                                    '${l10n.dueDate}: ${task.dueDate}',
                                    style: TextStyle(
                                      color: task.isOverdue
                                          ? AppTheme.semantics(context).danger
                                          : AppTheme.semantics(context).textMuted,
                                    ),
                                  ),
                                ],
                              ),
                            const SizedBox(height: 16),

                            // Description
                            if (task.description.isNotEmpty) ...[
                              Text(
                                task.description,
                                style: Theme.of(context).textTheme.bodyMedium,
                              ),
                              const SizedBox(height: 16),
                            ],

                            // Comments
                            const Divider(),
                            Text(
                              '${l10n.comments} (${provider.comments.length})',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 8),
                            ...provider.comments.map(
                              (c) => Padding(
                                padding:
                                    const EdgeInsets.only(bottom: 12),
                                child: Row(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  children: [
                                    CircleAvatar(
                                      radius: 16,
                                      child: Text(
                                        c.author.isNotEmpty
                                            ? c.author[0].toUpperCase()
                                            : '?',
                                        style:
                                            const TextStyle(fontSize: 14),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            children: [
                                              Text(c.author,
                                                  style: const TextStyle(
                                                      fontWeight:
                                                          FontWeight
                                                              .w600,
                                                      fontSize: 13)),
                                              const SizedBox(width: 8),
                                              Text(
                                                c.createdAt.split('T')[0],
                                                style: TextStyle(
                                                    fontSize: 11,
                                                    color:
                                                        AppTheme.semantics(context).textMuted),
                                              ),
                                            ],
                                          ),
                                          const SizedBox(height: 2),
                                          Text(c.content),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                    // Comment input
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.surface,
                        border: Border(
                          top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
                        ),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _commentController,
                              decoration: InputDecoration(
                                hintText: l10n.addComment,
                                isDense: true,
                                contentPadding: const EdgeInsets.symmetric(
                                    horizontal: 12, vertical: 10),
                              ),
                              textInputAction: TextInputAction.send,
                              onSubmitted: (_) => _sendComment(),
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton(
                            icon: const Icon(Icons.send),
                            color: Theme.of(context).primaryColor,
                            onPressed: _sendComment,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
    );
  }

  Future<void> _sendComment() async {
    final text = _commentController.text.trim();
    if (text.isEmpty) return;

    final success = await context
        .read<TaskProvider>()
        .addComment(widget.taskId, text);
    if (success) _commentController.clear();
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
}
