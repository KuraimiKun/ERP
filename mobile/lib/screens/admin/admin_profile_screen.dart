import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../providers/auth_provider.dart';
import 'admin_shell.dart';

class AdminProfileScreen extends StatelessWidget {
  const AdminProfileScreen({super.key});

  Future<void> _logout(BuildContext context) async {
    await context.read<AuthProvider>().logout();
    if (context.mounted) {
      Navigator.pushNamedAndRemoveUntil(
          context, AppRoutes.login, (_) => false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final admin = context.watch<AuthProvider>().admin;
    final sem = AppTheme.semantics(context);
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context)!;

    return AdminShell(
      title: l10n.profile,
      currentIndex: -1,
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: 16),
        children: [
          Center(
            child: Column(
              children: [
                CircleAvatar(
                  radius: 38,
                  backgroundColor: theme.colorScheme.primary,
                  child: Text(
                    admin?.initials ?? '?',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 24,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  admin?.fullName ?? '',
                  style: theme.textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                Text(
                  admin?.email ?? '',
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: sem.textSub),
                ),
                const SizedBox(height: 6),
                if (admin?.role.isNotEmpty == true)
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primary
                          .withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      admin!.role.toUpperCase(),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.primary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          if (admin?.company != null)
            _SectionCard(
              title: l10n.company,
              rows: [
                _InfoRow(l10n.nameField, admin!.company!.name),
                if (admin.company!.nameAr.isNotEmpty)
                  _InfoRow(l10n.arabicName, admin.company!.nameAr),
                _InfoRow(l10n.aiEnabled,
                    admin.company!.aiEnabled ? l10n.yes : l10n.no),
              ],
            ),
          if (admin?.employee != null)
            _SectionCard(
              title: l10n.employeeProfile,
              rows: [
                _InfoRow(l10n.employeeId, admin!.employee!.employeeId),
                _InfoRow(l10n.nameField,
                    '${admin.employee!.firstName} ${admin.employee!.lastName}'.trim()),
                _InfoRow(l10n.email, admin.employee!.email),
                if (admin.employee!.jobTitle.isNotEmpty)
                  _InfoRow(l10n.jobTitle, admin.employee!.jobTitle),
              ],
            ),
          const SizedBox(height: 16),
          ListTile(
            leading: const Icon(Icons.lock_outline),
            title: Text(l10n.changePassword),
            trailing: const Icon(Icons.chevron_right, size: 18),
            onTap: () =>
                Navigator.pushNamed(context, AppRoutes.adminChangePassword),
          ),
          Divider(color: sem.borderSoft),
          ListTile(
            leading: Icon(Icons.logout, color: sem.danger),
            title: Text(l10n.logout, style: TextStyle(color: sem.danger)),
            onTap: () => _logout(context),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  final String title;
  final List<_InfoRow> rows;

  const _SectionCard({required this.title, required this.rows});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: sem.textFaint,
                    ),
              ),
              const SizedBox(height: 8),
              ...rows,
            ],
          ),
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: sem.textFaint),
            ),
          ),
          Expanded(
            child: Text(
              value.isEmpty ? '—' : value,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}
