import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../config/routes.dart';
import '../config/theme.dart';
import '../providers/auth_provider.dart';
import '../providers/locale_provider.dart';
import '../providers/theme_provider.dart';

class AppDrawer extends StatelessWidget {
  const AppDrawer({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final auth = context.watch<AuthProvider>();
    final employee = auth.employee;
    final perms = auth.permissions;
    final locale = context.watch<LocaleProvider>();
    final themeProvider = context.watch<ThemeProvider>();

    return Drawer(
      child: Column(
        children: [
          _DrawerHeader(
            name: locale.locale.languageCode == 'ar'
                ? (employee?.fullNameAr ?? '')
                : (employee?.fullName ?? ''),
            email: employee?.email ?? '',
            initials: employee?.firstName.isNotEmpty == true
                ? employee!.firstName[0].toUpperCase()
                : '?',
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 8),
              children: [
                _DrawerItem(
                  icon: Icons.dashboard_outlined,
                  title: l10n.dashboard,
                  route: AppRoutes.dashboard,
                ),
                if (perms.canViewAttendance)
                  _DrawerItem(
                    icon: Icons.access_time_outlined,
                    title: l10n.attendance,
                    route: AppRoutes.attendance,
                  ),
                if (perms.canScanQr)
                  _DrawerItem(
                    icon: Icons.qr_code_scanner_outlined,
                    title: l10n.scanQR,
                    route: AppRoutes.qrScanner,
                  ),
                if (perms.canManageLeaves)
                  _DrawerItem(
                    icon: Icons.event_note_outlined,
                    title: l10n.leaveRequests,
                    route: AppRoutes.leaves,
                  ),
                if (perms.canViewPayslips)
                  _DrawerItem(
                    icon: Icons.receipt_long_outlined,
                    title: l10n.payslips,
                    route: AppRoutes.payslips,
                  ),
                if (perms.canViewTasks)
                  _DrawerItem(
                    icon: Icons.task_alt_outlined,
                    title: l10n.tasks,
                    route: AppRoutes.tasks,
                  ),
                if (perms.canUsePOS)
                  _DrawerItem(
                    icon: Icons.point_of_sale_outlined,
                    title: l10n.pos,
                    route: AppRoutes.posTerminals,
                  ),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: Divider(height: 1),
                ),
                _DrawerItem(
                  icon: Icons.person_outlined,
                  title: l10n.profile,
                  route: AppRoutes.profile,
                ),
                _DrawerItem(
                  icon: Icons.notifications_outlined,
                  title: l10n.notifications,
                  route: AppRoutes.notifications,
                ),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: Divider(height: 1),
                ),

                // Language switcher
                ExpansionTile(
                  leading: const Icon(Icons.language),
                  title: Text(l10n.language),
                  subtitle: Text(locale.languageName,
                      style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.semantics(context).textMuted)),
                  children: [
                    _LanguageTile(
                      label: 'العربية',
                      locale: const Locale('ar'),
                      current: locale.locale,
                    ),
                    _LanguageTile(
                      label: 'English',
                      locale: const Locale('en'),
                      current: locale.locale,
                    ),
                    _LanguageTile(
                      label: 'Bahasa Indonesia',
                      locale: const Locale('id'),
                      current: locale.locale,
                    ),
                  ],
                ),

                // Dark mode toggle
                ListTile(
                  leading: Icon(
                    themeProvider.isDark
                        ? Icons.dark_mode_outlined
                        : Icons.light_mode_outlined,
                  ),
                  title: Text(l10n.darkMode),
                  trailing: Switch.adaptive(
                    value: themeProvider.isDark,
                    onChanged: (_) => themeProvider.toggle(),
                  ),
                ),

                // Logout
                ListTile(
                  leading: Icon(Icons.logout,
                      color: Theme.of(context).colorScheme.error),
                  title: Text(l10n.logout,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error)),
                  onTap: () => _confirmLogout(context, l10n),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _confirmLogout(BuildContext context, AppLocalizations l10n) {
    final cs = Theme.of(context).colorScheme;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.logout),
        content: Text(l10n.logoutConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(l10n.cancel),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              context.read<AuthProvider>().logout();
              Navigator.pushNamedAndRemoveUntil(
                context,
                AppRoutes.login,
                (_) => false,
              );
            },
            child:
                Text(l10n.logout, style: TextStyle(color: cs.error)),
          ),
        ],
      ),
    );
  }
}

// ── Gradient drawer header ────────────────────────────────────────────────────

class _DrawerHeader extends StatelessWidget {
  final String name;
  final String email;
  final String initials;

  const _DrawerHeader({
    required this.name,
    required this.email,
    required this.initials,
  });

  @override
  Widget build(BuildContext context) {
    final topPadding = MediaQuery.of(context).padding.top;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.fromLTRB(20, topPadding + 20, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [MColors.primary, const Color(0xFF4338CA), MColors.primaryDeep],
        ),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 28,
            backgroundColor: Colors.white.withValues(alpha: 0.2),
            child: Text(
              initials,
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                    color: Colors.white,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  email,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.white.withValues(alpha: 0.75),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Drawer item with filled active highlight ──────────────────────────────────

class _DrawerItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final String route;

  const _DrawerItem({
    required this.icon,
    required this.title,
    required this.route,
  });

  @override
  Widget build(BuildContext context) {
    final current = ModalRoute.of(context)?.settings.name;
    final isActive = current == route;
    final cs = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
      child: Material(
        color: isActive ? cs.primaryContainer : Colors.transparent,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () {
            Navigator.pop(context);
            if (!isActive) {
              Navigator.pushReplacementNamed(context, route);
            }
          },
          child: Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            child: Row(
              children: [
                Icon(icon,
                    size: 22,
                    color: isActive ? cs.onPrimaryContainer : null),
                const SizedBox(width: 14),
                Text(
                  title,
                  style: TextStyle(
                    fontWeight:
                        isActive ? FontWeight.w700 : FontWeight.normal,
                    color: isActive ? cs.onPrimaryContainer : null,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Language tile ─────────────────────────────────────────────────────────────

class _LanguageTile extends StatelessWidget {
  final String label;
  final Locale locale;
  final Locale current;

  const _LanguageTile({
    required this.label,
    required this.locale,
    required this.current,
  });

  @override
  Widget build(BuildContext context) {
    final isSelected = locale == current;
    final cs = Theme.of(context).colorScheme;
    return ListTile(
      contentPadding: const EdgeInsetsDirectional.only(start: 72, end: 16),
      title: Text(
        label,
        style: TextStyle(
          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
          color: isSelected ? cs.primary : null,
        ),
      ),
      trailing: isSelected
          ? Icon(Icons.check_circle, size: 18, color: cs.primary)
          : null,
      onTap: () => context.read<LocaleProvider>().setLocale(locale),
    );
  }
}
