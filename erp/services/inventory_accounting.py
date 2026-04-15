"""
Inventory Accounting Hooks

Journal entry creation for inventory transactions:
  - create_grn_journal_entry          DR Inventory, CR GRNI
  - create_sales_issue_journal_entry  DR COGS, CR Inventory
  - create_adjustment_journal_entry   DR/CR Inventory ↔ Adjustment Expense
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from tenants.routers import get_current_db_alias
from erp.models import (
    JournalEntry,
    JournalEntryLine,
    InventoryValuationConfig,
)
from erp.services.accounting import (
    _get_or_create_account,
    _update_account_balances,
    _get_current_fiscal_year,
    _next_journal_number,
)

logger = logging.getLogger('erp.inventory')


# Default GL codes
_DEFAULTS = {
    'inventory': ('1500', 'Inventory', 'المخزون', 'asset'),
    'cogs': ('5100', 'Cost of Goods Sold', 'تكلفة البضاعة المباعة', 'expense'),
    'grni': ('1400', 'Goods Received Not Invoiced', 'بضاعة مستلمة بدون فاتورة', 'asset'),
    'adjustment': ('6200', 'Inventory Adjustment', 'تسوية مخزون', 'expense'),
    'write_off': ('6300', 'Inventory Write-Off', 'شطب مخزون', 'expense'),
}


def _get_valuation_account(company, account_field, default_key, db_alias):
    """
    Resolve the GL account from InventoryValuationConfig or fall back to
    the default account code.
    """
    try:
        config = InventoryValuationConfig.objects.using(db_alias).get(company=company)
        account = getattr(config, account_field, None)
        if account:
            return account
    except InventoryValuationConfig.DoesNotExist:
        logger.warning(
            'No InventoryValuationConfig found for company %s (pk=%s). '
            'Falling back to default GL account for "%s". '
            'Configure inventory valuation accounts in Settings → Inventory Valuation.',
            getattr(company, 'name', company),
            getattr(company, 'pk', '?'),
            default_key,
        )

    code, name, name_ar, atype = _DEFAULTS[default_key]
    return _get_or_create_account(company, code, name, name_ar, atype, db_alias)


# =========================================================================
# GRN Journal Entry
# =========================================================================

def create_grn_journal_entry(grn, user):
    """
    DR  Inventory (1500)           total received cost
    CR  GRNI / Accrued (1400)      total received cost

    Called after confirm_goods_receipt.
    """
    db = get_current_db_alias()
    company = grn.company

    # Calculate total received cost
    total_cost = Decimal('0')
    for line in grn.lines.using(db):
        qty = line.quantity_accepted or line.quantity_received
        total_cost += qty * line.unit_cost

    if total_cost <= 0:
        return None

    with transaction.atomic(using=db):
        inv_account = _get_valuation_account(company, 'inventory_account', 'inventory', db)
        grni_account = _get_valuation_account(company, 'grni_account', 'grni', db)
        fiscal_year = _get_current_fiscal_year(company, db)
        entry_number = _next_journal_number(company, 'GRN', db)

        journal_entry = JournalEntry.objects.using(db).create(
            company=company,
            entry_number=entry_number,
            entry_date=grn.receipt_date,
            entry_type=JournalEntry.EntryType.INVENTORY,
            description=f'استلام بضاعة {grn.grn_number} – PO {grn.purchase_order.po_number}',
            reference=grn.grn_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        # DR Inventory
        JournalEntryLine.objects.using(db).create(
            journal_entry=journal_entry,
            account=inv_account,
            description=f'مخزون – {grn.grn_number}',
            debit_amount=total_cost,
            credit_amount=Decimal('0'),
            reference_type='goods_receipt',
            reference_id=grn.pk,
        )

        # CR GRNI
        JournalEntryLine.objects.using(db).create(
            journal_entry=journal_entry,
            account=grni_account,
            description=f'بضاعة مستلمة بدون فاتورة – {grn.grn_number}',
            debit_amount=Decimal('0'),
            credit_amount=total_cost,
            reference_type='goods_receipt',
            reference_id=grn.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])
        _update_account_balances(journal_entry, db)

    return journal_entry


# =========================================================================
# Sales Issue Journal Entry (COGS)
# =========================================================================

def create_sales_issue_journal_entry(pick_list, user):
    """
    DR  COGS (5100)            total issued cost
    CR  Inventory (1500)       total issued cost

    Called after complete_pick_list.
    """
    db = get_current_db_alias()
    company = pick_list.company

    total_cost = Decimal('0')
    for line in pick_list.lines.select_related('product').using(db):
        qty = line.quantity_picked or line.quantity_requested
        # Use the cost from the stock movement or the product cost
        from erp.models import StockMovement
        mv = (
            StockMovement.objects.using(db)
            .filter(reference_type='pick_list', reference_id=pick_list.pk, product=line.product)
            .first()
        )
        cost = mv.unit_cost if mv else line.product.cost_price
        total_cost += qty * cost

    if total_cost <= 0:
        return None

    with transaction.atomic(using=db):
        cogs_account = _get_valuation_account(company, 'cogs_account', 'cogs', db)
        inv_account = _get_valuation_account(company, 'inventory_account', 'inventory', db)
        fiscal_year = _get_current_fiscal_year(company, db)
        entry_number = _next_journal_number(company, 'COGS', db)

        journal_entry = JournalEntry.objects.using(db).create(
            company=company,
            entry_number=entry_number,
            entry_date=pick_list.pick_date,
            entry_type=JournalEntry.EntryType.INVENTORY,
            description=f'تكلفة بضاعة مباعة – Pick {pick_list.pick_number}',
            reference=pick_list.pick_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        # DR COGS
        JournalEntryLine.objects.using(db).create(
            journal_entry=journal_entry,
            account=cogs_account,
            description=f'تكلفة مبيعات – {pick_list.pick_number}',
            debit_amount=total_cost,
            credit_amount=Decimal('0'),
            reference_type='pick_list',
            reference_id=pick_list.pk,
        )

        # CR Inventory
        JournalEntryLine.objects.using(db).create(
            journal_entry=journal_entry,
            account=inv_account,
            description=f'إصدار مخزون – {pick_list.pick_number}',
            debit_amount=Decimal('0'),
            credit_amount=total_cost,
            reference_type='pick_list',
            reference_id=pick_list.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])
        _update_account_balances(journal_entry, db)

    return journal_entry


# =========================================================================
# Stock Transfer Journal Entry
# =========================================================================

def create_transfer_journal_entry(transfer, user):
    """
    For inter-warehouse transfers, record the movement of inventory value.

    DR  Inventory (1500)   total_cost   [destination side]
    CR  Inventory (1500)   total_cost   [source side]

    Both sides use the same account code (single-warehouse GL). This is a
    self-balancing memo entry that makes the transfer visible in the journal
    without changing net inventory value.
    """
    from erp.models import StockMovement
    db = get_current_db_alias()
    company = transfer.company

    movements = StockMovement.objects.using(db).filter(
        reference_type='stock_transfer',
        reference_id=transfer.pk,
        movement_type=StockMovement.MovementType.TRANSFER_OUT,
    )
    total_cost = sum(m.unit_cost * m.quantity for m in movements)
    if total_cost <= Decimal('0'):
        return None

    with transaction.atomic(using=db):
        inv_account = _get_valuation_account(company, 'inventory_account', 'inventory', db)
        fiscal_year = _get_current_fiscal_year(company, db)
        entry_number = _next_journal_number(company, 'TRF', db)

        journal_entry = JournalEntry.objects.using(db).create(
            company=company,
            entry_number=entry_number,
            entry_date=transfer.received_date or timezone.now().date(),
            entry_type=JournalEntry.EntryType.INVENTORY,
            description=(
                f'تحويل مخزون {transfer.transfer_number} – '
                f'{transfer.from_warehouse.name} → {transfer.to_warehouse.name}'
            ),
            reference=transfer.transfer_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )
        JournalEntryLine.objects.using(db).create(
            journal_entry=journal_entry,
            account=inv_account,
            description=f'مخزون وارد – {transfer.to_warehouse.name}',
            debit_amount=total_cost,
            credit_amount=Decimal('0'),
            reference_type='stock_transfer',
            reference_id=transfer.pk,
        )
        JournalEntryLine.objects.using(db).create(
            journal_entry=journal_entry,
            account=inv_account,
            description=f'مخزون صادر – {transfer.from_warehouse.name}',
            debit_amount=Decimal('0'),
            credit_amount=total_cost,
            reference_type='stock_transfer',
            reference_id=transfer.pk,
        )
        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])
        _update_account_balances(journal_entry, db)

    return journal_entry


# =========================================================================
# Adjustment Journal Entry
# =========================================================================

def create_adjustment_journal_entry(adjustment, user):
    """
    Gain:
        DR  Inventory (1500)      total
        CR  Adjustment Exp (6200) total

    Loss / Write-off:
        DR  Adjustment Exp / Write-Off Exp   total
        CR  Inventory (1500)                 total
    """
    db = get_current_db_alias()
    company = adjustment.company

    total_cost = Decimal('0')
    for line in adjustment.lines.using(db):
        total_cost += abs(line.quantity) * line.unit_cost

    if total_cost <= 0:
        return None

    from erp.models import StockAdjustment
    is_gain = adjustment.adjustment_type == StockAdjustment.AdjustmentType.GAIN
    is_write_off = adjustment.adjustment_type == StockAdjustment.AdjustmentType.WRITE_OFF

    with transaction.atomic(using=db):
        inv_account = _get_valuation_account(company, 'inventory_account', 'inventory', db)
        if is_write_off:
            exp_account = _get_valuation_account(company, 'write_off_account', 'write_off', db)
        else:
            exp_account = _get_valuation_account(company, 'adjustment_account', 'adjustment', db)

        fiscal_year = _get_current_fiscal_year(company, db)
        entry_number = _next_journal_number(company, 'ADJ', db)

        journal_entry = JournalEntry.objects.using(db).create(
            company=company,
            entry_number=entry_number,
            entry_date=adjustment.adjustment_date,
            entry_type=JournalEntry.EntryType.INVENTORY,
            description=f'تسوية مخزون {adjustment.adjustment_number}',
            reference=adjustment.adjustment_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        if is_gain:
            # DR Inventory
            JournalEntryLine.objects.using(db).create(
                journal_entry=journal_entry,
                account=inv_account,
                description=f'تسوية مخزون – ربح {adjustment.adjustment_number}',
                debit_amount=total_cost,
                credit_amount=Decimal('0'),
                reference_type='stock_adjustment',
                reference_id=adjustment.pk,
            )
            # CR Adjustment Expense
            JournalEntryLine.objects.using(db).create(
                journal_entry=journal_entry,
                account=exp_account,
                description=f'تسوية مخزون – ربح {adjustment.adjustment_number}',
                debit_amount=Decimal('0'),
                credit_amount=total_cost,
                reference_type='stock_adjustment',
                reference_id=adjustment.pk,
            )
        else:
            # DR Adjustment / Write-off Expense
            JournalEntryLine.objects.using(db).create(
                journal_entry=journal_entry,
                account=exp_account,
                description=f'تسوية مخزون – خسارة {adjustment.adjustment_number}',
                debit_amount=total_cost,
                credit_amount=Decimal('0'),
                reference_type='stock_adjustment',
                reference_id=adjustment.pk,
            )
            # CR Inventory
            JournalEntryLine.objects.using(db).create(
                journal_entry=journal_entry,
                account=inv_account,
                description=f'إصدار مخزون – {adjustment.adjustment_number}',
                debit_amount=Decimal('0'),
                credit_amount=total_cost,
                reference_type='stock_adjustment',
                reference_id=adjustment.pk,
            )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])
        _update_account_balances(journal_entry, db)

    return journal_entry


# =========================================================================
# Supplier Invoice Journal Entry (3-way match: clear GRNI, create AP)
# =========================================================================

def create_supplier_invoice_journal_entry(supplier_invoice, user):
    """
    On SupplierInvoice approval, clear the GRNI accrual and record Accounts Payable:

        DR  Goods Received Not Invoiced (1400)   invoice_total
        CR  Accounts Payable (2000)              invoice_total

    This completes the 3-way match: GRN created DR Inventory / CR GRNI;
    now the invoice clears GRNI and books the real liability.
    """
    db = get_current_db_alias()
    company = supplier_invoice.company

    total = supplier_invoice.total_amount
    if total <= 0:
        return None

    with transaction.atomic(using=db):
        grni_account = _get_valuation_account(company, 'grni_account', 'grni', db)
        # AP account: code 2000
        ap_account = _get_or_create_account(
            company, '2000', 'Accounts Payable', 'الدائنون', 'liability', db
        )
        fiscal_year = _get_current_fiscal_year(company, db)
        entry_number = _next_journal_number(company, 'SI', db)

        journal_entry = JournalEntry.objects.using(db).create(
            company=company,
            entry_number=entry_number,
            entry_date=supplier_invoice.invoice_date,
            entry_type=JournalEntry.EntryType.PURCHASE,
            description=f'فاتورة مورد {supplier_invoice.invoice_number} – {supplier_invoice.supplier.name}',
            reference=supplier_invoice.invoice_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )
        # DR GRNI (clear the accrual)
        JournalEntryLine.objects.using(db).create(
            journal_entry=journal_entry,
            account=grni_account,
            description=f'تصفية بضاعة مستلمة – {supplier_invoice.invoice_number}',
            debit_amount=total,
            credit_amount=Decimal('0'),
            reference_type='supplier_invoice',
            reference_id=supplier_invoice.pk,
        )
        # CR Accounts Payable
        JournalEntryLine.objects.using(db).create(
            journal_entry=journal_entry,
            account=ap_account,
            description=f'دائنون – {supplier_invoice.supplier.name}',
            debit_amount=Decimal('0'),
            credit_amount=total,
            reference_type='supplier_invoice',
            reference_id=supplier_invoice.pk,
        )
        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])
        _update_account_balances(journal_entry, db)

    return journal_entry
