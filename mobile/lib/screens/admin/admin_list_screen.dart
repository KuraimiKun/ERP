import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/admin_sections.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../providers/admin_list_provider.dart';
import '../../services/admin_api_service.dart';
import '../../services/api_service.dart';
import 'admin_shell.dart';

/// Generic list screen driven by an [AdminSection].
///
/// Navigate with:
/// ```dart
/// Navigator.pushNamed(context, AppRoutes.adminList, arguments: 'employees');
/// ```
class AdminListScreen extends StatefulWidget {
  final AdminSection section;
  const AdminListScreen({super.key, required this.section});

  @override
  State<AdminListScreen> createState() => _AdminListScreenState();
}

class _AdminListScreenState extends State<AdminListScreen> {
  late final AdminListProvider _provider;
  final _searchCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  bool _condensedHeader = false;

  @override
  void initState() {
    super.initState();
    _provider = AdminListProvider(
      AdminApiService(context.read<ApiService>()),
      endpoint: widget.section.endpoint,
    );
    WidgetsBinding.instance
        .addPostFrameCallback((_) => _provider.load(reset: true));
    _scrollCtrl.addListener(_onScroll);
  }

  void _onScroll() {
    final shouldCondense = _scrollCtrl.offset > 24;
    if (shouldCondense != _condensedHeader) {
      setState(() => _condensedHeader = shouldCondense);
    }
    if (_scrollCtrl.position.pixels >=
        _scrollCtrl.position.maxScrollExtent - 240) {
      _provider.loadMore();
    }
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    _searchCtrl.dispose();
    _provider.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: _provider,
      child: Consumer<AdminListProvider>(
        builder: (context, p, _) => AdminShell(
          title: widget.section.title,
          currentIndex: -1,
          body: Stack(
            children: [
              const _AmbientBackdrop(),
              Column(
                children: [
                  _GlassHeader(
                    section: widget.section,
                    controller: _searchCtrl,
                    totalCount: p.items.length,
                    isLoading: p.isLoading,
                    compact: _condensedHeader,
                    onSubmit: p.setSearch,
                    onClear: () {
                      _searchCtrl.clear();
                      p.setSearch('');
                    },
                  ),
                  Expanded(child: _buildBody(context, p)),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context, AdminListProvider p) {
    if (p.isLoading && p.items.isEmpty) {
      return const _SkeletonList();
    }
    if (p.error != null && p.items.isEmpty) {
      return _ErrorState(
        error: p.error!,
        onRetry: () => p.load(reset: true),
      );
    }
    if (p.items.isEmpty) {
      return const _EmptyState();
    }

    return RefreshIndicator(
      onRefresh: p.refresh,
      child: ListView.builder(
        controller: _scrollCtrl,
        padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
        itemCount: p.items.length + (p.isLoadingMore ? 1 : 0),
        itemBuilder: (context, i) {
          if (i >= p.items.length) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Center(
                child: SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2.4),
                ),
              ),
            );
          }
          final row = p.items[i];
          return _AnimatedEntrance(
            index: i,
            child: _Card(
              section: widget.section,
              row: row,
              index: i,
              onTap: () => _openDetail(context, row),
            ),
          );
        },
      ),
    );
  }

  void _openDetail(BuildContext context, Map<String, dynamic> row) {
    Navigator.pushNamed(
      context,
      AppRoutes.adminDetail,
      arguments: {
        'section': widget.section.key,
        'id': (row['id'] as num?)?.toInt(),
        'initial': row,
      },
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Ambient backdrop — soft radial color wash
// ─────────────────────────────────────────────────────────────────────
class _AmbientBackdrop extends StatelessWidget {
  const _AmbientBackdrop();

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return IgnorePointer(
      child: Stack(
        children: [
          Positioned(
            top: -120,
            right: -60,
            child: _Blob(
              color: Theme.of(context).colorScheme.primary,
              size: 280,
              opacity: isDark ? 0.18 : 0.10,
            ),
          ),
          Positioned(
            top: 160,
            left: -80,
            child: _Blob(
              color: AppTheme.semantics(context).accent,
              size: 220,
              opacity: isDark ? 0.14 : 0.08,
            ),
          ),
        ],
      ),
    );
  }
}

class _Blob extends StatelessWidget {
  final Color color;
  final double size;
  final double opacity;
  const _Blob(
      {required this.color, required this.size, required this.opacity});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [
            color.withValues(alpha: opacity),
            color.withValues(alpha: 0),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Glassmorphism header — title, count pill, frosted search bar
// ─────────────────────────────────────────────────────────────────────
class _GlassHeader extends StatelessWidget {
  final AdminSection section;
  final TextEditingController controller;
  final int totalCount;
  final bool isLoading;
  final bool compact;
  final ValueChanged<String> onSubmit;
  final VoidCallback onClear;

  const _GlassHeader({
    required this.section,
    required this.controller,
    required this.totalCount,
    required this.isLoading,
    required this.compact,
    required this.onSubmit,
    required this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final isDark = theme.brightness == Brightness.dark;
    final glassBg = isDark
        ? Colors.white.withValues(alpha: 0.04)
        : Colors.white.withValues(alpha: 0.55);

    return ClipRRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
          padding: EdgeInsets.fromLTRB(16, 14, 16, compact ? 10 : 16),
          decoration: BoxDecoration(
            color: glassBg,
            border: Border(
              bottom: BorderSide(color: sem.borderSoft),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              AnimatedCrossFade(
                crossFadeState: compact
                    ? CrossFadeState.showSecond
                    : CrossFadeState.showFirst,
                duration: const Duration(milliseconds: 180),
                firstChild: _buildFullTitle(context, theme, sem),
                secondChild: const SizedBox.shrink(),
              ),
              SizedBox(height: compact ? 0 : 12),
              _SearchField(
                controller: controller,
                hintText: section.searchHint ??
                    '${AppLocalizations.of(context)?.search ?? 'Search'} ${section.title.toLowerCase()}…',
                onSubmit: onSubmit,
                onClear: onClear,
                accent: theme.colorScheme.primary,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFullTitle(
      BuildContext context, ThemeData theme, AppSemanticColors sem) {
    return Row(
      children: [
        _IconChip(icon: section.icon, accent: theme.colorScheme.primary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                section.title,
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.4,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                localizedGroupLabel(context, section.group).toUpperCase(),
                style: theme.textTheme.labelSmall?.copyWith(
                  color: sem.textMuted,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.9,
                ),
              ),
            ],
          ),
        ),
        _CountPill(count: totalCount, pulsing: isLoading),
      ],
    );
  }
}

class _IconChip extends StatelessWidget {
  final IconData icon;
  final Color accent;
  const _IconChip({required this.icon, required this.accent});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            accent.withValues(alpha: 0.18),
            accent.withValues(alpha: 0.06),
          ],
        ),
        border: Border.all(color: accent.withValues(alpha: 0.25)),
      ),
      child: Icon(icon, color: accent, size: 22),
    );
  }
}

class _CountPill extends StatelessWidget {
  final int count;
  final bool pulsing;
  const _CountPill({required this.count, required this.pulsing});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: sem.surfaceAlt,
        border: Border.all(color: sem.borderSoft),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (pulsing)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: SizedBox(
                width: 10,
                height: 10,
                child: CircularProgressIndicator(
                  strokeWidth: 1.6,
                  color: theme.colorScheme.primary,
                ),
              ),
            ),
          Text(
            '$count',
            style: theme.textTheme.labelMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _SearchField extends StatefulWidget {
  final TextEditingController controller;
  final String hintText;
  final ValueChanged<String> onSubmit;
  final VoidCallback onClear;
  final Color accent;

  const _SearchField({
    required this.controller,
    required this.hintText,
    required this.onSubmit,
    required this.onClear,
    required this.accent,
  });

  @override
  State<_SearchField> createState() => _SearchFieldState();
}

class _SearchFieldState extends State<_SearchField> {
  final _focus = FocusNode();

  @override
  void initState() {
    super.initState();
    _focus.addListener(() => setState(() {}));
    widget.controller.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final focused = _focus.hasFocus;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.7),
        border: Border.all(
          color: focused
              ? widget.accent.withValues(alpha: 0.6)
              : sem.borderSoft,
          width: focused ? 1.5 : 1,
        ),
        boxShadow: focused
            ? [
                BoxShadow(
                  color: widget.accent.withValues(alpha: 0.15),
                  blurRadius: 16,
                  spreadRadius: 1,
                ),
              ]
            : null,
      ),
      child: TextField(
        controller: widget.controller,
        focusNode: _focus,
        textInputAction: TextInputAction.search,
        decoration: InputDecoration(
          hintText: widget.hintText,
          prefixIcon: Icon(
            Icons.search_rounded,
            color: focused ? widget.accent : sem.textMuted,
          ),
          suffixIcon: widget.controller.text.isEmpty
              ? null
              : IconButton(
                  icon: const Icon(Icons.close_rounded, size: 18),
                  onPressed: widget.onClear,
                ),
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(vertical: 14),
        ),
        onSubmitted: widget.onSubmit,
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Floating card — asymmetric accent rail, avatar, dynamic badge,
// hover lift + press scale, quick-action arrow on hover
// ─────────────────────────────────────────────────────────────────────
class _Card extends StatefulWidget {
  final AdminSection section;
  final Map<String, dynamic> row;
  final int index;
  final VoidCallback onTap;

  const _Card({
    required this.section,
    required this.row,
    required this.index,
    required this.onTap,
  });

  @override
  State<_Card> createState() => _CardState();
}

class _CardState extends State<_Card> {
  bool _hover = false;
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final isDark = theme.brightness == Brightness.dark;

    final title = widget.section.title_.render(widget.row);
    final subtitle = widget.section.subtitle?.render(widget.row);
    final trailing = widget.section.trailing?.render(widget.row);
    final accent = _accentFor(widget.index, theme, sem);
    final badgeTone = _toneFor(trailing, sem, accent);

    final scale = _pressed ? 0.985 : (_hover ? 1.005 : 1.0);
    final shadow = _hover
        ? [
            BoxShadow(
              color: accent.withValues(alpha: isDark ? 0.25 : 0.18),
              blurRadius: 18,
              offset: const Offset(0, 6),
            ),
          ]
        : [
            BoxShadow(
              color: Colors.black.withValues(alpha: isDark ? 0.25 : 0.04),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ];

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: MouseRegion(
        onEnter: (_) => setState(() => _hover = true),
        onExit: (_) => setState(() => _hover = false),
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          onTapDown: (_) => setState(() => _pressed = true),
          onTapCancel: () => setState(() => _pressed = false),
          onTapUp: (_) => setState(() => _pressed = false),
          onTap: widget.onTap,
          child: AnimatedScale(
            scale: scale,
            duration: const Duration(milliseconds: 120),
            curve: Curves.easeOut,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              decoration: BoxDecoration(
                color: theme.colorScheme.surface,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: _hover
                      ? accent.withValues(alpha: 0.35)
                      : sem.borderSoft,
                ),
                boxShadow: shadow,
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(18),
                child: IntrinsicHeight(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      AnimatedContainer(
                        duration: const Duration(milliseconds: 180),
                        width: _hover ? 5 : 3,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                            colors: [
                              accent,
                              accent.withValues(alpha: 0.4),
                            ],
                          ),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(12, 14, 10, 14),
                        child: _Avatar(label: title, accent: accent),
                      ),
                      Expanded(
                        child: Padding(
                          padding:
                              const EdgeInsets.symmetric(vertical: 14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                title,
                                style: theme.textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: -0.2,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              if (subtitle != null && subtitle != '—') ...[
                                const SizedBox(height: 3),
                                Text(
                                  subtitle,
                                  style:
                                      theme.textTheme.bodySmall?.copyWith(
                                    color: sem.textSub,
                                    height: 1.3,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(8, 0, 10, 0),
                        child: Row(
                          children: [
                            if (trailing != null && trailing != '—')
                              _Badge(label: trailing, tone: badgeTone),
                            AnimatedSwitcher(
                              duration: const Duration(milliseconds: 160),
                              transitionBuilder: (c, a) => FadeTransition(
                                opacity: a,
                                child: SlideTransition(
                                  position: Tween(
                                    begin: const Offset(-0.2, 0),
                                    end: Offset.zero,
                                  ).animate(a),
                                  child: c,
                                ),
                              ),
                              child: Padding(
                                key: ValueKey(_hover),
                                padding: const EdgeInsets.only(left: 4),
                                child: Icon(
                                  _hover
                                      ? Icons.arrow_forward_rounded
                                      : Icons.chevron_right_rounded,
                                  size: 18,
                                  color: _hover ? accent : sem.textFaint,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Color _accentFor(int i, ThemeData theme, AppSemanticColors sem) {
    const rotation = [0, 1, 2, 3, 4];
    switch (rotation[i % rotation.length]) {
      case 0:
        return theme.colorScheme.primary;
      case 1:
        return sem.accent;
      case 2:
        return sem.info;
      case 3:
        return sem.purple;
      case 4:
      default:
        return sem.success;
    }
  }

  _BadgeTone _toneFor(
      String? trailing, AppSemanticColors sem, Color fallback) {
    if (trailing == null || trailing == '—') {
      return _BadgeTone(fallback, sem.surfaceAlt);
    }
    final t = trailing.toLowerCase();
    if (t.contains('paid') ||
        t.contains('approved') ||
        t.contains('active') ||
        t.contains('completed') ||
        t.contains('success')) {
      return _BadgeTone(sem.success, sem.successContainer);
    }
    if (t.contains('pending') ||
        t.contains('submitted') ||
        t.contains('review')) {
      return _BadgeTone(sem.warning, sem.warningContainer);
    }
    if (t.contains('overdue') ||
        t.contains('rejected') ||
        t.contains('failed') ||
        t.contains('cancel')) {
      return _BadgeTone(sem.danger, sem.dangerContainer);
    }
    if (t.contains('draft') || t.contains('inactive')) {
      return _BadgeTone(sem.textMuted, sem.surfaceAlt);
    }
    return _BadgeTone(fallback, fallback.withValues(alpha: 0.10));
  }
}

class _BadgeTone {
  final Color fg;
  final Color bg;
  const _BadgeTone(this.fg, this.bg);
}

class _Badge extends StatelessWidget {
  final String label;
  final _BadgeTone tone;
  const _Badge({required this.label, required this.tone});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: tone.bg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: tone.fg.withValues(alpha: 0.18)),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: tone.fg,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2,
            ),
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  final String label;
  final Color accent;
  const _Avatar({required this.label, required this.accent});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 40,
      height: 40,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            accent.withValues(alpha: 0.22),
            accent.withValues(alpha: 0.08),
          ],
        ),
        border: Border.all(color: accent.withValues(alpha: 0.25)),
      ),
      child: Text(
        _initials(label),
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: accent,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.4,
            ),
      ),
    );
  }

  String _initials(String s) {
    final clean = s.trim();
    if (clean.isEmpty) return '•';
    final parts =
        clean.split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '•';
    if (parts.length == 1) {
      final p = parts.first;
      return p.length >= 2
          ? p.substring(0, 2).toUpperCase()
          : p.toUpperCase();
    }
    return (parts.first.characters.first + parts.last.characters.first)
        .toUpperCase();
  }
}

// ─────────────────────────────────────────────────────────────────────
// Staggered fade/slide entrance
// ─────────────────────────────────────────────────────────────────────
class _AnimatedEntrance extends StatelessWidget {
  final int index;
  final Widget child;
  const _AnimatedEntrance({required this.index, required this.child});

  @override
  Widget build(BuildContext context) {
    final delayMs = (index * 30).clamp(0, 360);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 420 + delayMs),
      curve: Curves.easeOutCubic,
      builder: (context, t, child) {
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, (1 - t) * 14),
            child: child,
          ),
        );
      },
      child: child,
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Shimmer skeleton list (loading micro-animation)
// ─────────────────────────────────────────────────────────────────────
class _SkeletonList extends StatelessWidget {
  const _SkeletonList();

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
      itemCount: 8,
      itemBuilder: (_, i) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: _SkeletonCard(delay: i * 80),
      ),
    );
  }
}

class _SkeletonCard extends StatefulWidget {
  final int delay;
  const _SkeletonCard({required this.delay});

  @override
  State<_SkeletonCard> createState() => _SkeletonCardState();
}

class _SkeletonCardState extends State<_SkeletonCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );
    Future.delayed(Duration(milliseconds: widget.delay), () {
      if (mounted) _c.repeat();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final theme = Theme.of(context);
    return Container(
      height: 76,
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: sem.borderSoft),
      ),
      child: AnimatedBuilder(
        animation: _c,
        builder: (context, _) {
          final t = _c.value;
          return ShaderMask(
            shaderCallback: (rect) {
              return LinearGradient(
                begin: Alignment(-1 + t * 2, 0),
                end: Alignment(1 + t * 2, 0),
                colors: [
                  sem.surfaceAlt,
                  sem.borderSoft,
                  sem.surfaceAlt,
                ],
                stops: const [0.35, 0.5, 0.65],
              ).createShader(rect);
            },
            blendMode: BlendMode.srcATop,
            child: Row(
              children: [
                const SizedBox(width: 16),
                _block(40, 40, radius: 20, color: sem.surfaceAlt),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _block(160, 12, color: sem.surfaceAlt),
                      const SizedBox(height: 8),
                      _block(110, 10, color: sem.surfaceAlt),
                    ],
                  ),
                ),
                _block(56, 22, radius: 10, color: sem.surfaceAlt),
                const SizedBox(width: 16),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _block(double w, double h,
      {double radius = 6, required Color color}) {
    return Container(
      width: w,
      height: h,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(radius),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Error + Empty states
// ─────────────────────────────────────────────────────────────────────
class _ErrorState extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;

  const _ErrorState({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 84,
            height: 84,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: sem.dangerContainer,
            ),
            child: Icon(Icons.error_outline_rounded,
                size: 40, color: sem.danger),
          ),
          const SizedBox(height: 16),
          Text(
            error,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh_rounded),
            label: Text(AppLocalizations.of(context)?.retry ?? 'Retry'),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final theme = Theme.of(context);
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  theme.colorScheme.primary.withValues(alpha: 0.12),
                  theme.colorScheme.primary.withValues(alpha: 0),
                ],
              ),
            ),
            child: Icon(Icons.inbox_rounded,
                size: 42, color: theme.colorScheme.primary),
          ),
          const SizedBox(height: 14),
          Text(
            AppLocalizations.of(context)?.noResults ?? 'Nothing here yet',
            style: theme.textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            AppLocalizations.of(context)?.noData ??
                'New records will appear in this list.',
            style:
                theme.textTheme.bodySmall?.copyWith(color: sem.textMuted),
          ),
        ],
      ),
    );
  }
}
