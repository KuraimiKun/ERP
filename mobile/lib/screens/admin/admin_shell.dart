import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/admin_sections.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../providers/auth_provider.dart';
import '../../providers/locale_provider.dart';
import '../../providers/theme_provider.dart';

/// Responsive shell for admin-portal screens.
///
/// - **Phone** (width < 720): AppBar + Drawer.
/// - **Tablet / desktop** (width ≥ 720): persistent NavigationRail on the side.
///
/// Navigation items are declared statically — v1 scope is Dashboard only
/// plus Profile/Logout actions. Additional items will plug in here without
/// touching individual screens.
class AdminShell extends StatelessWidget {
  final String title;
  final Widget body;
  final int currentIndex;
  final List<Widget>? actions;
  final FloatingActionButton? floatingActionButton;

  const AdminShell({
    super.key,
    required this.title,
    required this.body,
    this.currentIndex = 0,
    this.actions,
    this.floatingActionButton,
  });

  static List<_AdminNavItem> _buildNavItems(AppLocalizations l10n) => [
    _AdminNavItem(
      icon: Icons.dashboard_outlined,
      selectedIcon: Icons.dashboard,
      label: l10n.dashboard,
      route: AppRoutes.adminDashboard,
    ),
    _AdminNavItem(
      icon: Icons.task_alt_outlined,
      selectedIcon: Icons.task_alt,
      label: l10n.approvals,
      route: AppRoutes.adminApprovals,
    ),
    _AdminNavItem(
      icon: Icons.notifications_outlined,
      selectedIcon: Icons.notifications,
      label: l10n.notifications,
      route: AppRoutes.adminNotifications,
    ),
    _AdminNavItem(
      icon: Icons.search,
      selectedIcon: Icons.search,
      label: l10n.search,
      route: AppRoutes.adminSearch,
    ),
    _AdminNavItem(
      icon: Icons.insights_outlined,
      selectedIcon: Icons.insights,
      label: l10n.reports,
      route: AppRoutes.adminReports,
    ),
    _AdminNavItem(
      icon: Icons.person_outline,
      selectedIcon: Icons.person,
      label: l10n.profile,
      route: AppRoutes.adminProfile,
    ),
  ];

  void _onNavTap(BuildContext context, List<_AdminNavItem> items, int index) {
    final item = items[index];
    if (index == currentIndex) return;
    Navigator.pushReplacementNamed(context, item.route);
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width >= 720;
    final l10n = AppLocalizations.of(context)!;
    final navItems = _buildNavItems(l10n);

    if (isWide) {
      return _WideLayout(
        title: title,
        body: body,
        currentIndex: currentIndex,
        navItems: navItems,
        onNavTap: (i) => _onNavTap(context, navItems, i),
        actions: actions,
        floatingActionButton: floatingActionButton,
      );
    }

    return _NarrowLayout(
      title: title,
      body: body,
      currentIndex: currentIndex,
      navItems: navItems,
      onNavTap: (i) => _onNavTap(context, navItems, i),
      actions: actions,
      floatingActionButton: floatingActionButton,
    );
  }
}

class _AdminNavItem {
  final IconData icon;
  final IconData selectedIcon;
  final String label;
  final String route;

  const _AdminNavItem({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    required this.route,
  });
}

// ──────────────────────────────────────────────────────────────────────
// Narrow layout (phone): AppBar + Drawer
// ──────────────────────────────────────────────────────────────────────

class _NarrowLayout extends StatelessWidget {
  final String title;
  final Widget body;
  final int currentIndex;
  final List<_AdminNavItem> navItems;
  final ValueChanged<int> onNavTap;
  final List<Widget>? actions;
  final FloatingActionButton? floatingActionButton;

  const _NarrowLayout({
    required this.title,
    required this.body,
    required this.currentIndex,
    required this.navItems,
    required this.onNavTap,
    required this.actions,
    required this.floatingActionButton,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title), actions: actions),
      drawer: _AdminDrawer(
        navItems: navItems,
        currentIndex: currentIndex,
        onNavTap: (i) {
          Navigator.pop(context);
          onNavTap(i);
        },
      ),
      body: body,
      floatingActionButton: floatingActionButton,
    );
  }
}

// ──────────────────────────────────────────────────────────────────────
// Wide layout (tablet/desktop): NavigationRail + body
// ──────────────────────────────────────────────────────────────────────

class _WideLayout extends StatelessWidget {
  final String title;
  final Widget body;
  final int currentIndex;
  final List<_AdminNavItem> navItems;
  final ValueChanged<int> onNavTap;
  final List<Widget>? actions;
  final FloatingActionButton? floatingActionButton;

