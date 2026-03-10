import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/notification_provider.dart';
import '../../widgets/loading_indicator.dart';
import '../../widgets/empty_state.dart';

class NotificationScreen extends StatefulWidget {
  const NotificationScreen({super.key});

  @override
  State<NotificationScreen> createState() => _NotificationScreenState();
}

class _NotificationScreenState extends State<NotificationScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationProvider>().loadNotifications();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<NotificationProvider>();

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.notifications),
        actions: [
          if (provider.unreadCount > 0)
            TextButton(
              onPressed: () => provider.markAllRead(),
              child: Text(l10n.markAllRead,
                  style: TextStyle(color: Theme.of(context).colorScheme.onPrimary)),
            ),
        ],
      ),
      body: provider.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : RefreshIndicator(
              onRefresh: () => provider.loadNotifications(),
              child: provider.notifications.isEmpty
                  ? EmptyState(
                      icon: Icons.notifications_none,
                      message: l10n.noNotifications,
                    )
                  : ListView.builder(
                      itemCount: provider.notifications.length,
                      itemBuilder: (context, index) {
                        final n = provider.notifications[index];
                        return Card(
                          margin: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 4),
                          color: n.isRead ? null : Theme.of(context).colorScheme.primaryContainer,
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: n.isRead
                                  ? Theme.of(context).colorScheme.surfaceContainerLow
                                  : Theme.of(context).primaryColor,
                              child: Icon(
                                _notificationIcon(n.type),
                                color:
                                    n.isRead ? AppTheme.semantics(context).textMuted : Theme.of(context).colorScheme.onPrimaryContainer,
                                size: 20,
                              ),
                            ),
                            title: Text(
                              n.title,
                              style: TextStyle(
                                fontWeight: n.isRead
                                    ? FontWeight.normal
                                    : FontWeight.bold,
                              ),
                            ),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(n.message, maxLines: 2,
                                    overflow: TextOverflow.ellipsis),
                                const SizedBox(height: 4),
                                Text(
                                  n.createdAt.split('T')[0],
                                  style: TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.semantics(context).textMuted),
                                ),
                              ],
                            ),
                            onTap: () {
                              if (!n.isRead) {
                                provider.markRead([n.id]);
                              }
                            },
                          ),
                        );
                      },
                    ),
            ),
    );
  }

  IconData _notificationIcon(String type) {
    switch (type) {
      case 'leave':
        return Icons.event_note;
      case 'attendance':
        return Icons.access_time;
      case 'task':
        return Icons.task_alt;
      case 'payroll':
        return Icons.receipt_long;
      default:
        return Icons.notifications;
    }
  }
}
