import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/api_config.dart';
import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../providers/admin_list_provider.dart';
import '../../services/admin_api_service.dart';
import '../../services/api_service.dart';
import 'admin_shell.dart';

class AdminNotificationsScreen extends StatefulWidget {
  const AdminNotificationsScreen({super.key});

  @override
  State<AdminNotificationsScreen> createState() =>
      _AdminNotificationsScreenState();
}

class _AdminNotificationsScreenState extends State<AdminNotificationsScreen> {
  late final AdminListProvider _provider;
  bool _unreadOnly = false;

  @override
  void initState() {
    super.initState();
    _provider = AdminListProvider(
      AdminApiService(context.read<ApiService>()),
      endpoint: ApiConfig.adminNotifications,
    );
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _provider.load(reset: true),
    );
  }

  @override
  void dispose() {
    _provider.dispose();
    super.dispose();
  }

  Future<void> _toggleUnread() async {
    setState(() => _unreadOnly = !_unreadOnly);
    await _provider.setBaseQuery(_unreadOnly ? {'unread': 1} : {});
  }

  Future<void> _markAllRead() async {
    try {
      final api = AdminApiService(context.read<ApiService>());
      await api.collectionAction(ApiConfig.adminNotifications, 'read-all');
      await _provider.refresh();
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('✔')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(AdminApiService.extractError(e))));
    }
  }

  Future<void> _markOneRead(int id) async {
    try {
      final api = AdminApiService(context.read<ApiService>());
      await api.collectionAction(
        ApiConfig.adminNotifications,
        'read',
        data: {
          'ids': [id],
        },
      );
      await _provider.refresh();
    } catch (_) {
      // non-fatal
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return ChangeNotifierProvider.value(
      value: _provider,
      child: Consumer<AdminListProvider>(
        builder: (context, p, _) => AdminShell(
          title: l10n.notifications,
          currentIndex: -1,
          actions: [
            IconButton(
              tooltip: _unreadOnly ? l10n.all : l10n.pending,
              icon: Icon(
                _unreadOnly ? Icons.filter_alt : Icons.filter_alt_outlined,
              ),
              onPressed: _toggleUnread,
            ),
            IconButton(
              tooltip: l10n.markAllRead,
              icon: const Icon(Icons.done_all),
              onPressed: _markAllRead,
            ),
          ],
          body: _buildBody(context, p),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context, AdminListProvider p) {
    final sem = AppTheme.semantics(context);
    if (p.isLoading && p.items.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (p.error != null && p.items.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 56, color: sem.danger),
            const SizedBox(height: 12),
            Text(p.error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () => p.load(reset: true),
              icon: const Icon(Icons.refresh),
              label: Text(AppLocalizations.of(context)?.retry ?? 'Retry'),
            ),
          ],
        ),
      );
    }
    if (p.items.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.notifications_off_outlined,
              size: 48,
              color: sem.textFaint,
            ),
            const SizedBox(height: 12),
            Text(
              AppLocalizations.of(context)?.noNotifications ??
                  (_unreadOnly
                      ? 'No unread notifications'
                      : 'No notifications'),
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: sem.textMuted),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: p.refresh,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: p.items.length,
        separatorBuilder: (_, __) => Divider(height: 1, color: sem.borderSoft),
        itemBuilder: (ctx, i) {
          final n = p.items[i];
          final isRead = n['is_read'] == true;
          return ListTile(
            onTap: () => isRead ? null : _markOneRead((n['id'] as num).toInt()),
            leading: CircleAvatar(
              backgroundColor: isRead
                  ? sem.borderSoft
                  : Theme.of(
                      context,
                    ).colorScheme.primary.withValues(alpha: 0.15),
              child: Icon(
                _iconFor((n['notification_type'] ?? '').toString()),
                color: isRead
                    ? sem.textFaint
                    : Theme.of(context).colorScheme.primary,
                size: 20,
              ),
            ),
            title: Text(
              (n['title'] ?? '—').toString(),
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                fontWeight: isRead ? FontWeight.w500 : FontWeight.w700,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(
              (n['message'] ?? '').toString(),
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: sem.textSub),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: isRead
                ? null
                : Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primary,
                      shape: BoxShape.circle,
                    ),
                  ),
          );
        },
      ),
    );
  }

  IconData _iconFor(String type) {
    switch (type) {
      case 'leave_request':
      case 'leave_approved':
      case 'leave_rejected':
        return Icons.beach_access_outlined;
      case 'expense_submitted':
      case 'expense_approved':
      case 'expense_rejected':
        return Icons.receipt_long_outlined;
      case 'task_assigned':
      case 'task_completed':
        return Icons.check_box_outlined;
      case 'invoice_paid':
      case 'payment_received':
        return Icons.payments_outlined;
      default:
        return Icons.notifications_outlined;
    }
  }
}
