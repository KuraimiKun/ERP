import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/api_config.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../config/admin_sections.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../services/admin_api_service.dart';
import '../../services/api_service.dart';
import 'admin_shell.dart';

/// Federated search across employees, customers, products, invoices.
class AdminSearchScreen extends StatefulWidget {
  const AdminSearchScreen({super.key});

  @override
  State<AdminSearchScreen> createState() => _AdminSearchScreenState();
}

class _AdminSearchScreenState extends State<AdminSearchScreen> {
  final _ctrl = TextEditingController();
  Timer? _debounce;
  bool _loading = false;
  String? _error;
  Map<String, List<Map<String, dynamic>>> _groups = const {};

  @override
  void dispose() {
    _debounce?.cancel();
    _ctrl.dispose();
    super.dispose();
  }

  void _onChanged(String q) {
    _debounce?.cancel();
    if (q.trim().length < 2) {
      setState(() => _groups = const {});
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 350), () => _search(q));
  }

  Future<void> _search(String q) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = AdminApiService(context.read<ApiService>());
      final res = await api.getRaw(ApiConfig.adminSearch, query: {'q': q});
      final map = Map<String, dynamic>.from(res as Map);
      final results = Map<String, dynamic>.from(map['results'] as Map);
      final grouped = <String, List<Map<String, dynamic>>>{};
      results.forEach((type, list) {
        if (list is List) {
          grouped[type] = list
              .whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m))
              .toList();
        }
      });
      if (!mounted) return;
      setState(() => _groups = grouped);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = AdminApiService.extractError(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _openRecord(String type, Map<String, dynamic> row) {
    final sectionKey = switch (type) {
      'employee' => 'employees',
      'customer' => 'customers',
      'product' => 'products',
      'invoice' => 'invoices',
      _ => null,
    };
    if (sectionKey == null) return;
    Navigator.pushNamed(
      context,
      AppRoutes.adminDetail,
      arguments: {
        'section': sectionKey,
        'id': (row['id'] as num?)?.toInt(),
        'initial': row,
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AdminShell(
      title: l10n.search,
      currentIndex: -1,
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              controller: _ctrl,
              autofocus: true,
              decoration: InputDecoration(
                hintText: l10n.search,
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _ctrl.text.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _ctrl.clear();
                          _onChanged('');
                        },
                      ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              onChanged: _onChanged,
            ),
          ),
          Expanded(child: _buildBody(context)),
        ],
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    final sem = AppTheme.semantics(context);
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_error!, textAlign: TextAlign.center),
        ),
      );
    }
    if (_groups.isEmpty) {
      return Center(
        child: Text(
          AppLocalizations.of(context)?.search ??
              'Type at least 2 characters to search.',
          style: Theme.of(context)
              .textTheme
              .bodyMedium
              ?.copyWith(color: sem.textFaint),
        ),
      );
    }

    final nonEmpty = _groups.entries.where((e) => e.value.isNotEmpty);
    if (nonEmpty.isEmpty) {
      return Center(
        child: Text(
          AppLocalizations.of(context)?.noResults ?? 'No results.',
          style: Theme.of(context)
              .textTheme
              .bodyMedium
              ?.copyWith(color: sem.textFaint),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 8),
      children: [
        for (final entry in nonEmpty)
          _Group(
            type: entry.key,
            items: entry.value,
            onTap: (row) => _openRecord(entry.key, row),
          ),
      ],
    );
  }
}

class _Group extends StatelessWidget {
  final String type;
  final List<Map<String, dynamic>> items;
  final void Function(Map<String, dynamic>) onTap;

  const _Group({
    required this.type,
    required this.items,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final section = switch (type) {
      'employee' => findSection('employees'),
      'customer' => findSection('customers'),
      'product' => findSection('products'),
      'invoice' => findSection('invoices'),
      _ => null,
    };

    final sem = AppTheme.semantics(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
          child: Text(
            _label(type),
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: sem.textFaint,
                  letterSpacing: 0.4,
                ),
          ),
        ),
        for (final row in items)
          ListTile(
            title: Text(
              section == null ? (row['name'] ?? '—').toString() : section.title_.render(row),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: section?.subtitle == null
                ? null
                : Text(
                    section!.subtitle!.render(row),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
            trailing: const Icon(Icons.chevron_right, size: 18),
            onTap: () => onTap(row),
          ),
      ],
    );
  }

  String _label(String t) {
    return '${t[0].toUpperCase()}${t.substring(1)}s';
  }
}
