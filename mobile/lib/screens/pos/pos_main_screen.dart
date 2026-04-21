import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/pos_provider.dart';

class POSMainScreen extends StatefulWidget {
  const POSMainScreen({super.key});

  @override
  State<POSMainScreen> createState() => _POSMainScreenState();
}

class _POSMainScreenState extends State<POSMainScreen> {
  final _searchCtrl = TextEditingController();
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
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pos = context.watch<POSProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final session = pos.currentSession;

    return Scaffold(
      backgroundColor: isDark ? MColors.darkBg : MColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            // Top bar
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => Navigator.maybePop(context),
                    child: Icon(Icons.arrow_back_ios_new_rounded, size: 20,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(session?.terminalName ?? 'POS', style: TextStyle(
                      fontSize: 15, fontWeight: FontWeight.w700,
                      color: isDark ? MColors.darkText : MColors.text,
                    )),
                  ),
                  _TopBtn(
                    icon: Icons.bar_chart_rounded,
                    isDark: isDark,
                    onTap: () => Navigator.pushNamed(context, AppRoutes.posStats),
                  ),
                  const SizedBox(width: 8),
                  _TopBtn(
                    icon: Icons.history_rounded,
                    isDark: isDark,
                    onTap: session != null ? () {
                      pos.loadOrderHistory(session.id);
                      Navigator.pushNamed(context, AppRoutes.posOrderHistory);
                    } : null,
                  ),
                  const SizedBox(width: 8),
                  _TopBtn(
                    icon: Icons.logout_rounded,
                    isDark: isDark,
                    onTap: session != null
                        ? () => _showCloseSessionDialog(session.id) : null,
                  ),
                ],
              ),
            ),

            // Search bar
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
              child: Container(
                height: 42,
                decoration: BoxDecoration(
                  color: isDark ? MColors.darkSurfaceAlt : MColors.surfaceAlt,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
                ),
                child: TextField(
                  controller: _searchCtrl,
                  style: TextStyle(fontSize: 13,
                      color: isDark ? MColors.darkText : MColors.text),
                  decoration: InputDecoration(
                    hintText: 'Search products…',
                    hintStyle: TextStyle(fontSize: 13,
                        color: isDark ? MColors.darkTextFaint : MColors.textFaint),
                    prefixIcon: Icon(Icons.search_rounded, size: 18,
                        color: isDark ? MColors.darkTextSub : MColors.textSub),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(vertical: 12),
                    suffixIcon: _searchCtrl.text.isNotEmpty
                        ? GestureDetector(
                            onTap: () {
                              _searchCtrl.clear();
                              pos.loadProducts();
                              setState(() {});
                            },
                            child: Icon(Icons.clear_rounded, size: 16,
                                color: isDark ? MColors.darkTextSub : MColors.textSub),
                          )
                        : null,
                  ),
                  onSubmitted: (q) => pos.loadProducts(
                      query: q, categoryId: _selectedCategoryId),
                  onChanged: (_) => setState(() {}),
                ),
              ),
            ),

            // Categories
            if (pos.categories.isNotEmpty)
              SizedBox(
                height: 44,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  children: [
                    _CategoryChip(
                      label: 'All',
                      selected: _selectedCategoryId == null,
                      isDark: isDark,
                      onTap: () {
                        setState(() => _selectedCategoryId = null);
                        pos.loadProducts(query: _searchCtrl.text);
                      },
                    ),
                    ...pos.categories.map((c) => _CategoryChip(
                      label: c.name,
                      selected: _selectedCategoryId == c.id,
                      isDark: isDark,
                      onTap: () {
                        setState(() => _selectedCategoryId = c.id);
                        pos.loadProducts(query: _searchCtrl.text, categoryId: c.id);
                      },
                    )),
                  ],
                ),
              ),

            const SizedBox(height: 8),

            // Products grid
            Expanded(
              child: pos.isLoading
                  ? const _Shimmer()
                  : pos.products.isEmpty
                      ? Center(child: Text('No products',
                          style: TextStyle(color: AppTheme.semantics(context).textSub)))
                      : GridView.builder(
                          padding: const EdgeInsets.fromLTRB(16, 0, 16, 120),
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2,
                            childAspectRatio: 0.82,
                            crossAxisSpacing: 10,
                            mainAxisSpacing: 10,
                          ),
                          itemCount: pos.products.length,
                          itemBuilder: (ctx, i) => _ProductCard(
                            product: pos.products[i],
                            isDark: isDark,
                            onTap: () => pos.addToCart(pos.products[i]),
                          ),
                        ),
            ),
          ],
        ),
      ),
      floatingActionButton: pos.cart.isNotEmpty
          ? FloatingActionButton.extended(
              onPressed: () => _showCartSheet(),
              icon: const Icon(Icons.shopping_cart_outlined),
              label: Text(
                '${pos.cartItemCount} · ${pos.cartTotal.toStringAsFixed(2)} SAR',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            )
          : null,
    );
  }

  void _showCartSheet() {
    final pos = context.read<POSProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.4,
        maxChildSize: 0.92,
        expand: false,
        builder: (_, scrollCtrl) => Container(
          decoration: BoxDecoration(
            color: isDark ? MColors.darkSurface : MColors.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: StatefulBuilder(builder: (ctx, setS) => Column(
            children: [
              Center(
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 10),
                  width: 36, height: 4,
                  decoration: BoxDecoration(
                    color: isDark ? MColors.darkBorder : MColors.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: Row(
                  children: [
                    Text('Cart', style: TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w700,
                        color: isDark ? MColors.darkText : MColors.text)),
                    const Spacer(),
                    GestureDetector(
                      onTap: () {
                        pos.clearCart();
                        Navigator.pop(ctx);
                      },
                      child: Text('Clear', style: TextStyle(
                          fontSize: 13, fontWeight: FontWeight.w600,
                          color: AppTheme.semantics(context).danger)),
                    ),
                  ],
                ),
              ),
              Divider(height: 1, color: isDark ? MColors.darkBorder : MColors.border),
              Expanded(
                child: ListView.builder(
                  controller: scrollCtrl,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  itemCount: pos.cart.length,
                  itemBuilder: (_, i) {
                    final item = pos.cart[i];
                    return Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: isDark ? MColors.darkSurfaceAlt : MColors.surfaceAlt,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(item.product.name, maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                        fontSize: 13, fontWeight: FontWeight.w600,
                                        color: isDark ? MColors.darkText : MColors.text)),
                                Text('${item.product.sellingPrice} × ${item.quantity}',
                                    style: TextStyle(fontSize: 11,
                                        color: isDark ? MColors.darkTextSub : MColors.textSub)),
                              ],
                            ),
                          ),
                          Row(children: [
                            _QtyBtn(icon: Icons.remove_rounded, isDark: isDark, onTap: () {
                              pos.updateCartItemQuantity(item.product.id, item.quantity - 1);
                              setS(() {});
                            }),
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 10),
                              child: Text('${item.quantity}', style: TextStyle(
                                  fontSize: 14, fontWeight: FontWeight.w700,
                                  color: isDark ? MColors.darkText : MColors.text)),
                            ),
                            _QtyBtn(icon: Icons.add_rounded, isDark: isDark, onTap: () {
                              pos.updateCartItemQuantity(item.product.id, item.quantity + 1);
                              setS(() {});
                            }),
                          ]),
                          const SizedBox(width: 10),
                          Text(item.total.toStringAsFixed(2), style: TextStyle(
                              fontSize: 13, fontWeight: FontWeight.w700,
                              color: isDark ? MColors.darkText : MColors.text)),
                        ],
                      ),
                    );
                  },
                ),
              ),
              Container(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
                decoration: BoxDecoration(
                  color: isDark ? MColors.darkSurface : MColors.surface,
                  border: Border(top: BorderSide(
                      color: isDark ? MColors.darkBorder : MColors.border, width: 0.5)),
                ),
                child: Column(
                  children: [
                    _TotalLine('Subtotal', pos.cartSubtotal.toStringAsFixed(2), isDark: isDark),
                    if (pos.cartTax > 0)
                      _TotalLine('Tax', pos.cartTax.toStringAsFixed(2), isDark: isDark),
                    Divider(height: 14, color: isDark ? MColors.darkBorder : MColors.border),
                    _TotalLine('Total', '${pos.cartTotal.toStringAsFixed(2)} SAR',
                        isDark: isDark, bold: true, large: true),
                    const SizedBox(height: 12),
                    SizedBox(
                      height: 50, width: double.infinity,
                      child: ElevatedButton(
                        onPressed: () async {
                          Navigator.pop(ctx);
                          final order = await pos.createOrder();
                          if (order != null && mounted) {
                            Navigator.pushNamed(context, AppRoutes.posPayment,
                                arguments: {
                                  'order_id': order.id,
                                  'total_amount': double.tryParse(order.totalAmount) ?? 0.0,
                                });
                          }
                        },
                        child: const Text('Checkout',
                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          )),
        ),
      ),
    );
  }

  void _showCloseSessionDialog(int sessionId) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final balanceCtrl = TextEditingController(text: '0');
    final notesCtrl = TextEditingController();

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
              Center(child: Container(width: 36, height: 4,
                  decoration: BoxDecoration(color: isDark ? MColors.darkBorder : MColors.border,
                      borderRadius: BorderRadius.circular(2)))),
              const SizedBox(height: 16),
              Text('Close Session', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700,
                  color: isDark ? MColors.darkText : MColors.text)),
              const SizedBox(height: 16),
              _SheetLabel('Closing balance', isDark: isDark),
              const SizedBox(height: 6),
              TextFormField(controller: balanceCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(isDense: true,
                      contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 12))),
              const SizedBox(height: 12),
              _SheetLabel('Notes (optional)', isDark: isDark),
              const SizedBox(height: 6),
              TextFormField(controller: notesCtrl, maxLines: 2,
                  decoration: const InputDecoration(isDense: true,
                      contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 12))),
              const SizedBox(height: 20),
              Row(children: [
                Expanded(child: OutlinedButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                )),
                const SizedBox(width: 12),
                Expanded(child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.semantics(context).danger),
                  onPressed: () async {
                    Navigator.pop(context);
                    final ok = await context.read<POSProvider>()
                        .closeSession(sessionId, balanceCtrl.text, notesCtrl.text);
                    if (ok && mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                        content: const Text('Session closed'),
                        backgroundColor: AppTheme.semantics(context).success,
                      ));
                      Navigator.pushReplacementNamed(context, AppRoutes.posTerminals);
                    }
                  },
                  child: const Text('Close Session',
                      style: TextStyle(fontWeight: FontWeight.w600)),
                )),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}

