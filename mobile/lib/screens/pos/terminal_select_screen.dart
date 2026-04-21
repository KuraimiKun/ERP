import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/pos_provider.dart';

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
    final pos = context.watch<POSProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? MColors.darkBg : MColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => Navigator.maybePop(context),
                    child: Icon(Icons.arrow_back_ios_new_rounded, size: 20,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const Spacer(),
                  Text('Select Terminal', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),
            Expanded(
              child: pos.isLoading
                  ? const _Shimmer()
                  : pos.terminals.isEmpty
                      ? const _Empty()
                      : RefreshIndicator(
                          onRefresh: () => pos.loadTerminals(),
                          color: isDark ? MColors.darkPrimary : MColors.primary,
                          child: ListView.builder(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                            itemCount: pos.terminals.length,
                            itemBuilder: (ctx, i) => _TerminalCard(
                              terminal: pos.terminals[i],
                              isDark: isDark,
                              onTap: () => _handleTap(pos.terminals[i]),
                            ),
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  void _handleTap(dynamic terminal) {
    if (terminal.hasOpenSession) {
      context.read<POSProvider>().loadSession(terminal.openSessionId);
      Navigator.pushNamed(context, AppRoutes.posMain);
    } else {
      _showOpenDialog(terminal);
    }
  }

  void _showOpenDialog(dynamic terminal) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final balanceCtrl = TextEditingController(text: '0');

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
        child: Container(
          decoration: BoxDecoration(
            color: isDark ? MColors.darkSurface : MColors.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36, height: 4,
                  decoration: BoxDecoration(
                    color: isDark ? MColors.darkBorder : MColors.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text('Open Session', style: TextStyle(
                  fontSize: 16, fontWeight: FontWeight.w700,
                  color: isDark ? MColors.darkText : MColors.text)),
              const SizedBox(height: 4),
              Text(terminal.name, style: TextStyle(
                  fontSize: 13, color: isDark ? MColors.darkTextSub : MColors.textSub)),
              const SizedBox(height: 16),
              Text('Opening balance', style: TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w600,
                  color: isDark ? MColors.darkTextSub : MColors.textSub)),
              const SizedBox(height: 8),
              TextFormField(
                controller: balanceCtrl,
                keyboardType: TextInputType.number,
                style: TextStyle(fontSize: 14, color: isDark ? MColors.darkText : MColors.text),
                decoration: const InputDecoration(isDense: true,
                    contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 12)),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Cancel'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () async {
                        Navigator.pop(context);
                        final ok = await context.read<POSProvider>()
                            .openSession(terminal.id, balanceCtrl.text);
                        if (ok && mounted) {
                          Navigator.pushNamed(context, AppRoutes.posMain);
                        }
                      },
                      child: const Text('Open Session',
                          style: TextStyle(fontWeight: FontWeight.w600)),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TerminalCard extends StatelessWidget {
  final dynamic terminal;
  final bool isDark;
  final VoidCallback onTap;
  const _TerminalCard({required this.terminal, required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final hasSession = terminal.hasOpenSession as bool;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isDark ? MColors.darkSurface : MColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
        ),
        child: Row(
          children: [
            Container(
              width: 44, height: 44,
              decoration: BoxDecoration(
                color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(Icons.point_of_sale_outlined, size: 22,
                  color: isDark ? MColors.darkPrimary : MColors.primary),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(terminal.name, style: TextStyle(
                      fontSize: 14, fontWeight: FontWeight.w700,
                      color: isDark ? MColors.darkText : MColors.text)),
                  const SizedBox(height: 2),
                  Text(terminal.location.isNotEmpty ? terminal.location : terminal.code,
                      style: TextStyle(fontSize: 12,
                          color: isDark ? MColors.darkTextSub : MColors.textSub)),
                ],
              ),
            ),
            if (hasSession)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: sem.successContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(terminal.openSessionNumber ?? 'Open',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700,
                        color: sem.success)),
              )
            else
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text('Open', style: TextStyle(
                    fontSize: 11, fontWeight: FontWeight.w600,
                    color: isDark ? MColors.darkPrimary : MColors.primary)),
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
      child: Column(children: List.generate(4, (_) => Container(
        height: 80, margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(16)),
      ))),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty();
  @override
  Widget build(BuildContext context) => Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.point_of_sale_outlined, size: 56,
          color: AppTheme.semantics(context).textFaint),
      const SizedBox(height: 12),
      Text('No terminals available',
          style: TextStyle(color: AppTheme.semantics(context).textSub)),
    ]),
  );
}
