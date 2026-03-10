import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../providers/pos_provider.dart';
import '../../widgets/loading_indicator.dart';
import '../../widgets/empty_state.dart';

class OrderHistoryScreen extends StatelessWidget {
  const OrderHistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final pos = context.watch<POSProvider>();

    return Scaffold(
      appBar: AppBar(title: Text(l10n.orderHistory)),
      body: pos.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : pos.orderHistory.isEmpty
              ? EmptyState(
                  icon: Icons.receipt_long_outlined,
                  message: l10n.noData,
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: pos.orderHistory.length,
                  itemBuilder: (context, index) {
                    final order = pos.orderHistory[index];
                    return Card(
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: order.status == 'completed'
                              ? Colors.green[50]
                              : Colors.orange[50],
                          child: Icon(
                            order.status == 'completed'
                                ? Icons.check_circle
                                : Icons.pending,
                            color: order.status == 'completed'
                                ? Colors.green
                                : Colors.orange,
                          ),
                        ),
                        title: Text('#${order.orderNumber}'),
                        subtitle: Text(
                          '${order.orderDate.split('T')[0]}${order.customerName != null && order.customerName!.isNotEmpty ? ' - ${order.customerName}' : ''}',
                        ),
                        trailing: Text(
                          order.totalAmount,
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        onTap: () => Navigator.pushNamed(
                          context,
                          AppRoutes.posReceipt,
                          arguments: order.id,
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}
