import 'package:flutter/material.dart';
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

    final provider = context.read<AttendanceProvider>();
    final result = await provider.scanQR(barcode.rawValue!);

    if (!mounted) return;

    if (result != null && result.success) {
      final isCheckIn = result.action == 'check_in';
      _showResultSheet(
        success: true,
        action: isCheckIn ? 'Checked In' : 'Checked Out',
        isLate: result.attendance.isLate,
        lateMinutes: result.attendance.lateMinutes,
      );
    } else {
      _showResultSheet(
        success: false,
        action: provider.error ?? 'Scan failed. Please try again.',
        isLate: false,
        lateMinutes: 0,
      );
    }
  }

  void _showResultSheet({
    required bool success,
    required String action,
    required bool isLate,
    required int lateMinutes,
  }) {
    final sem = AppTheme.semantics(context);
    showModalBottomSheet(
      context: context,
      isDismissible: false,
      enableDrag: false,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        decoration: const BoxDecoration(
          color: Color(0xFF111827),
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 40),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 36, height: 4,
              decoration: BoxDecoration(
                color: Colors.white24,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 20),
            Container(
              width: 56, height: 56,
              decoration: BoxDecoration(
                color: success ? sem.successContainer : sem.dangerContainer,
                shape: BoxShape.circle,
              ),
              child: Icon(
                success ? Icons.check_rounded : Icons.close_rounded,
                size: 30,
                color: success ? sem.success : sem.danger,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              success ? action : 'Scan Failed',
              style: const TextStyle(
                fontSize: 18, fontWeight: FontWeight.w700,
                color: Colors.white, letterSpacing: -0.3,
              ),
            ),
            if (success && isLate) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  color: sem.warningContainer,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.schedule_rounded, size: 14, color: sem.warning),
                    const SizedBox(width: 6),
                    Text(
                      'You are $lateMinutes minutes late',
                      style: TextStyle(fontSize: 13, color: sem.warning, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            ],
            if (!success) ...[
              const SizedBox(height: 8),
              Text(action, style: const TextStyle(color: Colors.white54, fontSize: 13)),
            ],
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(context); // close sheet
                  if (success) {
                    Navigator.pop(context); // go back
                  } else {
                    setState(() => _processing = false);
                    _controller.start();
                  }
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: success ? sem.success : MColors.primary,
                ),
                child: Text(success ? 'Done' : 'Try Again'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Camera
          MobileScanner(controller: _controller, onDetect: _onDetect),

          // Dark vignette overlay
          Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(0, -0.1),
                radius: 0.85,
                colors: [Colors.transparent, Color(0x99000000)],
              ),
            ),
          ),

          SafeArea(
            child: Column(
              children: [
                // Top bar
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: Row(
                    children: [
                      _GlassBtn(
                        icon: Icons.arrow_back_ios_new_rounded,
                        onTap: () => Navigator.pop(context),
                      ),
                      const Spacer(),
                      const Text(
                        'Scan to check in/out',
                        style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600),
                      ),
                      const Spacer(),
                      _GlassBtn(
                        icon: Icons.bolt_rounded,
                        onTap: () => _controller.toggleTorch(),
                      ),
                    ],
                  ),
                ),

                // Scanner frame — positioned in upper-mid area
                Expanded(
                  child: Center(
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 80),
                      child: _ScannerFrame(),
                    ),
                  ),
                ),

                // Instruction
                Padding(
                  padding: const EdgeInsets.only(bottom: 40),
                  child: Column(
                    children: [
                      const Text(
                        'Align QR within the frame',
                        style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600, letterSpacing: -0.3),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'The scan will trigger automatically',
                        style: TextStyle(color: Colors.white.withValues(alpha: 0.6), fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          if (_processing)
            Container(
              color: Colors.black54,
              child: const Center(
                child: CircularProgressIndicator(color: Colors.white),
              ),
            ),
        ],
      ),
    );
  }
}

class _GlassBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _GlassBtn({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 36, height: 36,
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, size: 18, color: Colors.white),
      ),
    );
  }
}

class _ScannerFrame extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const size = 240.0;
    const cornerLen = 36.0;
    const strokeW = 4.0;
    final accentColor = MColors.accent;

    return SizedBox(
      width: size, height: size,
      child: Stack(
        children: [
          // Scan line
          Positioned(
            top: size / 2 - 1, left: 16, right: 16,
            child: Container(
              height: 2,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [Colors.transparent, accentColor, Colors.transparent],
                ),
                boxShadow: [BoxShadow(color: accentColor.withValues(alpha: 0.6), blurRadius: 8)],
              ),
            ),
          ),
          // Corners
          ..._corners(size, cornerLen, strokeW, accentColor),
        ],
      ),
    );
  }

  List<Widget> _corners(double size, double len, double w, Color color) {
    return [
      // Top-left
      Positioned(top: 0, left: 0, child: _Corner(len: len, w: w, color: color, top: true, left: true)),
      // Top-right
      Positioned(top: 0, right: 0, child: _Corner(len: len, w: w, color: color, top: true, left: false)),
      // Bottom-left
      Positioned(bottom: 0, left: 0, child: _Corner(len: len, w: w, color: color, top: false, left: true)),
      // Bottom-right
      Positioned(bottom: 0, right: 0, child: _Corner(len: len, w: w, color: color, top: false, left: false)),
    ];
  }
}

class _Corner extends StatelessWidget {
  final double len, w;
  final Color color;
  final bool top, left;
  const _Corner({required this.len, required this.w, required this.color, required this.top, required this.left});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: len, height: len,
      child: CustomPaint(painter: _CornerPainter(w: w, color: color, top: top, left: left)),
    );
  }
}

class _CornerPainter extends CustomPainter {
  final double w;
  final Color color;
  final bool top, left;
  _CornerPainter({required this.w, required this.color, required this.top, required this.left});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color..strokeWidth = w..strokeCap = StrokeCap.round..style = PaintingStyle.stroke;
    final r = 12.0;
    final len = size.width;

    if (top && left) {
      canvas.drawLine(Offset(r, 0), Offset(len, 0), paint);
      canvas.drawLine(Offset(0, r), Offset(0, len), paint);
      canvas.drawArc(Rect.fromLTWH(0, 0, r * 2, r * 2), -3.14, 3.14 / 2, false, paint);
    } else if (top && !left) {
      canvas.drawLine(Offset(0, 0), Offset(len - r, 0), paint);
      canvas.drawLine(Offset(len, r), Offset(len, len), paint);
      canvas.drawArc(Rect.fromLTWH(len - r * 2, 0, r * 2, r * 2), -1.57, 1.57, false, paint);
    } else if (!top && left) {
      canvas.drawLine(Offset(0, 0), Offset(0, len - r), paint);
      canvas.drawLine(Offset(r, len), Offset(len, len), paint);
      canvas.drawArc(Rect.fromLTWH(0, len - r * 2, r * 2, r * 2), 1.57, 1.57, false, paint);
    } else {
      canvas.drawLine(Offset(len, 0), Offset(len, len - r), paint);
      canvas.drawLine(Offset(0, len), Offset(len - r, len), paint);
      canvas.drawArc(Rect.fromLTWH(len - r * 2, len - r * 2, r * 2, r * 2), 0, 1.57, false, paint);
    }
  }

  @override
  bool shouldRepaint(_CornerPainter old) => false;
}
