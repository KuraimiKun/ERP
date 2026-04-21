import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../models/pos/order.dart';
import '../../providers/pos_provider.dart';

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
    _load();
  }

  Future<void> _load() async {
    final r = await context.read<POSProvider>().loadReceipt(widget.orderId);
    if (mounted) setState(() { _receipt = r; _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

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
                  Text('Receipt', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 20),
                ],
              ),
            ),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _receipt == null
                      ? Center(child: Text('Could not load receipt',
                          style: TextStyle(color: AppTheme.semantics(context).textSub)))
                      : _ReceiptBody(receipt: _receipt!, isDark: isDark),
            ),
            if (_receipt != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.pushNamedAndRemoveUntil(
                            context, AppRoutes.posMain, (r) => r.isFirst),
                        child: const Text('Back to POS'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () => Navigator.pushReplacementNamed(
                            context, AppRoutes.posMain),
                        child: const Text('New order',
                            style: TextStyle(fontWeight: FontWeight.w600)),
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

class _ReceiptBody extends StatelessWidget {
  final POSReceipt receipt;
  final bool isDark;
  const _ReceiptBody({required this.receipt, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      children: [
        // Success state
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: sem.successContainer,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Column(
            children: [
              Container(
                width: 56, height: 56,
                decoration: BoxDecoration(color: sem.success, shape: BoxShape.circle),
                child: const Icon(Icons.check_rounded, size: 30, color: Colors.white),
              ),
              const SizedBox(height: 10),
              Text('Payment Successful', style: TextStyle(
                  fontSize: 17, fontWeight: FontWeight.w700, color: sem.success)),
            ],
          ),
        ),

        const SizedBox(height: 14),

        // Receipt card
        Container(
          decoration: BoxDecoration(
            color: isDark ? MColors.darkSurface : MColors.surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
          ),
          child: Column(
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                child: Column(
                  children: [
                    Text(receipt.companyName, style: TextStyle(
                        fontSize: 18, fontWeight: FontWeight.w700,
                        color: isDark ? MColors.darkText : MColors.text)),
                    if (receipt.companyNameAr.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(receipt.companyNameAr, style: TextStyle(
                          fontSize: 14, color: isDark ? MColors.darkTextSub : MColors.textSub)),
                    ],
                    const SizedBox(height: 4),
                    Text(receipt.terminalName, style: TextStyle(
                        fontSize: 12, color: isDark ? MColors.darkTextSub : MColors.textSub)),
                    if (receipt.receiptHeader.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(receipt.receiptHeader, textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 11,
                              color: isDark ? MColors.darkTextSub : MColors.textSub)),
                    ],
                  ],
                ),
              ),

              _Dashes(isDark: isDark),

              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('#${receipt.orderNumber}', style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w700,
                            color: isDark ? MColors.darkText : MColors.text)),
                        Text(receipt.orderDate.contains('T')
                            ? receipt.orderDate.split('T')[0] : receipt.orderDate,
                            style: TextStyle(fontSize: 12,
                                color: isDark ? MColors.darkTextSub : MColors.textSub)),
                      ],
                    ),
                    if (receipt.employeeName.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Align(alignment: AlignmentDirectional.centerStart,
                          child: Text('Cashier: ${receipt.employeeName}',
                              style: TextStyle(fontSize: 11,
                                  color: isDark ? MColors.darkTextSub : MColors.textSub))),
                    ],
                    if (receipt.customerName.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Align(alignment: AlignmentDirectional.centerStart,
                          child: Text('Customer: ${receipt.customerName}',
                              style: TextStyle(fontSize: 11,
                                  color: isDark ? MColors.darkTextSub : MColors.textSub))),
                    ],
                  ],
                ),
              ),

              _Dashes(isDark: isDark),

              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  children: receipt.lines.map((line) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 5),
                    child: Row(
                      children: [
                        Expanded(flex: 3, child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(line.productName, style: TextStyle(
                                fontSize: 13, fontWeight: FontWeight.w500,
                                color: isDark ? MColors.darkText : MColors.text)),
                            Text('${line.quantity} × ${line.unitPrice}', style: TextStyle(
                                fontSize: 11, color: isDark ? MColors.darkTextSub : MColors.textSub)),
                          ],
                        )),
                        Text(line.lineTotal, textAlign: TextAlign.end,
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
                                color: isDark ? MColors.darkText : MColors.text)),
                      ],
                    ),
                  )).toList(),
                ),
              ),

              _Dashes(isDark: isDark),

              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                child: Column(
                  children: [
                    _TotalRow('Subtotal', receipt.subtotal, isDark: isDark),
                    if ((double.tryParse(receipt.discountAmount) ?? 0) != 0)
                      _TotalRow('Discount', '-${receipt.discountAmount}',
                          isDark: isDark, color: sem.danger),
                    if ((double.tryParse(receipt.taxAmount) ?? 0) != 0)
                      _TotalRow('Tax', receipt.taxAmount, isDark: isDark),
                    Divider(height: 14, color: isDark ? MColors.darkBorder : MColors.border),
                    _TotalRow('Total', '${receipt.totalAmount} SAR',
                        isDark: isDark, bold: true, large: true),
                    const SizedBox(height: 8),
                    ...receipt.payments.map((p) => _TotalRow(p.method, p.amount, isDark: isDark)),
                    if (receipt.payments.isNotEmpty &&
                        (double.tryParse(receipt.payments.last.change) ?? 0) != 0)
                      _TotalRow('Change', receipt.payments.last.change, isDark: isDark),
                    if (receipt.receiptFooter.isNotEmpty) ...[
                      Divider(height: 20, color: isDark ? MColors.darkBorder : MColors.border),
                      Text(receipt.receiptFooter, textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 11,
                              color: isDark ? MColors.darkTextSub : MColors.textSub)),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Dashes extends StatelessWidget {
  final bool isDark;
  const _Dashes({required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: List.generate(30, (i) => Expanded(
          child: Container(
            height: 1,
            color: i % 2 == 0
                ? (isDark ? MColors.darkBorder : MColors.border)
                : Colors.transparent,
          ),
        )),
      ),
    );
  }
}

class _TotalRow extends StatelessWidget {
  final String label, value;
  final bool isDark, bold, large;
  final Color? color;
  const _TotalRow(this.label, this.value,
      {required this.isDark, this.bold = false, this.large = false, this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(
              fontSize: large ? 15 : 13,
              fontWeight: bold ? FontWeight.w700 : FontWeight.normal,
              color: isDark ? MColors.darkTextMid : MColors.textMid)),
          Text(value, style: TextStyle(
              fontSize: large ? 16 : 13,
              fontWeight: bold ? FontWeight.w700 : FontWeight.w500,
              color: color ?? (isDark ? MColors.darkText : MColors.text))),
        ],
      ),
    );
  }
}
