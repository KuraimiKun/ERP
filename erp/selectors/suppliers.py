"""
Selectors – Suppliers & Purchase Orders
"""

from django.db.models import Q

from erp.models import Supplier, PurchaseOrder

__all__ = [
    "get_supplier_list",
    "get_supplier_detail_context",
    "get_purchase_order_list",
    "get_purchase_order_detail_context",
]


def get_supplier_list(company, *, supplier_type=None, search=None):
    qs = Supplier.objects.filter(company=company).order_by("name")
    if supplier_type:
        qs = qs.filter(supplier_type=supplier_type)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search) | Q(supplier_id__icontains=search))
    return qs


def get_supplier_detail_context(supplier, limit=10):
    return {
        "purchase_orders": supplier.purchase_orders.order_by("-po_date")[:limit],
        "invoices": supplier.invoices.order_by("-invoice_date")[:limit],
        "contacts": supplier.contacts.all(),
        "documents": supplier.documents.order_by("-created_at"),
    }


def get_purchase_order_list(company, *, status=None, limit=100):
    qs = PurchaseOrder.objects.filter(company=company).select_related("supplier", "currency")
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-po_date")[:limit]


def get_purchase_order_detail_context(order):
    return {
        "lines": order.lines.all(),
    }