  const _WideLayout({
    required this.title,
    required this.body,
    required this.currentIndex,
    required this.navItems,
    required this.onNavTap,
    required this.actions,
    required this.floatingActionButton,
  });

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    return Scaffold(
      drawer: _AdminDrawer(
        navItems: navItems,
        currentIndex: -1,
        onNavTap: (_) {},
      ),
      body: SafeArea(
        child: Row(
          children: [
            _AdminRail(
              navItems: navItems,
              currentIndex: currentIndex,
              onNavTap: onNavTap,
            ),
            VerticalDivider(width: 1, color: sem.border),
            Expanded(
              child: Column(
                children: [
                  _TopBar(title: title, actions: actions),
                  Divider(height: 1, color: sem.border),
                  Expanded(child: body),
                ],
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}

class _TopBar extends StatelessWidget {
  final String title;
  final List<Widget>? actions;

  const _TopBar({required this.title, required this.actions});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(color: Theme.of(context).colorScheme.surface),
      child: Row(
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w600,
              color: sem.textMuted.withValues(alpha: 1),
            ),
          ),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.menu_open),
            tooltip:
                AppLocalizations.of(context)?.allSections ?? 'All sections',
            onPressed: () => Scaffold.of(context).openDrawer(),
          ),
          if (actions != null) ...actions!,
        ],
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────────────
// Navigation rail (wide)
// ──────────────────────────────────────────────────────────────────────

class _AdminRail extends StatelessWidget {
  final List<_AdminNavItem> navItems;
  final int currentIndex;
  final ValueChanged<int> onNavTap;

  const _AdminRail({
    required this.navItems,
    required this.currentIndex,
    required this.onNavTap,
  });

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final admin = auth.admin;
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);

    return Container(
      width: 240,
      color: theme.colorScheme.surface,
      child: Column(
        children: [
          const SizedBox(height: 16),
          // ── Brand ──────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primary,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.admin_panel_settings,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        admin?.company?.name ??
                            (AppLocalizations.of(context)?.adminPortal ??
                                'Admin Portal'),
                        style: theme.textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        (admin?.role ?? '').toUpperCase(),
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: sem.textFaint,
                          letterSpacing: 1.1,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          // ── Nav items ──────────────────────────────────────────
          for (var i = 0; i < navItems.length; i++)
            _RailItem(
              item: navItems[i],
              selected: i == currentIndex,
              onTap: () => onNavTap(i),
            ),
          const Spacer(),
          Divider(height: 1, color: sem.border),
          _RailFooter(admin: admin),
        ],
      ),
    );
  }
}

class _RailItem extends StatelessWidget {
  final _AdminNavItem item;
  final bool selected;
  final VoidCallback onTap;