class _TopBtn extends StatelessWidget {
  final IconData icon;
  final bool isDark;
  final VoidCallback? onTap;
  const _TopBtn({required this.icon, required this.isDark, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 34, height: 34,
        decoration: BoxDecoration(
          color: isDark ? MColors.darkSurfaceAlt : MColors.surfaceAlt,
          borderRadius: BorderRadius.circular(9),
          border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
        ),
        child: Icon(icon, size: 17,
            color: onTap != null
                ? (isDark ? MColors.darkTextMid : MColors.textMid)
                : (isDark ? MColors.darkTextFaint : MColors.textFaint)),
      ),
    );
  }
}

class _CategoryChip extends StatelessWidget {
  final String label;
  final bool selected;
  final bool isDark;
  final VoidCallback onTap;
  const _CategoryChip({required this.label, required this.selected,
      required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(right: 6),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
        decoration: BoxDecoration(
          color: selected
              ? (isDark ? MColors.darkPrimary : MColors.primary)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: selected
                ? (isDark ? MColors.darkPrimary : MColors.primary)
                : (isDark ? MColors.darkBorder : MColors.border),
            width: 0.5,
          ),
        ),
        child: Text(label, style: TextStyle(
          fontSize: 12, fontWeight: FontWeight.w600,
          color: selected ? Colors.white
              : (isDark ? MColors.darkTextMid : MColors.textMid),
        )),
      ),
    );
  }
}

