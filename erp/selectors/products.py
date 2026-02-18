"""
Selectors – Products & Product Categories
"""

from django.db.models import Q, F

from erp.models import Product, ProductCategory

__all__ = [
    'get_product_category_list',
    'get_product_list',
    'get_product_detail_context',
]


def get_product_category_list(company, *, active_only=False):
    qs = ProductCategory.objects.filter(company=company)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs


def get_product_list(
    company,
    *,
    search=None,
    category=None,
    product_type=None,
    low_stock=False,
    limit=200,
):
    qs = Product.objects.filter(company=company).select_related(
        'category', 'supplier', 'currency', 'tax_rate',
    )
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(sku__icontains=search)
            | Q(barcode__icontains=search)
            | Q(name_ar__icontains=search)
        )
    if category:
        qs = qs.filter(category_id=category)
    if product_type:
        qs = qs.filter(product_type=product_type)
    if low_stock:
        qs = qs.filter(track_inventory=True, quantity_on_hand__lte=F('reorder_level'))
    return qs.order_by('name')[:limit]


def get_product_detail_context(product, limit=20):
    return {
        'suppliers': product.product_suppliers.select_related('supplier', 'currency').all(),
        'invoice_lines': (
            product.invoice_lines
            .select_related('invoice__customer')
            .order_by('-invoice__invoice_date')[:limit]
        ),
        'po_lines': (
            product.purchase_order_lines
            .select_related('purchase_order__supplier')
            .order_by('-purchase_order__po_date')[:limit]
        ),
    }
