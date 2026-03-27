"""
Inventory & Warehouse Management – Service Layer

Covers:
  - record_stock_movement      (single source of truth for all qty changes)
  - confirm_goods_receipt       (GRN → movements + PO update)
  - ship_stock_transfer         (dispatch → in-transit movements)
  - receive_stock_transfer      (arrival → receive movements)
  - approve_stock_adjustment    (apply gain/loss movements)
  - complete_cycle_count        (post variance as adjustment)
  - complete_pick_list          (allocate & issue stock)
  - ship_shipment               (mark shipped)
  - get_reorder_suggestions     (compare stock vs rules)
  - get_stock_summary_by_*      (warehouse/product aggregation)

Legacy helpers (kept for backward compat):
  - adjust_inventory_for_invoice
  - adjust_inventory_for_purchase_order
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from tenants.routers import get_current_db_alias

from erp.models import (
    StockItem,
    StockMovement,
    GoodsReceiptNote,
    StockTransfer,
    StockAdjustment,
    StockAdjustmentLine,
    CycleCount,
    PickList,
    ShipmentNote,
    ReorderRule,
    Product,
    PurchaseOrder,
)


# =========================================================================
# Legacy helpers (kept for backward-compatible call sites)
# =========================================================================

def adjust_inventory_for_invoice(invoice, direction='out'):
    """
    Adjust inventory when an invoice is created.

    direction='out'  → decrement stock (sales invoice)
    direction='in'   → increment stock (credit note / return)
    """
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
    db_alias = get_current_db_alias()

    with transaction.atomic(using=db_alias):
        for line in purchase_order.lines.select_related('product').all():
            if line.received_quantity and line.received_quantity > 0:
                continue
            if line.product and line.product.track_inventory:
                product = Product.objects.using(db_alias).select_for_update().get(pk=line.product.pk)
                qty = Decimal(str(line.quantity))
                product.quantity_on_hand += qty
                product.save(using=db_alias, update_fields=['quantity_on_hand'])
                line.received_quantity = line.quantity
                line.save(using=db_alias, update_fields=['received_quantity'])


# =========================================================================
# Helper – ensure a StockItem row exists
# =========================================================================

def _get_or_create_stock_item(company, product, warehouse, bin=None, lot=None, db_alias=None):
    """Return existing or fresh StockItem for the given composite key."""
    db = db_alias or get_current_db_alias()
    item, _ = StockItem.objects.using(db).get_or_create(
        company=company,
        product=product,
        warehouse=warehouse,
        bin=bin,
        lot=lot,
        defaults={'on_hand': 0, 'allocated': 0, 'in_transit': 0, 'unit_cost': 0},
    )
    return item


# =========================================================================
# Core: record_stock_movement
# =========================================================================

def record_stock_movement(
    *,
    company,
    product,
    warehouse,
    movement_type,
    quantity,
    unit_cost=Decimal('0'),
    bin=None,
    lot=None,
    reference_type='',
    reference_id=None,
    reference_number='',
    description='',
    user=None,
    db_alias=None,
):
    """
    Single source of truth for **all** inventory quantity changes.

    Creates a StockMovement row and updates the corresponding StockItem.
    Always called inside an outer ``transaction.atomic(using=db_alias)``.
    """
    db = db_alias or get_current_db_alias()
    total_cost = quantity * unit_cost

    movement = StockMovement.objects.using(db).create(
        company=company,
        movement_date=timezone.now(),
        movement_type=movement_type,
        product=product,
        warehouse=warehouse,
        bin=bin,
        lot=lot,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_number=reference_number,
        description=description,
        performed_by=user,
    )

    # Update StockItem
    stock = _get_or_create_stock_item(company, product, warehouse, bin, lot, db)

    if movement.is_inbound:
        # Weighted average cost recalculation
        if unit_cost > 0 and (stock.on_hand + quantity) > 0:
            old_total = stock.on_hand * stock.unit_cost
            new_total = old_total + total_cost
            stock.unit_cost = new_total / (stock.on_hand + quantity)
        stock.on_hand += quantity
    else:
        stock.on_hand -= quantity

    stock.save(using=db, update_fields=['on_hand', 'unit_cost', 'updated_at'])

    # Keep Product.quantity_on_hand in sync (aggregate across all warehouses)
    _sync_product_on_hand(product, company, db)

    return movement


def _sync_product_on_hand(product, company, db_alias):
    """Re-aggregate on_hand from all StockItems into Product.quantity_on_hand."""
    total = (
        StockItem.objects.using(db_alias)
        .filter(company=company, product=product)
        .aggregate(total=Coalesce(Sum('on_hand'), Decimal('0')))
    )['total']
    Product.objects.using(db_alias).filter(pk=product.pk).update(quantity_on_hand=total)


# =========================================================================
# Goods Receipt Note
# =========================================================================

def confirm_goods_receipt(grn_id, user):
    """
    Confirm a draft GRN:
      1. Create purchase_receipt movements for each accepted line
      2. Update PurchaseOrderLine.received_quantity
      3. Set PO status to partial/received as appropriate
      4. Mark GRN confirmed
      5. Trigger accounting hook
    """
    db = get_current_db_alias()
    grn = GoodsReceiptNote.objects.using(db).select_related(
        'company', 'purchase_order', 'warehouse',
    ).get(pk=grn_id)

    if grn.status != GoodsReceiptNote.Status.DRAFT:
        raise ValueError('GRN is not in Draft status')

    if grn.purchase_order and grn.purchase_order.status != PurchaseOrder.Status.APPROVED:
        raise ValueError(
            f'لا يمكن تأكيد استلام البضاعة لأمر الشراء {grn.purchase_order.po_number} '
            'لأنه غير معتمد. يجب اعتماد أمر الشراء أولاً.'
        )

    lines = grn.lines.select_related('product', 'po_line', 'bin', 'lot').using(db)

    with transaction.atomic(using=db):
        for line in lines:
            qty = line.quantity_accepted or line.quantity_received
            if qty <= 0:
                continue

            record_stock_movement(
                company=grn.company,
                product=line.product,
                warehouse=grn.warehouse,
                movement_type=StockMovement.MovementType.PURCHASE_RECEIPT,
                quantity=qty,
                unit_cost=line.unit_cost,
                bin=line.bin,
                lot=line.lot,
                reference_type='goods_receipt',
                reference_id=grn.pk,
                reference_number=grn.grn_number,
                description=f'GRN {grn.grn_number} – {line.product.sku}',
                user=user,
                db_alias=db,
            )

            # Update PO line received_quantity
            if line.po_line:
                line.po_line.received_quantity += qty
                line.po_line.save(using=db, update_fields=['received_quantity'])

        # Update PO status
        po = grn.purchase_order
        po_lines = po.lines.using(db)
        fully_received = all(l.received_quantity >= l.quantity for l in po_lines)
        any_received = any(l.received_quantity > 0 for l in po_lines)
        if fully_received:
            po.status = PurchaseOrder.Status.RECEIVED
        elif any_received:
            po.status = PurchaseOrder.Status.PARTIAL
        po.save(using=db, update_fields=['status', 'updated_at'])

        grn.status = GoodsReceiptNote.Status.CONFIRMED
        grn.save(using=db, update_fields=['status', 'updated_at'])

    # Trigger accounting hook
    from erp.services.inventory_accounting import create_grn_journal_entry
    create_grn_journal_entry(grn, user)

    return grn


# =========================================================================
# Stock Transfer
# =========================================================================

def ship_stock_transfer(transfer_id, user):
    """Ship a draft transfer: transfer_out from source, set in-transit at dest."""
    db = get_current_db_alias()
    transfer = StockTransfer.objects.using(db).select_related(
        'company', 'from_warehouse', 'to_warehouse',
    ).get(pk=transfer_id)

    if transfer.status != StockTransfer.Status.DRAFT:
        raise ValueError('Transfer is not in Draft status')

    lines = transfer.lines.select_related('product', 'from_bin', 'to_bin', 'lot').using(db)

    with transaction.atomic(using=db):
        for line in lines:
            record_stock_movement(
                company=transfer.company,
                product=line.product,
                warehouse=transfer.from_warehouse,
                movement_type=StockMovement.MovementType.TRANSFER_OUT,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                bin=line.from_bin,
                lot=line.lot,
                reference_type='stock_transfer',
                reference_id=transfer.pk,
                reference_number=transfer.transfer_number,
                description=f'Transfer Out {transfer.transfer_number}',
                user=user,
                db_alias=db,
            )

            # Mark in-transit at destination
            dest_stock = _get_or_create_stock_item(
                transfer.company, line.product, transfer.to_warehouse,
                line.to_bin, line.lot, db,
            )
            dest_stock.in_transit += line.quantity
            dest_stock.save(using=db, update_fields=['in_transit', 'updated_at'])

        transfer.status = StockTransfer.Status.IN_TRANSIT
        transfer.shipped_date = timezone.now().date()
        transfer.save(using=db, update_fields=['status', 'shipped_date', 'updated_at'])

    return transfer


def receive_stock_transfer(transfer_id, user):
    """Receive an in-transit transfer: transfer_in at destination, clear in_transit."""
    db = get_current_db_alias()
    transfer = StockTransfer.objects.using(db).select_related(
        'company', 'from_warehouse', 'to_warehouse',
    ).get(pk=transfer_id)

    if transfer.status != StockTransfer.Status.IN_TRANSIT:
        raise ValueError('Transfer is not In Transit')

    lines = transfer.lines.select_related('product', 'to_bin', 'lot').using(db)

    with transaction.atomic(using=db):
        for line in lines:
            record_stock_movement(
                company=transfer.company,
                product=line.product,
                warehouse=transfer.to_warehouse,
                movement_type=StockMovement.MovementType.TRANSFER_IN,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                bin=line.to_bin,
                lot=line.lot,
                reference_type='stock_transfer',
                reference_id=transfer.pk,
                reference_number=transfer.transfer_number,
                description=f'Transfer In {transfer.transfer_number}',
                user=user,
                db_alias=db,
            )

            # Clear in-transit
            dest_stock = _get_or_create_stock_item(
                transfer.company, line.product, transfer.to_warehouse,
                line.to_bin, line.lot, db,
            )
            dest_stock.in_transit = max(dest_stock.in_transit - line.quantity, Decimal('0'))
            dest_stock.save(using=db, update_fields=['in_transit', 'updated_at'])

        transfer.status = StockTransfer.Status.RECEIVED
        transfer.received_date = timezone.now().date()
        transfer.save(using=db, update_fields=['status', 'received_date', 'updated_at'])

    return transfer


# =========================================================================
# Stock Adjustment
# =========================================================================

def approve_stock_adjustment(adjustment_id, user):
    """Approve a draft/pending adjustment and record gain/loss movements."""
    db = get_current_db_alias()
    adj = StockAdjustment.objects.using(db).select_related(
        'company', 'warehouse',
    ).get(pk=adjustment_id)

    if adj.status not in (StockAdjustment.Status.DRAFT, StockAdjustment.Status.PENDING_APPROVAL):
        raise ValueError('Adjustment is not in an approvable status')

    lines = adj.lines.select_related('product', 'bin', 'lot').using(db)

    movement_map = {
        StockAdjustment.AdjustmentType.GAIN: StockMovement.MovementType.ADJUSTMENT_GAIN,
        StockAdjustment.AdjustmentType.LOSS: StockMovement.MovementType.ADJUSTMENT_LOSS,
        StockAdjustment.AdjustmentType.WRITE_OFF: StockMovement.MovementType.WRITE_OFF,
        StockAdjustment.AdjustmentType.REVALUATION: StockMovement.MovementType.ADJUSTMENT_GAIN,
    }

    # Pre-validate: LOSS / WRITE_OFF must not result in negative on-hand
    outbound_types = {StockAdjustment.AdjustmentType.LOSS, StockAdjustment.AdjustmentType.WRITE_OFF}
    if adj.adjustment_type in outbound_types:
        for line in lines:
            stock = _get_or_create_stock_item(adj.company, line.product, adj.warehouse, line.bin, line.lot, db)
            if abs(line.quantity) > stock.on_hand:
                raise ValueError(
                    f'الكمية المطلوبة ({abs(line.quantity)}) للمنتج "{line.product.name}" '
                    f'تتجاوز المخزون المتاح ({stock.on_hand}). لا يمكن إنشاء مخزون سالب.'
                )

    with transaction.atomic(using=db):
        for line in lines:
            mt = movement_map.get(adj.adjustment_type, StockMovement.MovementType.ADJUSTMENT_LOSS)
            record_stock_movement(
                company=adj.company,
                product=line.product,
                warehouse=adj.warehouse,
                movement_type=mt,
                quantity=abs(line.quantity),
                unit_cost=line.unit_cost,
                bin=line.bin,
                lot=line.lot,
                reference_type='stock_adjustment',
                reference_id=adj.pk,
                reference_number=adj.adjustment_number,
                description=f'Adjustment {adj.adjustment_number} – {adj.get_adjustment_type_display()}',
                user=user,
                db_alias=db,
            )

        adj.status = StockAdjustment.Status.APPROVED
        adj.approved_by = user
        adj.approved_at = timezone.now()
        adj.save(using=db, update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    # Accounting hook
    from erp.services.inventory_accounting import create_adjustment_journal_entry
    create_adjustment_journal_entry(adj, user)

    return adj


# =========================================================================
# Cycle Count
# =========================================================================

def complete_cycle_count(cycle_count_id, user):
    """
    Complete a cycle count:
      - calculate variance per line
      - auto-create stock adjustments for variance
      - approve adjustments immediately
    """
    db = get_current_db_alias()
    cc = CycleCount.objects.using(db).select_related(
        'company', 'warehouse',
    ).get(pk=cycle_count_id)

    if cc.status not in (CycleCount.Status.PLANNED, CycleCount.Status.IN_PROGRESS):
        raise ValueError('Cycle count is not completable')

    lines = cc.lines.select_related('product', 'bin', 'lot').using(db)

    gain_lines = []
    loss_lines = []

    for line in lines:
        if line.counted_quantity is None:
            continue
        var = line.variance
        if var > 0:
            gain_lines.append(line)
        elif var < 0:
            loss_lines.append(line)

    from erp.services.sequence import SequenceService

    with transaction.atomic(using=db):
        if gain_lines:
            adj_num = SequenceService.get_next_number(cc.company, 'stock_adjustment', db_alias=db)
            gain_adj = StockAdjustment.objects.using(db).create(
                company=cc.company,
                adjustment_number=adj_num,
                adjustment_date=timezone.now().date(),
                adjustment_type=StockAdjustment.AdjustmentType.GAIN,
                warehouse=cc.warehouse,
                reason=f'Cycle count {cc.count_number} – gain variance',
                status=StockAdjustment.Status.DRAFT,
                created_by=user,
            )
            for line in gain_lines:
                StockAdjustmentLine.objects.using(db).create(
                    adjustment=gain_adj,
                    product=line.product,
                    bin=line.bin,
                    lot=line.lot,
                    quantity=line.variance,
                    unit_cost=_get_stock_unit_cost(
                        cc.company, line.product, cc.warehouse, line.bin, line.lot, db
                    ),
                )
            approve_stock_adjustment(gain_adj.pk, user)

        if loss_lines:
            adj_num = SequenceService.get_next_number(cc.company, 'stock_adjustment', db_alias=db)
            loss_adj = StockAdjustment.objects.using(db).create(
                company=cc.company,
                adjustment_number=adj_num,
                adjustment_date=timezone.now().date(),
                adjustment_type=StockAdjustment.AdjustmentType.LOSS,
                warehouse=cc.warehouse,
                reason=f'Cycle count {cc.count_number} – loss variance',
                status=StockAdjustment.Status.DRAFT,
                created_by=user,
            )
            for line in loss_lines:
                StockAdjustmentLine.objects.using(db).create(
                    adjustment=loss_adj,
                    product=line.product,
                    bin=line.bin,
                    lot=line.lot,
                    quantity=abs(line.variance),
                    unit_cost=_get_stock_unit_cost(
                        cc.company, line.product, cc.warehouse, line.bin, line.lot, db
                    ),
                )
            approve_stock_adjustment(loss_adj.pk, user)

        cc.status = CycleCount.Status.COMPLETED
        cc.variance_posted = True
        cc.save(using=db, update_fields=['status', 'variance_posted', 'updated_at'])

    return cc


def _get_stock_unit_cost(company, product, warehouse, bin, lot, db):
    """Get current unit cost for a stock item row."""
    try:
        si = StockItem.objects.using(db).get(
            company=company, product=product, warehouse=warehouse, bin=bin, lot=lot,
        )
        return si.unit_cost
    except StockItem.DoesNotExist:
        return product.cost_price


# =========================================================================
# Pick List
# =========================================================================

def complete_pick_list(pick_list_id, user):
    """Mark a pick list as fully picked: issue stock via sales_issue movements."""
    db = get_current_db_alias()
    pl = PickList.objects.using(db).select_related(
        'company', 'warehouse',
    ).get(pk=pick_list_id)

    if pl.status not in (PickList.Status.DRAFT, PickList.Status.IN_PROGRESS):
        raise ValueError('Pick list is not completable')

    lines = pl.lines.select_related('product', 'from_bin', 'lot').using(db)

    with transaction.atomic(using=db):
        for line in lines:
            qty = line.quantity_picked or line.quantity_requested
            if qty <= 0:
                continue

            record_stock_movement(
                company=pl.company,
                product=line.product,
                warehouse=pl.warehouse,
                movement_type=StockMovement.MovementType.SALES_ISSUE,
                quantity=qty,
                unit_cost=_get_stock_unit_cost(
                    pl.company, line.product, pl.warehouse,
                    line.from_bin, line.lot, db,
                ),
                bin=line.from_bin,
                lot=line.lot,
                reference_type='pick_list',
                reference_id=pl.pk,
                reference_number=pl.pick_number,
                description=f'Pick {pl.pick_number} – {line.product.sku}',
                user=user,
                db_alias=db,
            )

        pl.status = PickList.Status.PICKED
        pl.save(using=db, update_fields=['status', 'updated_at'])

    # Accounting hook for COGS
    from erp.services.inventory_accounting import create_sales_issue_journal_entry
    create_sales_issue_journal_entry(pl, user)

    return pl


# =========================================================================
# Shipment
# =========================================================================

def ship_shipment(shipment_id, user):
    """Mark shipment as shipped. Stock was already issued via pick list."""
    db = get_current_db_alias()
    ship = ShipmentNote.objects.using(db).get(pk=shipment_id)

    if ship.status != ShipmentNote.Status.DRAFT:
        raise ValueError('Shipment is not in Draft status')

    ship.status = ShipmentNote.Status.SHIPPED
    ship.save(using=db, update_fields=['status', 'updated_at'])
    return ship


# =========================================================================
# Reorder Suggestions
# =========================================================================

def get_reorder_suggestions(company):
    """
    Return list of dicts for products that need reordering
    based on ReorderRules.
    """
    db = get_current_db_alias()
    rules = (
        ReorderRule.objects.using(db)
        .filter(company=company, is_active=True)
        .select_related('product', 'warehouse', 'preferred_supplier')
    )

    suggestions = []
    for rule in rules:
        stock = (
            StockItem.objects.using(db)
            .filter(company=company, product=rule.product, warehouse=rule.warehouse)
            .values('product')
            .annotate(
                total_on_hand=Sum('on_hand'),
                total_allocated=Sum('allocated'),
            )
            .first()
        )
        on_hand = (stock['total_on_hand'] or Decimal('0')) if stock else Decimal('0')
        allocated = (stock['total_allocated'] or Decimal('0')) if stock else Decimal('0')
        available = on_hand - allocated

        if available <= rule.reorder_point:
            order_qty = max(rule.min_order_qty, rule.reorder_point + rule.safety_stock - available)
            if rule.max_order_qty and order_qty > rule.max_order_qty:
                order_qty = rule.max_order_qty
            suggestions.append({
                'product': rule.product,
                'warehouse': rule.warehouse,
                'available': available,
                'reorder_point': rule.reorder_point,
                'suggested_qty': order_qty,
                'preferred_supplier': rule.preferred_supplier or rule.product.supplier,
                'lead_time_days': rule.lead_time_days,
            })

    return suggestions


# =========================================================================
# Stock Summary Queries
# =========================================================================

def get_stock_summary_by_warehouse(company, warehouse_id=None):
    """Aggregate stock quantities grouped by warehouse."""
    db = get_current_db_alias()
    qs = StockItem.objects.using(db).filter(company=company)
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    return (
        qs.values('warehouse__code', 'warehouse__name')
        .annotate(
            total_on_hand=Coalesce(Sum('on_hand'), Decimal('0')),
            total_allocated=Coalesce(Sum('allocated'), Decimal('0')),
            total_in_transit=Coalesce(Sum('in_transit'), Decimal('0')),
        )
        .order_by('warehouse__code')
    )


def get_stock_summary_by_product(company, product_id=None):
    """Aggregate stock quantities grouped by product."""
    db = get_current_db_alias()
    qs = StockItem.objects.using(db).filter(company=company)
    if product_id:
        qs = qs.filter(product_id=product_id)
    return (
        qs.values('product__sku', 'product__name')
        .annotate(
            total_on_hand=Coalesce(Sum('on_hand'), Decimal('0')),
            total_allocated=Coalesce(Sum('allocated'), Decimal('0')),
            total_in_transit=Coalesce(Sum('in_transit'), Decimal('0')),
        )
        .order_by('product__sku')
    )
