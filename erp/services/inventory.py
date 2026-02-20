"""
ERP Services - Inventory Management

Adjusts Product.quantity_on_hand when invoices are created (outbound)
or purchase orders are approved/received (inbound).
"""

from decimal import Decimal
from django.db import transaction

from tenants.routers import get_current_db_alias


def adjust_inventory_for_invoice(invoice, direction='out'):
    """
    Adjust inventory when an invoice is created.

    direction='out'  → decrement stock (sales invoice)
    direction='in'   → increment stock (credit note / return)
    """
    from erp.models import Product

    db_alias = get_current_db_alias()

    with transaction.atomic(using=db_alias):
        for line in invoice.lines.select_related('product').all():
            if line.product and line.product.track_inventory:
                product = Product.objects.using(db_alias).select_for_update().get(pk=line.product.pk)
                qty = Decimal(str(line.quantity))
                if direction == 'out':
                    product.quantity_on_hand -= qty
                else:
                    product.quantity_on_hand += qty
                product.save(using=db_alias, update_fields=['quantity_on_hand'])


def adjust_inventory_for_purchase_order(purchase_order):
    """
    Increment inventory when a purchase order is approved.
    Updates both quantity_on_hand and received_quantity on each PO line.
    Skips lines that have already been received (received_quantity > 0).
    """
    from erp.models import Product

    db_alias = get_current_db_alias()

    with transaction.atomic(using=db_alias):
        for line in purchase_order.lines.select_related('product').all():
            # Skip lines already received (avoid double-counting)
            if line.received_quantity and line.received_quantity > 0:
                continue
            if line.product and line.product.track_inventory:
                product = Product.objects.using(db_alias).select_for_update().get(pk=line.product.pk)
                qty = Decimal(str(line.quantity))
                product.quantity_on_hand += qty
                product.save(using=db_alias, update_fields=['quantity_on_hand'])

                # Mark the PO line as received
                line.received_quantity = line.quantity
                line.save(using=db_alias, update_fields=['received_quantity'])
