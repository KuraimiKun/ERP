import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../config/admin_sections.dart';
import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../services/admin_api_service.dart';
import '../../services/api_service.dart';

/// Generic record detail screen.
///
/// Loads `/endpoint/:id/` and renders all fields as a grouped, glassy
/// layout.  Works for any DRF detail endpoint — no per-entity code
/// needed.
class AdminRecordDetailScreen extends StatefulWidget {
  final AdminSection section;
  final int id;
  final Map<String, dynamic>? initial;

  const AdminRecordDetailScreen({
    super.key,
    required this.section,
    required this.id,
    this.initial,
  });

  @override
  State<AdminRecordDetailScreen> createState() =>
      _AdminRecordDetailScreenState();
}

class _AdminRecordDetailScreenState extends State<AdminRecordDetailScreen> {
  Map<String, dynamic>? _record;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _record = widget.initial;
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = AdminApiService(context.read<ApiService>());
      final data = await api.retrieve(widget.section.endpoint, widget.id);
      if (!mounted) return;
      setState(() => _record = data);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = AdminApiService.extractError(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: _buildAppBar(),
      body: _buildBody(context),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return PreferredSize(
      preferredSize: const Size.fromHeight(kToolbarHeight),
      child: ClipRect(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
          child: AppBar(
            backgroundColor: Colors.transparent,
            elevation: 0,
            flexibleSpace: Container(
              decoration: BoxDecoration(
                color: Theme.of(
                  context,
                ).colorScheme.surface.withValues(alpha: 0.55),
              ),
            ),
            title: Text(
              _titleLine(),
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            actions: [
              IconButton(
                icon: AnimatedRotation(
                  turns: _loading ? 1 : 0,
                  duration: const Duration(milliseconds: 800),
                  child: const Icon(Icons.refresh_rounded),
                ),
                onPressed: _loading ? null : _load,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _titleLine() {
    if (_record == null) return '${widget.section.title} #${widget.id}';
    return widget.section.title_.render(_record!);
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _record == null) {
      return const _SkeletonDetail();
    }
    if (_error != null && _record == null) {
      return _ErrorState(error: _error!, onRetry: _load);
    }

    final record = _record ?? const <String, dynamic>{};
    return Stack(
      children: [
        const _AmbientBackdrop(),
        RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            padding: EdgeInsets.only(
              top: MediaQuery.of(context).padding.top + kToolbarHeight + 12,
              bottom: 28,
              left: 16,
              right: 16,
            ),
            children: [
              _HeroCard(section: widget.section, record: record),
              const SizedBox(height: 18),
              ..._buildFieldGroups(record),
            ],
          ),
        ),
      ],
    );
  }

  // Split fields into semantic groups so the page isn't one huge list.
  List<Widget> _buildFieldGroups(Map<String, dynamic> record) {
    final scalars = <MapEntry<String, dynamic>>[];
    final collections = <MapEntry<String, dynamic>>[];
    final nested = <MapEntry<String, dynamic>>[];

    for (final e in record.entries) {
      if (e.key == 'id') continue; // surfaced in the hero card
      final v = e.value;
      if (v is List) {
        collections.add(e);
      } else if (v is Map) {
        nested.add(e);
      } else {
        scalars.add(e);
      }
    }

    // Within scalars, push timestamps to the bottom for calm flow.
    int rank(MapEntry<String, dynamic> e) {
      final k = e.key.toLowerCase();
      if (k == 'id') return 0;
      if (k.endsWith('_at') || k.endsWith('_on') || k.contains('date')) {
        return 10;
      }
      return 5;
    }

    scalars.sort((a, b) => rank(a).compareTo(rank(b)));

    final widgets = <Widget>[];
    if (scalars.isNotEmpty) {
      widgets.add(
        _FieldGroup(
          title: AppLocalizations.of(context)?.details ?? 'Details',
          icon: Icons.description_outlined,
          entries: scalars,
        ),
      );
    }
    for (final e in nested) {
      widgets.add(const SizedBox(height: 14));
      widgets.add(_NestedCard(keyName: e.key, value: e.value as Map));
    }
    for (final e in collections) {
      widgets.add(const SizedBox(height: 14));
      widgets.add(_CollectionCard(keyName: e.key, items: e.value as List));
    }
    // Also include the id row at the very top of a hidden "Meta" group if
    // the caller wants to copy it.
    widgets.add(const SizedBox(height: 14));
    widgets.add(_MetaRow(id: record['id']));
    return widgets;
  }
}

// ─────────────────────────────────────────────────────────────────────
// Ambient backdrop (matches list screen vibe)
// ─────────────────────────────────────────────────────────────────────
class _AmbientBackdrop extends StatelessWidget {
  const _AmbientBackdrop();

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final sem = AppTheme.semantics(context);
    return IgnorePointer(
      child: Stack(
        children: [
          Positioned(
            top: -160,
            right: -80,
            child: _Blob(
              color: Theme.of(context).colorScheme.primary,
              size: 320,
              opacity: isDark ? 0.18 : 0.10,
            ),
          ),
          Positioned(
            top: 180,
            left: -100,
            child: _Blob(
              color: sem.accent,
              size: 260,
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
  const _Blob({required this.color, required this.size, required this.opacity});
  @override
  Widget build(BuildContext context) => Container(
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

// ─────────────────────────────────────────────────────────────────────
// Hero card — section icon, title, id chip, primary status badge,
// quick-fact strip with two or three key fields.
// ─────────────────────────────────────────────────────────────────────
class _HeroCard extends StatelessWidget {
  final AdminSection section;
  final Map<String, dynamic> record;
  const _HeroCard({required this.section, required this.record});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final accent = theme.colorScheme.primary;
    final title = section.title_.render(record);
    final subtitle = section.subtitle?.render(record);
    final trailing = section.trailing?.render(record);
    final badge = _badgeTone(trailing, sem, accent);

    return ClipRRect(
      borderRadius: BorderRadius.circular(22),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                accent.withValues(alpha: 0.14),
                accent.withValues(alpha: 0.02),
              ],
            ),
            border: Border.all(color: accent.withValues(alpha: 0.22)),
            boxShadow: [
              BoxShadow(
                color: accent.withValues(alpha: 0.12),
                blurRadius: 24,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 54,
                    height: 54,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          accent.withValues(alpha: 0.28),
                          accent.withValues(alpha: 0.10),
                        ],
                      ),
                      border: Border.all(color: accent.withValues(alpha: 0.35)),
                    ),
                    child: Icon(section.icon, color: accent, size: 26),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          section.title.toUpperCase(),
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: sem.textMuted,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.9,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          title,
                          style: theme.textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.4,
                            height: 1.2,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              if (subtitle != null && subtitle != '—') ...[
                const SizedBox(height: 10),
                Text(
                  subtitle,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: sem.textSub,
                    height: 1.35,
                  ),
                ),
              ],
              if (trailing != null && trailing != '—') ...[
                const SizedBox(height: 14),
                _Badge(label: trailing, tone: badge),
              ],
              const SizedBox(height: 14),
              _QuickFactStrip(record: record, accent: accent),
            ],
          ),
        ),
      ),
    );
  }
}

class _QuickFactStrip extends StatelessWidget {
  final Map<String, dynamic> record;
  final Color accent;
  const _QuickFactStrip({required this.record, required this.accent});

  @override
  Widget build(BuildContext context) {
    final facts = _pickFacts(record).take(3).toList();
    if (facts.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    return Row(
      children: [
        for (var i = 0; i < facts.length; i++) ...[
          if (i > 0)
            Container(
              width: 1,
              height: 28,
              margin: const EdgeInsets.symmetric(horizontal: 10),
              color: sem.borderSoft,
            ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _humanize(facts[i].key),
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: sem.textMuted,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.4,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  _format(facts[i].value),
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: accent,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  // Prefer money/amount/total/balance, else dates, else booleans.
  List<MapEntry<String, dynamic>> _pickFacts(Map<String, dynamic> r) {
    final out = <MapEntry<String, dynamic>>[];
    final moneyKeys = RegExp(
      r'(amount|total|balance|price|cost|paid|due|subtotal|tax|net|gross)',
      caseSensitive: false,
    );
    final dateKeys = RegExp(r'(date|_at|_on)$|^date', caseSensitive: false);
    for (final e in r.entries) {
      if (e.value == null || e.value is Map || e.value is List) continue;
      if (moneyKeys.hasMatch(e.key)) out.add(e);
    }
    for (final e in r.entries) {
      if (out.any((x) => x.key == e.key)) continue;
      if (e.value == null || e.value is Map || e.value is List) continue;
      if (dateKeys.hasMatch(e.key)) out.add(e);
    }
    return out;
  }
}

// ─────────────────────────────────────────────────────────────────────
// Field group card — alternating row tint, humanized key, copyable value
// ─────────────────────────────────────────────────────────────────────
class _FieldGroup extends StatelessWidget {
  final String title;
  final IconData icon;
  final List<MapEntry<String, dynamic>> entries;

  const _FieldGroup({
    required this.title,
    required this.icon,
    required this.entries,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: sem.borderSoft),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _SectionHeader(icon: icon, title: title),
          for (var i = 0; i < entries.length; i++)
            _KvRow(keyName: entries[i].key, value: entries[i].value, index: i),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  const _SectionHeader({required this.icon, required this.title});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
      child: Row(
        children: [
          Icon(icon, size: 16, color: sem.textMuted),
          const SizedBox(width: 8),
          Text(
            title.toUpperCase(),
            style: theme.textTheme.labelSmall?.copyWith(
              color: sem.textMuted,
              fontWeight: FontWeight.w700,
              letterSpacing: 1,
            ),
          ),
        ],
      ),
    );
  }
}

class _KvRow extends StatefulWidget {
  final String keyName;
  final dynamic value;
  final int index;

  const _KvRow({
    required this.keyName,
    required this.value,
    required this.index,
  });

  @override
  State<_KvRow> createState() => _KvRowState();
}

class _KvRowState extends State<_KvRow> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final display = _format(widget.value);
    final isZebra = widget.index.isOdd;

    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 140),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        color: _hover
            ? sem.accent.withValues(alpha: 0.06)
            : (isZebra ? sem.surfaceAlt.withValues(alpha: 0.4) : null),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 130,
              child: Text(
                _humanize(widget.keyName),
                style: theme.textTheme.labelMedium?.copyWith(
                  color: sem.textMuted,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.2,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _ValueView(value: widget.value, display: display),
            ),
            AnimatedOpacity(
              opacity: _hover ? 1 : 0,
              duration: const Duration(milliseconds: 140),
              child: Padding(
                padding: const EdgeInsets.only(left: 8),
                child: InkResponse(
                  radius: 18,
                  onTap: () => _copy(context, display),
                  child: Icon(
                    Icons.copy_rounded,
                    size: 16,
                    color: sem.textMuted,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _copy(BuildContext context, String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (!context.mounted) return;
    final l10n = AppLocalizations.of(context);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        duration: const Duration(seconds: 1),
        content: Text(
          l10n?.copied(widget.keyName) ?? 'Copied "${widget.keyName}"',
        ),
      ),
    );
  }
}

class _ValueView extends StatelessWidget {
  final dynamic value;
  final String display;
  const _ValueView({required this.value, required this.display});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);

    if (value is bool) {
      return _BooleanPill(value: value as bool);
    }

    // Status-like string → colored pill
    if (value is String && _looksLikeStatus(value as String)) {
      final tone = _badgeTone(value as String, sem, theme.colorScheme.primary);
      return Align(
        alignment: Alignment.centerLeft,
        child: _Badge(label: (value as String).toUpperCase(), tone: tone),
      );
    }

    return SelectableText(
      display,
      style: theme.textTheme.bodyMedium?.copyWith(
        fontWeight: FontWeight.w600,
        height: 1.35,
      ),
    );
  }

  bool _looksLikeStatus(String v) {
    if (v.isEmpty || v.length > 24) return false;
    final t = v.toLowerCase();
    const markers = [
      'paid',
      'approved',
      'active',
      'completed',
      'success',
      'open',
      'pending',
      'submitted',
      'review',
      'draft',
      'inactive',
      'overdue',
      'rejected',
      'failed',
      'cancelled',
      'canceled',
      'closed',
    ];
    return markers.any(t.contains);
  }
}

class _BooleanPill extends StatelessWidget {
  final bool value;
  const _BooleanPill({required this.value});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final fg = value ? sem.success : sem.textMuted;
    final bg = value ? sem.successContainer : sem.surfaceAlt;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: fg.withValues(alpha: 0.2)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              value ? Icons.check_rounded : Icons.remove_rounded,
              size: 14,
              color: fg,
            ),
            const SizedBox(width: 4),
            Text(
              value ? 'Yes' : 'No',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: fg,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Nested + collection cards
// ─────────────────────────────────────────────────────────────────────
class _NestedCard extends StatelessWidget {
  final String keyName;
  final Map<dynamic, dynamic> value;
  const _NestedCard({required this.keyName, required this.value});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final entries = value.entries
        .map<MapEntry<String, dynamic>>(
          (e) => MapEntry(e.key.toString(), e.value),
        )
        .toList();

    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: sem.borderSoft),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _SectionHeader(
            icon: Icons.account_tree_outlined,
            title: _humanize(keyName),
          ),
          for (var i = 0; i < entries.length; i++)
            _KvRow(keyName: entries[i].key, value: entries[i].value, index: i),
        ],
      ),
    );
  }
}

class _CollectionCard extends StatelessWidget {
  final String keyName;
  final List<dynamic> items;
  const _CollectionCard({required this.keyName, required this.items});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    final accent = sem.accent;

    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: sem.borderSoft),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
            child: Row(
              children: [
                Icon(
                  Icons.format_list_bulleted_rounded,
                  size: 16,
                  color: sem.textMuted,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _humanize(keyName).toUpperCase(),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: sem.textMuted,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '${items.length}',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: accent,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (items.isEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
              child: Text(
                AppLocalizations.of(context)?.noItems ?? 'No items',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: sem.textMuted,
                  fontStyle: FontStyle.italic,
                ),
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Column(
                children: [
                  for (var i = 0; i < items.length; i++)
                    _CollectionItem(item: items[i], index: i),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _CollectionItem extends StatelessWidget {
  final dynamic item;
  final int index;
  const _CollectionItem({required this.item, required this.index});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);

    if (item is Map) {
      final m = item as Map;
      final title =
          (m['name'] ??
                  m['title'] ??
                  m['label'] ??
                  m['description'] ??
                  m['id'] ??
                  '—')
              .toString();
      final subtitle = (m['status'] ?? m['amount'] ?? m['quantity'])
          ?.toString();
      return Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: sem.surfaceAlt.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: sem.borderSoft),
        ),
        child: Row(
          children: [
            Container(
              width: 26,
              height: 26,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: sem.accent.withValues(alpha: 0.12),
              ),
              child: Text(
                '${index + 1}',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: sem.accent,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (subtitle != null && subtitle != 'null') ...[
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: sem.textSub,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      child: Row(
        children: [
          Icon(Icons.circle, size: 6, color: sem.textFaint),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              item?.toString() ?? '—',
              style: theme.textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// ID / meta row at the bottom
// ─────────────────────────────────────────────────────────────────────
class _MetaRow extends StatelessWidget {
  final dynamic id;
  const _MetaRow({required this.id});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sem = AppTheme.semantics(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: Row(
        children: [
          Icon(Icons.fingerprint_rounded, size: 14, color: sem.textFaint),
          const SizedBox(width: 6),
          Text(
            AppLocalizations.of(context)?.recordId ?? 'Record ID',
            style: theme.textTheme.labelSmall?.copyWith(
              color: sem.textFaint,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.6,
            ),
          ),
          const SizedBox(width: 6),
          SelectableText(
            '#${id ?? '—'}',
            style: theme.textTheme.labelSmall?.copyWith(
              color: sem.textMuted,
              fontWeight: FontWeight.w700,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Badge helpers
// ─────────────────────────────────────────────────────────────────────
class _BadgeTone {
  final Color fg;
  final Color bg;
  const _BadgeTone(this.fg, this.bg);
}

_BadgeTone _badgeTone(String? trailing, AppSemanticColors sem, Color fallback) {
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
  return _BadgeTone(fallback, fallback.withValues(alpha: 0.12));
}

class _Badge extends StatelessWidget {
  final String label;
  final _BadgeTone tone;
  const _Badge({required this.label, required this.tone});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: tone.bg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tone.fg.withValues(alpha: 0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            margin: const EdgeInsets.only(right: 7),
            decoration: BoxDecoration(shape: BoxShape.circle, color: tone.fg),
          ),
          Text(
            label,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: tone.fg,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Skeleton + error states
// ─────────────────────────────────────────────────────────────────────
class _SkeletonDetail extends StatefulWidget {
  const _SkeletonDetail();
  @override
  State<_SkeletonDetail> createState() => _SkeletonDetailState();
}

class _SkeletonDetailState extends State<_SkeletonDetail>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();
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
    Widget block(double w, double h, {double r = 8}) => Container(
      width: w,
      height: h,
      decoration: BoxDecoration(
        color: sem.surfaceAlt,
        borderRadius: BorderRadius.circular(r),
      ),
    );

    return ListView(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + kToolbarHeight + 12,
        bottom: 28,
        left: 16,
        right: 16,
      ),
      children: [
        AnimatedBuilder(
          animation: _c,
          builder: (context, _) {
            return ShaderMask(
              shaderCallback: (rect) => LinearGradient(
                begin: Alignment(-1 + _c.value * 2, 0),
                end: Alignment(1 + _c.value * 2, 0),
                colors: [sem.surfaceAlt, sem.borderSoft, sem.surfaceAlt],
                stops: const [0.35, 0.5, 0.65],
              ).createShader(rect),
              blendMode: BlendMode.srcATop,
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(22),
                      color: theme.colorScheme.surface,
                      border: Border.all(color: sem.borderSoft),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            block(54, 54, r: 16),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  block(80, 10),
                                  const SizedBox(height: 10),
                                  block(210, 16),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 18),
                        block(double.infinity, 12),
                        const SizedBox(height: 10),
                        block(180, 12),
                      ],
                    ),
                  ),
                  const SizedBox(height: 18),
                  for (var i = 0; i < 2; i++) ...[
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(18),
                        color: theme.colorScheme.surface,
                        border: Border.all(color: sem.borderSoft),
                      ),
                      child: Column(
                        children: [
                          for (var k = 0; k < 4; k++)
                            Padding(
                              padding: const EdgeInsets.symmetric(vertical: 9),
                              child: Row(
                                children: [
                                  block(110, 10),
                                  const SizedBox(width: 20),
                                  Expanded(child: block(140, 10)),
                                ],
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 14),
                  ],
                ],
              ),
            );
          },
        ),
      ],
    );
  }
}

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
            child: Icon(
              Icons.error_outline_rounded,
              size: 40,
              color: sem.danger,
            ),
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

// ─────────────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────────────
String _humanize(String key) {
  return key
      .replaceAll('_', ' ')
      .split(' ')
      .where((p) => p.isNotEmpty)
      .map((p) => p[0].toUpperCase() + p.substring(1))
      .join(' ');
}

String _format(dynamic v) {
  if (v == null) return '—';
  if (v is bool) return v ? 'Yes' : 'No';
  if (v is List) {
    if (v.isEmpty) return '—';
    return v.map((e) => e.toString()).join(', ');
  }
  if (v is Map) return v.toString();
  return v.toString();
}
