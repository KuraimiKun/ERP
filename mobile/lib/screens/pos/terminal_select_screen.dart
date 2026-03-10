import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/pos_provider.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/loading_indicator.dart';
import '../../widgets/empty_state.dart';

class TerminalSelectScreen extends StatefulWidget {
  const TerminalSelectScreen({super.key});

  @override
  State<TerminalSelectScreen> createState() => _TerminalSelectScreenState();
}

class _TerminalSelectScreenState extends State<TerminalSelectScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<POSProvider>().loadTerminals();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final pos = context.watch<POSProvider>();

    return Scaffold(
      appBar: AppBar(title: Text(l10n.selectTerminal)),
      drawer: const AppDrawer(),
      body: pos.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : RefreshIndicator(
              onRefresh: () => pos.loadTerminals(),
              child: pos.terminals.isEmpty
                  ? EmptyState(
                      icon: Icons.point_of_sale_outlined,
                      message: l10n.noData,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: pos.terminals.length,
                      itemBuilder: (context, index) {
                        final terminal = pos.terminals[index];
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor:
                                  Theme.of(context).primaryColor.withValues(alpha: 0.1),
                              child: Icon(Icons.point_of_sale,
                                  color: Theme.of(context).primaryColor),
                            ),
                            title: Text(terminal.name),
                            subtitle: Text(terminal.location.isNotEmpty
                                ? terminal.location
                                : terminal.code),
                            trailing: terminal.hasOpenSession
                                ? Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: AppTheme.semantics(context).successContainer,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      terminal.openSessionNumber ?? 'Open',
                                      style: TextStyle(
                                          color: AppTheme.semantics(context).success,
                                          fontSize: 12),
                                    ),
                                  )
                                : null,
                            onTap: () => _handleTerminalTap(terminal),
                          ),
                        );
                      },
                    ),
            ),
    );
  }

  void _handleTerminalTap(dynamic terminal) {
    if (terminal.hasOpenSession) {
      // Resume existing session
      final pos = context.read<POSProvider>();
      pos.loadSession(terminal.openSessionId);
      Navigator.pushNamed(context, AppRoutes.posMain);
    } else {
      // Open new session
      _showOpenSessionDialog(terminal);
    }
  }

  void _showOpenSessionDialog(dynamic terminal) {
    final l10n = AppLocalizations.of(context)!;
    final balanceController = TextEditingController(text: '0');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.openSession),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('${terminal.name}'),
            const SizedBox(height: 16),
            TextField(
              controller: balanceController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: l10n.openingBalance,
                prefixIcon: const Icon(Icons.attach_money),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(l10n.cancel),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(ctx);
              final pos = context.read<POSProvider>();
              final success = await pos.openSession(
                terminal.id,
                balanceController.text,
              );
              if (success && mounted) {
                Navigator.pushNamed(context, AppRoutes.posMain);
              }
            },
            child: Text(l10n.openSession),
          ),
        ],
      ),
    );
  }
}
