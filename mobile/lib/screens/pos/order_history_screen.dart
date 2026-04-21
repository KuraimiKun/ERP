import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/pos_provider.dart';

class OrderHistoryScreen extends StatelessWidget {
  const OrderHistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final pos = context.watch<POSProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final sem = AppTheme.semantics(context);

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
                  Text('Order History', style: TextStyle(
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
                  : pos.orderHistory.isEmpty
                      ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                          Icon(Icons.receipt_long_outlined, size: 56,
                              color: sem.textFaint),
                          const SizedBox(height: 12),
                          Text('No orders yet',
                              style: TextStyle(color: sem.textSub)),
                        ]))
                      : ListView.builder(
                          padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                          itemCount: pos.orderHistory.length,
                          itemBuilder: (ctx, i) {
                            final order = pos.orderHistory[i];
                            final isComplete = order.status == 'completed';
                            final dateStr = order.orderDate.contains('T')
                                ? order.orderDate.split('T')[0] : order.orderDate;

                            return GestureDetector(
                              onTap: () => Navigator.pushNamed(ctx,
                                  AppRoutes.posReceipt, arguments: order.id),
                              child: Container(
                                margin: const EdgeInsets.only(bottom: 8),
                                padding: const EdgeInsets.all(14),
                                decoration: BoxDecoration(
                                  color: isDark ? MColors.darkSurface : MColors.surface,
                                  borderRadius: BorderRadius.circular(14),
                                  border: Border.all(
                                      color: isDark ? MColors.darkBorder : MColors.border,
                                      width: 0.5),
                                ),
                                child: Row(
                                  children: [
                                    Container(
                                      width: 40, height: 40,
                                      decoration: BoxDecoration(
                                        color: isComplete ? sem.successContainer : sem.warningContainer,
                                        borderRadius: BorderRadius.circular(10),
                                      ),
                                      child: Icon(
                                        isComplete ? Icons.check_circle_outline_rounded
                                            : Icons.pending_outlined,
                                        size: 20,
                                        color: isComplete ? sem.success : sem.warning,
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text('#${order.orderNumber}',
                                              style: TextStyle(
                                                  fontSize: 14, fontWeight: FontWeight.w700,
                                                  color: isDark ? MColors.darkText : MColors.text)),
                                          const SizedBox(height: 2),
                                          Text(
                                            order.customerName != null && order.customerName!.isNotEmpty
                                                ? '$dateStr · ${order.customerName}'
                                                : dateStr,
                                            style: TextStyle(fontSize: 12,
                                                color: isDark ? MColors.darkTextSub : MColors.textSub),
                                          ),
                                        ],
                                      ),
                                    ),
                                    Text(order.totalAmount, style: TextStyle(
                                        fontSize: 15, fontWeight: FontWeight.w700,
                                        color: isDark ? MColors.darkText : MColors.text)),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
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
      child: Column(children: List.generate(5, (_) => Container(
        height: 70, margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(14)),
      ))),
    );
  }
}
