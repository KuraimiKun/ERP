import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/pos_provider.dart';

class PaymentScreen extends StatefulWidget {
  final int orderId;
  final double totalAmount;
  const PaymentScreen({super.key, required this.orderId, required this.totalAmount});

  @override
  State<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends State<PaymentScreen> {
  final _tenderedCtrl = TextEditingController();
  int? _selectedMethodId;
  bool _processing = false;

  @override
  void dispose() {
    _tenderedCtrl.dispose();
    super.dispose();
  }

  double get _tendered => double.tryParse(_tenderedCtrl.text) ?? 0;
  double get _change => _tendered - widget.totalAmount;

  Future<void> _processPayment() async {
    setState(() => _processing = true);
    final pos = context.read<POSProvider>();
    final ok = await pos.completeOrder(widget.orderId, [
      {
        'payment_method_id': _selectedMethodId,
        'amount': widget.totalAmount,
        'tendered': _tendered,
      },
    ]);
    if (!mounted) return;
    setState(() => _processing = false);
    if (ok) {
      Navigator.pushReplacementNamed(context, AppRoutes.posReceipt,
          arguments: widget.orderId);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(pos.error ?? 'Payment failed'),
        backgroundColor: AppTheme.semantics(context).danger,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final pos = context.watch<POSProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final sem = AppTheme.semantics(context);
    final canPay = _selectedMethodId != null && _tendered >= widget.totalAmount && !_processing;

    return Scaffold(
      backgroundColor: isDark ? MColors.darkBg : MColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => Navigator.pop(context),
                    child: Icon(Icons.arrow_back_ios_new_rounded, size: 20,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const Spacer(),
                  Text('Checkout', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                children: [
                  // Total card (gradient)
                  Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft, end: Alignment.bottomRight,
                        colors: [
                          isDark ? MColors.darkPrimary : MColors.primary,
                          isDark ? MColors.darkPrimaryDeep : MColors.primaryDeep,
                        ],
                      ),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Column(
                      children: [
                        const Text('ORDER TOTAL',
                            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600,
                                color: Color(0xCCFFFFFF), letterSpacing: 0.8)),
                        const SizedBox(height: 6),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.baseline,
                          textBaseline: TextBaseline.alphabetic,
                          children: [
                            Text(widget.totalAmount.toStringAsFixed(2),
                                style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w700,
                                    color: Colors.white, letterSpacing: -0.8)),
                            const SizedBox(width: 6),
                            const Text('SAR', style: TextStyle(fontSize: 15,
                                fontWeight: FontWeight.w600, color: Color(0xCCFFFFFF))),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Payment method
                  _Label('Payment method', isDark: isDark),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8, runSpacing: 8,
                    children: pos.paymentMethods.map((m) {
                      final sel = _selectedMethodId == m.id;
                      return GestureDetector(
                        onTap: () => setState(() => _selectedMethodId = m.id),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                          decoration: BoxDecoration(
                            color: sel
                                ? (isDark ? MColors.darkPrimary : MColors.primary)
                                : (isDark ? MColors.darkSurface : MColors.surface),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(
                              color: sel
                                  ? (isDark ? MColors.darkPrimary : MColors.primary)
                                  : (isDark ? MColors.darkBorder : MColors.border),
                              width: sel ? 1.5 : 0.5,
                            ),
                          ),
                          child: Text(m.name, style: TextStyle(
                              fontSize: 13, fontWeight: FontWeight.w600,
                              color: sel ? Colors.white
                                  : (isDark ? MColors.darkText : MColors.text))),
                        ),
                      );
                    }).toList(),
                  ),

                  const SizedBox(height: 16),

                  // Amount tendered
                  _Label('Amount tendered', isDark: isDark),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _tenderedCtrl,
                    keyboardType: TextInputType.number,
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700,
                        color: isDark ? MColors.darkText : MColors.text),
                    decoration: const InputDecoration(
                      isDense: true,
                      contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                      suffix: Text('SAR', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
                    ),
                    onChanged: (_) => setState(() {}),
                  ),

                  // Change
                  if (_tendered > 0 && _tendered >= widget.totalAmount) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: BoxDecoration(
                        color: sem.successContainer,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(children: [
                            Icon(Icons.keyboard_return_rounded, size: 14, color: sem.success),
                            const SizedBox(width: 8),
                            Text('Change', style: TextStyle(
                                fontSize: 14, fontWeight: FontWeight.w600, color: sem.success)),
                          ]),
                          Text('${_change.toStringAsFixed(2)} SAR', style: TextStyle(
                              fontSize: 18, fontWeight: FontWeight.w700, color: sem.success)),
                        ],
                      ),
                    ),
                  ],

                  const SizedBox(height: 16),

                  // Quick amount chips
                  _Label('Quick amounts', isDark: isDark),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8, runSpacing: 8,
                    children: [
                      _QuickChip(
                        label: 'Exact',
                        isDark: isDark,
                        onTap: () => setState(() =>
                            _tenderedCtrl.text = widget.totalAmount.toStringAsFixed(2)),
                      ),
                      ...[50, 100, 200, 500].map((amt) => _QuickChip(
                        label: '$amt',
                        isDark: isDark,
                        onTap: () => setState(() => _tenderedCtrl.text = '$amt'),
                      )),
                    ],
                  ),

                  const SizedBox(height: 24),

                  SizedBox(
                    height: 52,
                    child: ElevatedButton(
                      onPressed: canPay ? _processPayment : null,
                      child: _processing
                          ? const SizedBox(width: 20, height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('Complete payment',
                              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Label extends StatelessWidget {
  final String label;
  final bool isDark;
  const _Label(this.label, {required this.isDark});

  @override
  Widget build(BuildContext context) => Text(label, style: TextStyle(
      fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.1,
      color: isDark ? MColors.darkTextMid : MColors.textMid));
}

class _QuickChip extends StatelessWidget {
  final String label;
  final bool isDark;
  final VoidCallback onTap;
  const _QuickChip({required this.label, required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isDark ? MColors.darkSurface : MColors.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
        ),
        child: Text(label, style: TextStyle(
            fontSize: 13, fontWeight: FontWeight.w600,
            color: isDark ? MColors.darkText : MColors.text)),
      ),
    );
  }
}
