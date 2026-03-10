import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../providers/pos_provider.dart';

class PaymentScreen extends StatefulWidget {
  final int orderId;
  final double totalAmount;

  const PaymentScreen({
    super.key,
    required this.orderId,
    required this.totalAmount,
  });

  @override
  State<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends State<PaymentScreen> {
  final _tenderedController = TextEditingController();
  int? _selectedMethodId;
  bool _processing = false;

  @override
  void dispose() {
    _tenderedController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final pos = context.watch<POSProvider>();
    final tendered = double.tryParse(_tenderedController.text) ?? 0;
    final change = tendered - widget.totalAmount;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.checkout)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Total
            Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    Text(l10n.total,
                        style: TextStyle(
                            fontSize: 16, color: Colors.grey[600])),
                    const SizedBox(height: 8),
                    Text(
                      widget.totalAmount.toStringAsFixed(2),
                      style: TextStyle(
                        fontSize: 36,
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).primaryColor,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Payment method selection
            Text(l10n.paymentMethod,
                style: const TextStyle(
                    fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: pos.paymentMethods.map((method) {
                final isSelected = _selectedMethodId == method.id;
                return ChoiceChip(
                  label: Text(method.name),
                  selected: isSelected,
                  onSelected: (_) =>
                      setState(() => _selectedMethodId = method.id),
                );
              }).toList(),
            ),
            const SizedBox(height: 16),

            // Amount tendered
            TextField(
              controller: _tenderedController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: l10n.tendered,
                prefixIcon: const Icon(Icons.attach_money),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 12),

            if (tendered > 0 && tendered >= widget.totalAmount)
              Card(
                color: Colors.green[50],
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(l10n.change,
                          style: const TextStyle(fontSize: 16)),
                      Text(
                        change.toStringAsFixed(2),
                        style: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                          color: Colors.green,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 24),

            // Quick amount buttons
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _QuickAmountButton(
                  amount: widget.totalAmount,
                  label: 'Exact',
                  onTap: () => setState(() => _tenderedController.text =
                      widget.totalAmount.toStringAsFixed(2)),
                ),
                ...[50, 100, 200, 500].map(
                  (amt) => _QuickAmountButton(
                    amount: amt.toDouble(),
                    label: '$amt',
                    onTap: () => setState(
                        () => _tenderedController.text = '$amt'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            ElevatedButton(
              onPressed: _selectedMethodId == null ||
                      tendered < widget.totalAmount ||
                      _processing
                  ? null
                  : _processPayment,
              child: _processing
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : Text(l10n.pay),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _processPayment() async {
    setState(() => _processing = true);

    final pos = context.read<POSProvider>();
    final tendered = double.tryParse(_tenderedController.text) ?? 0;

    final success = await pos.completeOrder(widget.orderId, [
      {
        'payment_method_id': _selectedMethodId,
        'amount': widget.totalAmount,
        'tendered': tendered,
      },
    ]);

    if (mounted) {
      setState(() => _processing = false);
      if (success) {
        Navigator.pushReplacementNamed(
          context,
          AppRoutes.posReceipt,
          arguments: widget.orderId,
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(pos.error ?? 'Error'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }
}

class _QuickAmountButton extends StatelessWidget {
  final double amount;
  final String label;
  final VoidCallback onTap;

  const _QuickAmountButton({
    required this.amount,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(
        minimumSize: Size.zero,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),
      child: Text(label),
    );
  }
}
