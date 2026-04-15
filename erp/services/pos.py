"""
POS Service Layer

Core business logic for Point of Sale operations:
  - open_session           Open a new POS session on a terminal
  - close_session          Close session with cash count
  - create_pos_order       Build order from cart data
  - complete_pos_order     Process payments, finalize order, deduct stock
  - void_pos_order         Void a draft or completed order
  - generate_invoice_from_pos  Create Invoice + InvoiceLines from POSOrder
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from django.utils import timezone

from tenants.routers import get_current_db_alias
from erp.models import (
    POSSession, POSOrder, POSOrderLine, POSPayment,
    Product, PaymentMethod, TaxRate,
    StockMovement, Invoice, InvoiceLine,
)
from erp.services.sequence import SequenceService
from erp.services.inventory import record_stock_movement
from erp.services.accounting import create_invoice_journal_entry

logger = logging.getLogger(__name__)

# Cash variance threshold (fraction of expected_cash); e.g. 0.05 = 5 %
_CASH_VARIANCE_THRESHOLD = Decimal('0.05')


def open_session(*, company, terminal, employee, opening_balance):
    """
    Open a new POS session on a terminal.

    Only one session per terminal can be open at a time.
    Raises ValueError if a session is already open.
    """
    db = get_current_db_alias()

    if POSSession.objects.using(db).filter(
        terminal=terminal, status='open',
    ).exists():
        raise ValueError('This terminal already has an open session.')

    session_number = SequenceService.get_next_number(company, 'pos_session')

    session = POSSession.objects.using(db).create(
        company=company,
        terminal=terminal,
        session_number=session_number,
        opened_by=employee,
        opening_balance=Decimal(str(opening_balance)),
        status='open',
        created_by=employee.user,
    )
    return session


def close_session(*, session, employee, closing_balance, notes=''):
    """
    Close a POS session, computing expected cash and difference.

    Populates summary fields (total_sales, total_orders, total_refunds).
    """
    db = get_current_db_alias()

    with transaction.atomic(using=db):
        session.calculate_expected_cash()
        session.closing_balance = Decimal(str(closing_balance))
        session.cash_difference = session.closing_balance - session.expected_cash
        session.closed_by = employee
        session.closed_at = timezone.now()
        session.closing_notes = notes
        session.status = 'closed'

        stats = session.orders.filter(status='completed').aggregate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0')),
            order_count=Count('id'),
        )
        refund_stats = session.orders.filter(status='refunded').aggregate(
            total_refunds=Coalesce(Sum('total_amount'), Decimal('0')),
        )
        session.total_sales = stats['total_sales']
        session.total_orders = stats['order_count']
        session.total_refunds = refund_stats['total_refunds']

        session.save(using=db)

    # -- Cash variance audit alert --
    if session.expected_cash:
        variance_ratio = abs(session.cash_difference) / session.expected_cash
        if variance_ratio > _CASH_VARIANCE_THRESHOLD:
            logger.warning(
                "POS cash variance alert: session=%s employee=%s "
                "expected=%s closing=%s diff=%s (%.1f%%)",
                session.session_number,
                employee.pk,
                session.expected_cash,
                session.closing_balance,
                session.cash_difference,
                float(variance_ratio * 100),
            )
            session.closing_notes = (
                f"⚠ CASH VARIANCE {variance_ratio * 100:.1f}% "
                f"(diff {session.cash_difference})\n{session.closing_notes}"
            )
            session.save(using=db, update_fields=['closing_notes'])

    return session


def create_pos_order(*, session, employee, cart_items, customer=None,
                     discount_percent=Decimal('0'), discount_amount=Decimal('0'),
                     notes=''):
    """
    Create a POSOrder with lines from cart data.

    Args:
        session: The open POSSession
        employee: The Employee creating the order
        cart_items: list of dicts, each containing:
            - product_id (int)
            - quantity (number)
            - unit_price (number)
            - discount_percent (number, optional)
            - tax_rate_id (int, optional)
        customer: Customer instance (optional, falls back to terminal default)
        discount_percent: Order-level discount percentage
        discount_amount: Order-level fixed discount amount
        notes: Order notes

    Returns:
        POSOrder instance
    """
    db = get_current_db_alias()
    company = session.company

    order_number = SequenceService.get_next_number(company, 'pos_order')

    with transaction.atomic(using=db):
        order = POSOrder.objects.using(db).create(
            company=company,
            session=session,
            order_number=order_number,
            customer=customer or session.terminal.default_customer,
            employee=employee,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            notes=notes,
            status='draft',
            created_by=employee.user,
        )

        for item in cart_items:
            product = Product.objects.using(db).get(pk=item['product_id'])
            tax_rate = None
            if item.get('tax_rate_id'):
                tax_rate = TaxRate.objects.using(db).get(pk=item['tax_rate_id'])
            elif product.tax_rate_id:
                tax_rate = product.tax_rate

            POSOrderLine.objects.using(db).create(
                order=order,
                product=product,
                product_name=product.name,
                product_sku=product.sku,
                quantity=Decimal(str(item['quantity'])),
                unit_price=Decimal(str(item['unit_price'])),
                cost_price=product.cost_price or Decimal('0'),
                discount_percent=Decimal(str(item.get('discount_percent', 0))),
                tax_rate=tax_rate,
            )

        order.calculate_totals()
        order.save(using=db)

    return order


def complete_pos_order(*, order, payments_data):
    """
    Process payments and complete a POS order.

    Deducts inventory via record_stock_movement for tracked products.

    Args:
        order: POSOrder instance (must be in 'draft' status)
        payments_data: list of dicts, each containing:
            - payment_method_id (int)
            - amount (number)
            - tendered (number, optional - defaults to amount)
            - reference (str, optional)

    Returns:
        POSOrder instance (status='completed')

    Raises:
        ValueError: If total paid is less than order total
    """
    db = get_current_db_alias()

    with transaction.atomic(using=db):
        total_paid = Decimal('0')
        for pdata in payments_data:
            method = PaymentMethod.objects.using(db).get(pk=pdata['payment_method_id'])
            amount = Decimal(str(pdata['amount']))
            tendered = Decimal(str(pdata.get('tendered', amount)))
            change = max(tendered - amount, Decimal('0')) if method.code.upper() == 'CASH' else Decimal('0')

            POSPayment.objects.using(db).create(
                order=order,
                payment_method=method,
                amount=amount,
                tendered=tendered,
                change_amount=change,
                reference=pdata.get('reference', ''),
            )
            total_paid += amount

        if total_paid < order.total_amount:
            raise ValueError(
                f'Payment total ({total_paid}) is less than order total ({order.total_amount})'
            )

        # Deduct inventory
        warehouse = order.session.terminal.warehouse
        for line in order.lines.select_related('product').all():
            if line.product.track_inventory:
                record_stock_movement(
                    company=order.company,
                    product=line.product,
                    warehouse=warehouse,
                    movement_type=StockMovement.MovementType.SALES_ISSUE,
                    quantity=line.quantity,
                    unit_cost=line.cost_price,
                    reference_type='pos_order',
                    reference_id=order.pk,
                    reference_number=order.order_number,
                    description=f'POS Sale {order.order_number} - {line.product_sku}',
                    user=order.employee.user if order.employee else None,
                    db_alias=db,
                )

        order.status = 'completed'
        order.save(using=db, update_fields=['status', 'updated_at'])

    # Create COGS journal entry for tracked inventory items
    _create_pos_cogs_journal_entry(order)

    return order


def _create_pos_cogs_journal_entry(order):
    """
    DR  Cost of Goods Sold (5100)   total_cost
    CR  Inventory (1500)            total_cost

    Called after complete_pos_order to record COGS for POS sales.
    """
    from decimal import Decimal
    from erp.services.inventory_accounting import _get_valuation_account
    from erp.services.accounting import (
        _get_current_fiscal_year, _next_journal_number, _update_account_balances,
    )
    from erp.models import JournalEntry, JournalEntryLine, StockMovement
    from django.db import transaction
    from django.utils import timezone

    db = get_current_db_alias()
    company = order.company

    # Sum cost from the stock movements just created for this order
    movements = StockMovement.objects.using(db).filter(
        reference_type='pos_order',
        reference_id=order.pk,
        movement_type=StockMovement.MovementType.SALES_ISSUE,
    )
    total_cost = sum(m.unit_cost * m.quantity for m in movements)
    if total_cost <= Decimal('0'):
        return None

    try:
        with transaction.atomic(using=db):
            cogs_account = _get_valuation_account(company, 'cogs_account', 'cogs', db)
            inv_account = _get_valuation_account(company, 'inventory_account', 'inventory', db)
            fiscal_year = _get_current_fiscal_year(company, db)
            entry_number = _next_journal_number(company, 'PCOGS', db)

            je = JournalEntry.objects.using(db).create(
                company=company,
                entry_number=entry_number,
                entry_date=order.order_date.date() if hasattr(order.order_date, 'date') else order.order_date,
                entry_type=JournalEntry.EntryType.INVENTORY,
                description=f'تكلفة بضاعة مباعة POS – {order.order_number}',
                reference=order.order_number,
                fiscal_year=fiscal_year,
                status=JournalEntry.Status.POSTED,
                posted_by=order.employee.user if order.employee else None,
                posted_at=timezone.now(),
            )
            JournalEntryLine.objects.using(db).create(
                journal_entry=je,
                account=cogs_account,
                description=f'COGS POS {order.order_number}',
                debit_amount=total_cost,
                credit_amount=Decimal('0'),
                reference_type='pos_order',
                reference_id=order.pk,
            )
            JournalEntryLine.objects.using(db).create(
                journal_entry=je,
                account=inv_account,
                description=f'مخزون POS {order.order_number}',
                debit_amount=Decimal('0'),
                credit_amount=total_cost,
                reference_type='pos_order',
                reference_id=order.pk,
            )
            je.calculate_totals()
            je.save(update_fields=['total_debit', 'total_credit'])
            _update_account_balances(je, db)
    except Exception:
        logger.exception('POS COGS journal entry failed for order %s', order.order_number)


def void_pos_order(*, order, user):
    """
    Void a POS order.

    If the order was completed, reverses inventory deductions and any COGS
    journal entries.  If an invoice was generated, it is cancelled and its
    own journal entries are also reversed.
    """
    db = get_current_db_alias()

    with transaction.atomic(using=db):
        if order.status == 'completed':
            # Reverse inventory
            warehouse = order.session.terminal.warehouse
            for line in order.lines.select_related('product').all():
                if line.product.track_inventory:
                    record_stock_movement(
                        company=order.company,
                        product=line.product,
                        warehouse=warehouse,
                        movement_type=StockMovement.MovementType.RETURN_IN,
                        quantity=line.quantity,
                        unit_cost=line.cost_price,
                        reference_type='pos_order',
                        reference_id=order.pk,
                        reference_number=order.order_number,
                        description=f'POS Void {order.order_number} - {line.product_sku}',
                        user=user,
                        db_alias=db,
                    )

            # Reverse the COGS journal entry created by _create_pos_cogs_journal_entry
            _reverse_pos_cogs_je(order, db)

        order.status = 'voided'
        order.save(using=db, update_fields=['status', 'updated_at'])

    # If an invoice was generated, cancel it and reverse its journal entries
    if order.invoice_id:
        _reverse_pos_invoice(order, db)

    return order


def _reverse_pos_cogs_je(order, db):
    """Cancel and reverse any posted COGS journal entries for a POS order.

    COGS JEs are created by _create_pos_cogs_journal_entry with
    reference=order.order_number.  Must be called inside an atomic block.
    """
    from erp.models import Account, JournalEntry
    try:
        posted_cogs = JournalEntry.objects.using(db).filter(
            company=order.company,
            reference=order.order_number,
            status=JournalEntry.Status.POSTED,
        )
        if not posted_cogs.exists():
            return
        account_ids = sorted(
            posted_cogs.values_list('lines__account_id', flat=True).distinct()
        )
        locked_accounts = {
            a.pk: a
            for a in Account.objects.using(db).select_for_update().filter(pk__in=account_ids)
        }
        for je in posted_cogs:
            for line in je.lines.select_related('account').using(db).all():
                acc = locked_accounts.get(line.account_id)
                if acc:
                    # Reverse: swap debit/credit
                    acc.update_balance(line.credit_amount, line.debit_amount)
                    acc.save(using=db, update_fields=['current_balance'])
            je.status = JournalEntry.Status.CANCELLED
            je.save(using=db, update_fields=['status'])
    except Exception:
        logger.exception('Failed to reverse COGS JE for voided POS order %s', order.order_number)


def _reverse_pos_invoice(order, db):
    """Cancel the linked POS invoice and reverse all its posted journal entries."""
    from erp.models import Invoice, Account, JournalEntry
    try:
        invoice = Invoice.objects.using(db).get(pk=order.invoice_id)
        if invoice.status == Invoice.Status.CANCELLED:
            return

        with transaction.atomic(using=db):
            # Collect and reverse all posted JEs for this invoice
            posted_entries = JournalEntry.objects.using(db).filter(
                company=order.company,
                reference=invoice.invoice_number,
                status=JournalEntry.Status.POSTED,
            )
            account_ids = sorted(
                posted_entries.values_list('lines__account_id', flat=True).distinct()
            )
            locked_accounts = {
                a.pk: a
                for a in Account.objects.using(db).select_for_update().filter(pk__in=account_ids)
            }
            for je in posted_entries:
                for line in je.lines.select_related('account').using(db).all():
                    acc = locked_accounts.get(line.account_id)
                    if acc:
                        acc.update_balance(line.credit_amount, line.debit_amount)
                        acc.save(using=db, update_fields=['current_balance'])
                je.status = JournalEntry.Status.CANCELLED
                je.save(using=db, update_fields=['status'])

            invoice.status = Invoice.Status.CANCELLED
            invoice.save(using=db, update_fields=['status'])
    except Exception:
        logger.exception('Failed to reverse POS invoice for voided order %s', order.order_number)


def generate_invoice_from_pos(order, user):
    """
    Generate a formal Invoice from a completed POSOrder.

    Links the invoice back to the order. Creates journal entries.

    Raises:
        ValueError: If order is not completed or already has an invoice.
    """
    if order.status != 'completed':
        raise ValueError('Can only generate invoice from completed orders.')
    if order.invoice:
        raise ValueError('Invoice already generated for this order.')

    db = get_current_db_alias()
    company = order.company
    customer = order.customer

    if not customer:
        raise ValueError('Customer is required to generate an invoice.')

    from erp.services.sequence import get_invoice_number

    with transaction.atomic(using=db):
        invoice = Invoice.objects.using(db).create(
            company=company,
            customer=customer,
            invoice_number=get_invoice_number(company),
            invoice_type='standard',
            invoice_date=order.order_date.date() if hasattr(order.order_date, 'date') else order.order_date,
            due_date=order.order_date.date() if hasattr(order.order_date, 'date') else order.order_date,
            currency=company.base_currency,
            reference=f'POS: {order.order_number}',
            status='paid',
            notes=f'Generated from POS order {order.order_number}',
            created_by=user,
        )

        for line in order.lines.select_related('product', 'tax_rate').all():
            InvoiceLine.objects.using(db).create(
                invoice=invoice,
                product=line.product,
                description=line.product_name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
                tax_rate=line.tax_rate,
            )

        invoice.discount_amount = order.discount_amount
        invoice.calculate_totals()
        invoice.paid_amount = invoice.total_amount
        invoice.balance_due = Decimal('0')
        invoice.save(using=db)

        # Link invoice to POS order
        order.invoice = invoice
        order.save(using=db, update_fields=['invoice', 'updated_at'])

        # Create journal entry for accounting
        create_invoice_journal_entry(invoice, user)

    return invoice