  const _RailItem({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final bg = selected
        ? theme.colorScheme.primary.withValues(alpha: 0.1)
        : Colors.transparent;
    final fg = selected ? theme.colorScheme.primary : sem.textSub;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(
              children: [
                Icon(
                  selected ? item.selectedIcon : item.icon,
                  size: 20,
                  color: fg,
                ),
                const SizedBox(width: 12),
                Text(
                  item.label,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: fg,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
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

class _RailFooter extends StatelessWidget {
  final dynamic admin;

  const _RailFooter({required this.admin});

  Future<void> _logout(BuildContext context) async {
    await context.read<AuthProvider>().logout();
    if (context.mounted) {
      Navigator.pushNamedAndRemoveUntil(context, AppRoutes.login, (_) => false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);

    return Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: theme.colorScheme.primary,
            child: Text(
              admin?.initials ?? '?',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  admin?.fullName.isNotEmpty == true
                      ? admin!.fullName
                      : (admin?.email ?? ''),
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  admin?.email ?? '',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: sem.textFaint,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: () => _logout(context),
            icon: Icon(Icons.logout, size: 20, color: sem.danger),
            tooltip: AppLocalizations.of(context)?.logout ?? 'Logout',
          ),
        ],
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────────────
// Drawer (narrow)
// ──────────────────────────────────────────────────────────────────────

class _AdminDrawer extends StatelessWidget {
  final List<_AdminNavItem> navItems;
  final int currentIndex;
  final ValueChanged<int> onNavTap;

  const _AdminDrawer({
    required this.navItems,
    required this.currentIndex,
    required this.onNavTap,
  });

  Future<void> _logout(BuildContext context) async {
    Navigator.pop(context);
    await context.read<AuthProvider>().logout();
    if (context.mounted) {
      Navigator.pushNamedAndRemoveUntil(context, AppRoutes.login, (_) => false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final admin = auth.admin;
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final localeProvider = context.watch<LocaleProvider>();
    final themeProvider = context.watch<ThemeProvider>();

    return Drawer(
      child: Column(
        children: [
          // ── Header ─────────────────────────────────────────────
          Container(
            padding: EdgeInsets.only(
              top: MediaQuery.of(context).padding.top + 16,
              left: 20,
              right: 20,
              bottom: 20,
            ),
            decoration: BoxDecoration(color: theme.colorScheme.primary),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 26,
                  backgroundColor: Colors.white,
                  child: Text(
                    admin?.initials ?? '?',
                    style: TextStyle(
                      color: theme.colorScheme.primary,
                      fontWeight: FontWeight.w700,
                      fontSize: 18,
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        admin?.fullName.isNotEmpty == true
                            ? admin!.fullName
                            : (admin?.email ?? ''),
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${admin?.role.toUpperCase() ?? ''} • ${admin?.company?.name ?? ''}',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.85),
                          fontSize: 12,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // ── Nav items ──────────────────────────────────────────
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 8),
              children: [
                for (var i = 0; i < navItems.length; i++)
                  ListTile(
                    leading: Icon(
                      i == currentIndex
                          ? navItems[i].selectedIcon
                          : navItems[i].icon,
                      color: i == currentIndex
                          ? theme.colorScheme.primary
                          : sem.textSub,
                    ),
                    title: Text(
                      navItems[i].label,
                      style: TextStyle(
                        fontWeight: i == currentIndex
                            ? FontWeight.w600
                            : FontWeight.w500,
                        color: i == currentIndex
                            ? theme.colorScheme.primary
                            : null,
                      ),
                    ),
                    selected: i == currentIndex,
                    onTap: () => onNavTap(i),
                  ),
                const Divider(),
                // ── All admin sections grouped ─────────────────
                for (final entry in groupSections().entries) ...[
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
                    child: Text(
                      localizedGroupLabel(context, entry.key).toUpperCase(),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: sem.textFaint,
                        letterSpacing: 1.1,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  for (final section in entry.value)
                    if (section.endpoint.isNotEmpty)
                      ListTile(
                        dense: true,
                        leading: Icon(
                          section.icon,
                          size: 20,
                          color: sem.textSub,
                        ),
                        title: Text(section.title),
                        onTap: () {
                          Navigator.pop(context);
                          Navigator.pushNamed(
                            context,
                            AppRoutes.adminList,
                            arguments: section.key,
                          );
                        },
                      ),
                ],
                const Divider(),
                // ── Theme toggle ────────────────────────────────
                ListTile(
                  leading: Icon(
                    themeProvider.themeMode == ThemeMode.dark
                        ? Icons.dark_mode_outlined
                        : Icons.light_mode_outlined,
                    color: sem.textSub,
                  ),
                  title: Text(AppLocalizations.of(context)?.theme ?? 'Theme'),
                  trailing: DropdownButton<ThemeMode>(
                    value: themeProvider.themeMode,
                    underline: const SizedBox.shrink(),
                    items: [
                      DropdownMenuItem(
                        value: ThemeMode.system,
                        child: Text(
                          AppLocalizations.of(context)?.systemTheme ?? 'System',
                        ),
                      ),
                      DropdownMenuItem(
                        value: ThemeMode.light,
                        child: Text(
                          AppLocalizations.of(context)?.lightMode ?? 'Light',
                        ),
                      ),
                      DropdownMenuItem(
                        value: ThemeMode.dark,
                        child: Text(
                          AppLocalizations.of(context)?.darkMode ?? 'Dark',
                        ),
                      ),
                    ],
                    onChanged: (m) {
                      if (m != null) themeProvider.setThemeMode(m);
                    },
                  ),
                ),
                // ── Language toggle ─────────────────────────────
                ListTile(
                  leading: Icon(Icons.language_outlined, color: sem.textSub),
                  title: Text(
                    AppLocalizations.of(context)?.language ?? 'Language',
                  ),
                  trailing: DropdownButton<String>(
                    value: localeProvider.locale.languageCode,
                    underline: const SizedBox.shrink(),
                    items: const [
                      DropdownMenuItem(value: 'en', child: Text('English')),
                      DropdownMenuItem(value: 'ar', child: Text('العربية')),
                      DropdownMenuItem(
                        value: 'id',
                        child: Text('Bahasa Indonesia'),
                      ),
                    ],
                    onChanged: (code) {
                      if (code != null) localeProvider.setLocale(Locale(code));
                    },
                  ),
                ),
              ],
            ),
          ),
          // ── Footer: logout ───────────────────────────────────
          Divider(height: 1, color: sem.border),
          ListTile(
            leading: Icon(Icons.logout, color: sem.danger),
            title: Text(
              AppLocalizations.of(context)?.logout ?? 'Logout',
              style: TextStyle(color: sem.danger),
            ),
            onTap: () => _logout(context),
          ),
        ],
      ),
    );
  }
}
