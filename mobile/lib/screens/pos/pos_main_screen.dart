import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/pos_provider.dart';
import '../../widgets/loading_indicator.dart';

class POSMainScreen extends StatefulWidget {
  const POSMainScreen({super.key});

  @override
  State<POSMainScreen> createState() => _POSMainScreenState();
}

class _POSMainScreenState extends State<POSMainScreen> {
  final _searchController = TextEditingController();
  int? _selectedCategoryId;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final pos = context.read<POSProvider>();
      pos.loadProducts();
      pos.loadCategories();
      pos.loadPaymentMethods();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final pos = context.watch<POSProvider>();
    final session = pos.currentSession;
    final cs = Theme.of(context).colorScheme;
    final sem = AppTheme.semantics(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(session?.terminalName ?? l10n.pos),
        actions: [
          // Stats
          IconButton(
            icon: const Icon(Icons.bar_chart),
            tooltip: l10n.myPerformance,
            onPressed: () {
              Navigator.pushNamed(context, AppRoutes.posStats);
            },
          ),
          // Order history
          IconButton(
            icon: const Icon(Icons.history),
            onPressed: session != null
                ? () {
                    pos.loadOrderHistory(session.id);
                    Navigator.pushNamed(context, AppRoutes.posOrderHistory);
                  }
                : null,
          ),
          // Close session
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: session != null
                ? () => _showCloseSessionDialog(session.id)
                : null,
          ),
        ],
      ),
      body: Column(
        children: [
          // Search bar
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: l10n.search,
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          pos.loadProducts();
                        },
                      )
                    : null,
                isDense: true,
              ),
              onSubmitted: (q) =>
                  pos.loadProducts(query: q, categoryId: _selectedCategoryId),
            ),
          ),

          // Category chips
          if (pos.categories.isNotEmpty)
            SizedBox(
              height: 40,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                children: [
                  Padding(
                    padding: const EdgeInsetsDirectional.only(end: 8),
                    child: ChoiceChip(
                      label: Text(l10n.categories),
                      selected: _selectedCategoryId == null,
                      onSelected: (_) {
                        setState(() => _selectedCategoryId = null);
                        pos.loadProducts(query: _searchController.text);
                      },
                    ),
                  ),
                  ...pos.categories.map(
                    (c) => Padding(
                      padding: const EdgeInsetsDirectional.only(end: 8),
                      child: ChoiceChip(
                        label: Text(c.name),
                        selected: _selectedCategoryId == c.id,
                        onSelected: (_) {
                          setState(() => _selectedCategoryId = c.id);
                          pos.loadProducts(
                            query: _searchController.text,
                            categoryId: c.id,
                          );
                        },
                      ),
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 8),

          // Products grid
          Expanded(
            child: pos.isLoading
                ? LoadingIndicator(message: l10n.loading)
                : pos.products.isEmpty
                    ? Center(child: Text(l10n.noData))
                    : GridView.builder(
                        padding: const EdgeInsets.all(12),
                        gridDelegate:
                            const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          childAspectRatio: 0.85,
                          crossAxisSpacing: 8,
                          mainAxisSpacing: 8,
                        ),
                        itemCount: pos.products.length,
                        itemBuilder: (context, index) {
                          final product = pos.products[index];
                          return Card(
                            clipBehavior: Clip.antiAlias,
                            child: InkWell(
                              onTap: () => pos.addToCart(product),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // Product image or placeholder
                                  Expanded(
                                    child: Container(
                                      width: double.infinity,
                                      color: cs.surfaceContainerLow,
                                      child: product.imageUrl.isNotEmpty
                                          ? Image.network(
                                              product.imageUrl,
                                              fit: BoxFit.cover,
                                              errorBuilder: (_, __, ___) =>
                                                  Icon(
                                                Icons.inventory_2_outlined,
                                                size: 40,
                                                color: sem.textMuted,
                                              ),
                                            )
                                          : Icon(
                                              Icons.inventory_2_outlined,
                                              size: 40,
                                              color: sem.textMuted,
                                            ),
                                    ),
                                  ),
                                  Padding(
                                    padding: const EdgeInsets.all(8),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          product.name,
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: const TextStyle(
                                              fontWeight: FontWeight.w600,
                                              fontSize: 13),
                                        ),
                                        const SizedBox(height: 2),
                                        Text(
                                          product.sellingPrice,
                                          style: TextStyle(
                                            color: cs.primary,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),

      // Cart FAB
      floatingActionButton: pos.cart.isNotEmpty
          ? FloatingActionButton.extended(
              onPressed: () => _showCartSheet(),
              icon: const Icon(Icons.shopping_cart),
              label: Text('${pos.cartItemCount} - ${pos.cartTotal.toStringAsFixed(2)}'),
            )
          : null,
    );
  }

  void _showCartSheet() {
    final l10n = AppLocalizations.of(context)!;
    final pos = context.read<POSProvider>();
    final cs = Theme.of(context).colorScheme;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.4,
        maxChildSize: 0.9,
        expand: false,
        builder: (_, scrollController) {
          return StatefulBuilder(
            builder: (ctx, setSheetState) {
              final cartItems = pos.cart;
              return Column(
                children: [
                  // Handle
                  Container(
                    margin: const EdgeInsets.symmetric(vertical: 8),
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: cs.outlineVariant,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(l10n.cart,
                            style: const TextStyle(
                                fontSize: 18, fontWeight: FontWeight.bold)),
                        TextButton(
                          onPressed: () {
                            pos.clearCart();
                            Navigator.pop(ctx);
                          },
                          child: Text(l10n.delete,
                              style: TextStyle(color: cs.error)),
                        ),
                      ],
                    ),
                  ),
                  const Divider(),
                  // Cart items
                  Expanded(
                    child: ListView.builder(
                      controller: scrollController,
                      itemCount: cartItems.length,
                      itemBuilder: (_, i) {
                        final item = cartItems[i];
                        return ListTile(
                          title: Text(item.product.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis),
                          subtitle: Text(
                              '${item.product.sellingPrice} x ${item.quantity}'),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(Icons.remove_circle_outline),
                                onPressed: () {
                                  pos.updateCartItemQuantity(
                                      item.product.id, item.quantity - 1);
                                  setSheetState(() {});
                                },
                              ),
                              Text('${item.quantity}',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold)),
                              IconButton(
                                icon: const Icon(Icons.add_circle_outline),
                                onPressed: () {
                                  pos.updateCartItemQuantity(
                                      item.product.id, item.quantity + 1);
                                  setSheetState(() {});
                                },
                              ),
                              const SizedBox(width: 8),
                              Text(item.total.toStringAsFixed(2),
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold)),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                  // Totals
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: cs.surfaceContainerLow,
                      border: Border(
                        top: BorderSide(color: cs.outlineVariant),
                      ),
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(l10n.subtotal),
                            Text(pos.cartSubtotal.toStringAsFixed(2)),
                          ],
                        ),
                        if (pos.cartTax > 0)
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(l10n.tax),
                              Text(pos.cartTax.toStringAsFixed(2)),
                            ],
                          ),
                        const Divider(),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(l10n.total,
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 18)),
                            Text(pos.cartTotal.toStringAsFixed(2),
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 18)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton(
                            onPressed: () async {
                              Navigator.pop(ctx);
                              final order = await pos.createOrder();
                              if (order != null && mounted) {
                                Navigator.pushNamed(
                                  context,
                                  AppRoutes.posPayment,
                                  arguments: {
                                    'order_id': order.id,
                                    'total_amount': double.tryParse(
                                            order.totalAmount) ??
                                        0.0,
                                  },
                                );
                              }
                            },
                            child: Text(l10n.checkout),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }

  void _showCloseSessionDialog(int sessionId) {
    final l10n = AppLocalizations.of(context)!;
    final sem = AppTheme.semantics(context);
    final balanceController = TextEditingController(text: '0');
    final notesController = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.closeSession),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: balanceController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: l10n.closingBalance,
                prefixIcon: const Icon(Icons.attach_money),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: notesController,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Notes',
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
              final success = await pos.closeSession(
                sessionId,
                balanceController.text,
                notesController.text,
              );
              if (success && mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(l10n.sessionClosed),
                    backgroundColor: sem.success,
                  ),
                );
                Navigator.pushReplacementNamed(
                    context, AppRoutes.posTerminals);
              }
            },
            child: Text(l10n.closeSession),
          ),
        ],
      ),
    );
  }
}
