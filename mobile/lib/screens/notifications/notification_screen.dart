import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../models/notification_model.dart';
import '../../providers/notification_provider.dart';

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
    final provider = context.watch<NotificationProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;

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
                  Text('Notifications', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  if (provider.unreadCount > 0)
                    GestureDetector(
                      onTap: () => provider.markAllRead(),
                      child: Text('Mark all read', style: TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w600,
                          color: isDark ? MColors.darkPrimary : MColors.primary)),
                    )
                  else
                    const SizedBox(width: 72),
                ],
              ),
            ),
            if (provider.unreadCount > 0)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                  decoration: BoxDecoration(
                    color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 7, height: 7,
                        decoration: BoxDecoration(
                          color: isDark ? MColors.darkPrimary : MColors.primary,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text('${provider.unreadCount} unread',
                          style: TextStyle(
                              fontSize: 12, fontWeight: FontWeight.w600,
                              color: isDark ? MColors.darkPrimary : MColors.primary)),
                    ],
                  ),
                ),
              ),
            Expanded(
              child: provider.isLoading
                  ? const _Shimmer()
                  : provider.notifications.isEmpty
                      ? const _Empty()
                      : RefreshIndicator(
                          onRefresh: () => provider.loadNotifications(),
                          color: isDark ? MColors.darkPrimary : MColors.primary,
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                            itemCount: provider.notifications.length,
                            itemBuilder: (ctx, i) => _NotificationTile(
                              notification: provider.notifications[i],
                              isDark: isDark,
                              onTap: () {
                                if (!provider.notifications[i].isRead) {
                                  provider.markRead([provider.notifications[i].id]);
                                }
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

class _NotificationTile extends StatelessWidget {
  final AppNotification notification;
  final bool isDark;
  final VoidCallback onTap;
  const _NotificationTile({required this.notification, required this.isDark,
      required this.onTap});

  IconData _icon(String type) {
    switch (type) {
      case 'leave': return Icons.event_note_outlined;
      case 'attendance': return Icons.access_time_rounded;
      case 'task': return Icons.task_alt_outlined;
      case 'payroll': return Icons.receipt_long_outlined;
      default: return Icons.notifications_outlined;
    }
  }

  Color _iconColor(String type, bool isDark) {
    switch (type) {
      case 'leave': return isDark ? MColors.darkSuccess : MColors.success;
      case 'attendance': return isDark ? MColors.darkPrimary : MColors.primary;
      case 'task': return const Color(0xFF8B5CF6);
      case 'payroll': return isDark ? MColors.darkAccent : MColors.accent;
      default: return isDark ? MColors.darkPrimary : MColors.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isUnread = !notification.isRead;
    final iconColor = _iconColor(notification.type, isDark);
    final dateStr = notification.createdAt.contains('T')
        ? notification.createdAt.split('T')[0] : notification.createdAt;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isUnread
              ? (isDark ? MColors.darkPrimarySoft : MColors.primarySoft).withValues(alpha: 0.6)
              : (isDark ? MColors.darkSurface : MColors.surface),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isUnread
                ? (isDark ? MColors.darkPrimary : MColors.primary).withValues(alpha: 0.3)
                : (isDark ? MColors.darkBorder : MColors.border),
            width: isUnread ? 1 : 0.5,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 38, height: 38,
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(_icon(notification.type), size: 18, color: iconColor),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(notification.title, style: TextStyle(
                          fontSize: 13, fontWeight: isUnread ? FontWeight.w700 : FontWeight.w600,
                          color: isDark ? MColors.darkText : MColors.text))),
                      if (isUnread)
                        Container(
                          width: 7, height: 7,
                          decoration: BoxDecoration(
                            color: isDark ? MColors.darkPrimary : MColors.primary,
                            shape: BoxShape.circle,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(notification.message,
                      maxLines: 2, overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          fontSize: 12, height: 1.4,
                          color: isDark ? MColors.darkTextSub : MColors.textSub)),
                  const SizedBox(height: 4),
                  Text(dateStr, style: TextStyle(
                      fontSize: 11,
                      color: isDark ? MColors.darkTextFaint : MColors.textFaint)),
                ],
              ),
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
    final c = Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF1F2937) : const Color(0xFFE2E8F0);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: List.generate(6, (_) => Container(
          height: 72, margin: const EdgeInsets.only(bottom: 8),
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
      Icon(Icons.notifications_none_outlined, size: 56,
          color: AppTheme.semantics(context).textFaint),
      const SizedBox(height: 12),
      Text('No notifications',
          style: TextStyle(color: AppTheme.semantics(context).textSub)),
      const SizedBox(height: 6),
      Text("You're all caught up",
          style: TextStyle(fontSize: 12, color: AppTheme.semantics(context).textFaint)),
    ]),
  );
}
