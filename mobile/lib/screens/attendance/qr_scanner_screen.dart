import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/attendance_provider.dart';

class QRScannerScreen extends StatefulWidget {
  const QRScannerScreen({super.key});

  @override
  State<QRScannerScreen> createState() => _QRScannerScreenState();
}

class _QRScannerScreenState extends State<QRScannerScreen> {
  final MobileScannerController _controller = MobileScannerController();
  bool _processing = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (_processing) return;
    final barcode = capture.barcodes.firstOrNull;
    if (barcode == null || barcode.rawValue == null) return;

    setState(() => _processing = true);
    _controller.stop();

    final l10n = AppLocalizations.of(context)!;
    final provider = context.read<AttendanceProvider>();
    final result = await provider.scanQR(barcode.rawValue!);

    if (!mounted) return;

    if (result != null && result.success) {
      final action = result.action == 'check_in'
          ? l10n.scanCheckIn
          : l10n.scanCheckOut;

      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (ctx) => AlertDialog(
          icon: Icon(Icons.check_circle,
              color: AppTheme.semantics(ctx).success, size: 48),
          title: Text(l10n.scanSuccess),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(action),
              if (result.attendance.isLate) ...[
                const SizedBox(height: 8),
                Text(
                  '${l10n.late}: ${result.attendance.lateMinutes} ${l10n.lateMinutes}',
                  style: TextStyle(color: AppTheme.semantics(ctx).danger),
                ),
              ],
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                Navigator.pop(context);
              },
              child: Text(l10n.ok),
            ),
          ],
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(provider.error ?? l10n.error),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
      setState(() => _processing = false);
      _controller.start();
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.scanQR)),
      body: Stack(
        children: [
          MobileScanner(
            controller: _controller,
            onDetect: _onDetect,
          ),
          // Scan overlay
          Center(
            child: Container(
              width: 250,
              height: 250,
              decoration: BoxDecoration(
                border: Border.all(color: Theme.of(context).colorScheme.onPrimary, width: 2),
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
          // Bottom instruction
          Positioned(
            bottom: 60,
            left: 0,
            right: 0,
            child: Text(
              l10n.scanQR,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          if (_processing)
            Container(
              color: Colors.black54,
              child: Center(
                child: CircularProgressIndicator(color: Theme.of(context).colorScheme.onPrimary),
              ),
            ),
        ],
      ),
    );
  }
}
