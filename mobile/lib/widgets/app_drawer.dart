import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../config/routes.dart';
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
    final cs = Theme.of(context).colorScheme;

    return Drawer(
      child: Column(
        children: [
          UserAccountsDrawerHeader(
            decoration: BoxDecoration(
              color: cs.primary,
            ),
            accountName: Text(
              locale.locale.languageCode == 'ar'
                  ? (employee?.fullNameAr ?? '')
                  : (employee?.fullName ?? ''),
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            accountEmail: Text(employee?.email ?? ''),
            currentAccountPicture: CircleAvatar(
              backgroundColor: cs.onPrimary,
              child: Text(
                employee?.firstName.isNotEmpty == true
                    ? employee!.firstName[0].toUpperCase()
                    : '?',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: cs.primary,
                ),
              ),
            ),
          ),
          Expanded(
            child: ListView(
              padding: EdgeInsets.zero,
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
                const Divider(),
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
                const Divider(),
                // Language switcher
                ExpansionTile(
                  leading: const Icon(Icons.language),
                  title: Text(locale.languageName),
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
                ListTile(
                  leading: Icon(Icons.logout, color: cs.error),
                  title: Text(l10n.logout,
                      style: TextStyle(color: cs.error)),
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
            child: Text(l10n.logout,
                style: TextStyle(color: cs.error)),
          ),
        ],
      ),
    );
  }
}

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

    return ListTile(
      leading: Icon(icon,
          color: isActive ? cs.primary : null),
      title: Text(
        title,
        style: TextStyle(
          fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
          color: isActive ? cs.primary : null,
        ),
      ),
      selected: isActive,
      onTap: () {
        Navigator.pop(context); // Close drawer
        if (!isActive) {
          Navigator.pushReplacementNamed(context, route);
        }
      },
    );
  }
}

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
      contentPadding: const EdgeInsetsDirectional.only(start: 72),
      title: Text(
        label,
        style: TextStyle(
          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
          color: isSelected ? cs.primary : null,
        ),
      ),
      trailing: isSelected
          ? Icon(Icons.check, color: cs.primary)
          : null,
      onTap: () {
        context.read<LocaleProvider>().setLocale(locale);
      },
    );
  }
}