class _ProductCard extends StatelessWidget {
  final dynamic product;
  final bool isDark;
  final VoidCallback onTap;
  const _ProductCard({required this.product, required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: isDark ? MColors.darkSurface : MColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Container(
                width: double.infinity,
                color: isDark ? MColors.darkSurfaceAlt : MColors.surfaceAlt,
                child: product.imageUrl.isNotEmpty
                    ? Image.network(product.imageUrl, fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Icon(Icons.inventory_2_outlined,
                            size: 36, color: isDark ? MColors.darkTextFaint : MColors.textFaint))
                    : Icon(Icons.inventory_2_outlined, size: 36,
                        color: isDark ? MColors.darkTextFaint : MColors.textFaint),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(product.name, maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600,
                          color: isDark ? MColors.darkText : MColors.text)),
                  const SizedBox(height: 2),
                  Text(product.sellingPrice, style: TextStyle(
                      fontSize: 13, fontWeight: FontWeight.w700,
                      color: isDark ? MColors.darkPrimary : MColors.primary)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QtyBtn extends StatelessWidget {
  final IconData icon;
  final bool isDark;
  final VoidCallback onTap;
  const _QtyBtn({required this.icon, required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 28, height: 28,
        decoration: BoxDecoration(
          color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(icon, size: 16, color: isDark ? MColors.darkPrimary : MColors.primary),
      ),
    );
  }
}

class _TotalLine extends StatelessWidget {
  final String label, value;
  final bool isDark, bold, large;
  const _TotalLine(this.label, this.value,
      {required this.isDark, this.bold = false, this.large = false});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: TextStyle(
            fontSize: large ? 15 : 13,
            fontWeight: bold ? FontWeight.w700 : FontWeight.normal,
            color: isDark ? MColors.darkTextMid : MColors.textMid)),
        Text(value, style: TextStyle(
            fontSize: large ? 16 : 13,
            fontWeight: bold ? FontWeight.w700 : FontWeight.w500,
            color: isDark ? MColors.darkText : MColors.text)),
      ],
    );
  }
}

class _SheetLabel extends StatelessWidget {
  final String label;
  final bool isDark;
  const _SheetLabel(this.label, {required this.isDark});

  @override
  Widget build(BuildContext context) => Text(label,
      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
          color: isDark ? MColors.darkTextSub : MColors.textSub));
}

class _Shimmer extends StatelessWidget {
  const _Shimmer();
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF1F2937) : const Color(0xFFE2E8F0);
    return GridView.count(
      crossAxisCount: 2, crossAxisSpacing: 10, mainAxisSpacing: 10,
      childAspectRatio: 0.82,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
      children: List.generate(6, (_) => Container(
        decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(14)),
      )),
    );
  }
}
