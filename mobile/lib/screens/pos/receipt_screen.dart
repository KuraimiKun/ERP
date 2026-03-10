import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../providers/pos_provider.dart';
import '../../models/pos/order.dart';
import '../../widgets/loading_indicator.dart';

class ReceiptScreen extends StatefulWidget {
  final int orderId;

  const ReceiptScreen({super.key, required this.orderId});

  @override
  State<ReceiptScreen> createState() => _ReceiptScreenState();
}

class _ReceiptScreenState extends State<ReceiptScreen> {
  POSReceipt? _receipt;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadReceipt();
  }

  Future<void> _loadReceipt() async {
    final pos = context.read<POSProvider>();
    final receipt = await pos.loadReceipt(widget.orderId);
    if (mounted) {
      setState(() {
        _receipt = receipt;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.receipt)),
      body: _loading
          ? LoadingIndicator(message: l10n.loading)
          : _receipt == null
              ? Center(child: Text(l10n.error))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        children: [
                          // Company name
                          Text(
                            _receipt!.companyName,
                            style: const TextStyle(
                                fontSize: 20, fontWeight: FontWeight.bold),
                          ),
                          if (_receipt!.companyNameAr.isNotEmpty)
                            Text(_receipt!.companyNameAr,
                                style: const TextStyle(fontSize: 16)),
                          const SizedBox(height: 4),
                          Text(_receipt!.terminalName,
                              style: TextStyle(color: Colors.grey[600])),
                          if (_receipt!.receiptHeader.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Text(_receipt!.receiptHeader,
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(fontSize: 12)),
                            ),
                          const Divider(height: 24),

                          // Order info
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text('#${_receipt!.orderNumber}'),
                              Text(_receipt!.orderDate.split('T')[0]),
                            ],
                          ),
                          if (_receipt!.employeeName.isNotEmpty)
                            Align(
                              alignment: AlignmentDirectional.centerStart,
                              child: Text(
                                  'Cashier: ${_receipt!.employeeName}',
                                  style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey[600])),
                            ),
                          if (_receipt!.customerName.isNotEmpty)
                            Align(
                              alignment: AlignmentDirectional.centerStart,
                              child: Text(
                                  'Customer: ${_receipt!.customerName}',
                                  style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey[600])),
                            ),
                          const Divider(height: 24),

                          // Line items
                          ...(_receipt!.lines.map(
                            (line) => Padding(
                              padding: const EdgeInsets.symmetric(vertical: 4),
                              child: Row(
                                children: [
                                  Expanded(
                                    flex: 3,
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(line.productName,
                                            style: const TextStyle(
                                                fontSize: 13)),
                                        Text(
                                          '${line.quantity} x ${line.unitPrice}',
                                          style: TextStyle(
                                              fontSize: 11,
                                              color: Colors.grey[600]),
                                        ),
                                      ],
                                    ),
                                  ),
                                  Expanded(
                                    child: Text(
                                      line.lineTotal,
                                      textAlign: TextAlign.end,
                                      style: const TextStyle(fontSize: 13),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          )),
                          const Divider(height: 24),

                          // Totals
                          _TotalRow(l10n.subtotal, _receipt!.subtotal),
                          if (double.tryParse(_receipt!.discountAmount) != 0)
                            _TotalRow(l10n.discount,
                                '-${_receipt!.discountAmount}',
                                color: Colors.red),
                          if (double.tryParse(_receipt!.taxAmount) != 0)
                            _TotalRow(l10n.tax, _receipt!.taxAmount),
                          const Divider(),
                          _TotalRow(l10n.total, _receipt!.totalAmount,
                              isBold: true, fontSize: 18),
                          const SizedBox(height: 8),

                          // Payments
                          ...(_receipt!.payments.map(
                            (p) => _TotalRow(p.method, p.amount),
                          )),
                          if (_receipt!.payments.isNotEmpty &&
                              double.tryParse(
                                      _receipt!.payments.last.change) !=
                                  0)
                            _TotalRow(l10n.change,
                                _receipt!.payments.last.change),

                          if (_receipt!.receiptFooter.isNotEmpty) ...[
                            const Divider(height: 24),
                            Text(_receipt!.receiptFooter,
                                textAlign: TextAlign.center,
                                style: const TextStyle(fontSize: 12)),
                          ],
                        ],
                      ),
                    ),
                  ),
                ),
      bottomNavigationBar: _receipt != null
          ? Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        Navigator.pushNamedAndRemoveUntil(
                          context,
                          AppRoutes.posMain,
                          (route) => route.isFirst,
                        );
                      },
                      child: Text(l10n.back),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => Navigator.pushReplacementNamed(
                          context, AppRoutes.posMain),
                      child: Text(l10n.orderComplete),
                    ),
                  ),
                ],
              ),
            )
          : null,
    );
  }
}

class _TotalRow extends StatelessWidget {
  final String label;
  final String value;
  final bool isBold;
  final double fontSize;
  final Color? color;

  const _TotalRow(
    this.label,
    this.value, {
    this.isBold = false,
    this.fontSize = 14,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(
                fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
                fontSize: fontSize,
              )),
          Text(value,
              style: TextStyle(
                fontWeight: isBold ? FontWeight.bold : FontWeight.w500,
                fontSize: fontSize,
                color: color,
              )),
        ],
      ),
    );
  }
}
