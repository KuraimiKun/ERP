"""
ERP Services - Automatic Journal Entry Generation

Creates double-entry journal entries when invoices, payments, and
expenses are recorded.

Standard accounting entries:
  Invoice created (Sales):
    DR  Accounts Receivable    (total_amount)
    CR  Sales Revenue          (subtotal)
    CR  Tax Payable            (tax_amount)

  Payment received (Customer):
    DR  Cash / Bank            (amount)
    CR  Accounts Receivable    (amount)

  Expense recorded:
    DR  Expense Account        (amount)
    DR  Tax Receivable         (tax_amount)   [if any]
    CR  Cash / Accounts Payable (total_amount)

  Supplier Invoice (Bill):
    DR  Purchases / Inventory  (subtotal)
    DR  Input Tax              (tax_amount)   [if any]
    CR  Accounts Payable       (total_amount)

  Supplier Payment:
    DR  Accounts Payable       (amount)
    CR  Cash / Bank            (amount)

  Purchase Order (on approval — accrual):
    DR  Goods Received / Inventory  (total_amount)
    CR  Accrued Liabilities         (total_amount)
"""

from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from tenants.routers import get_current_db_alias
from erp.models import JournalEntry, JournalEntryLine, Account, FiscalYear

def _to_base(amount, exchange_rate):
    """Convert an amount to base currency using the snapshot exchange rate."""
    rate = exchange_rate or Decimal('1')
    return (Decimal(str(amount)) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _update_account_balances(journal_entry, db_alias):
    """Update current_balance on all accounts affected by a posted journal entry.

    Acquires row-level locks on the affected accounts (sorted by PK to prevent
    deadlocks) so that concurrent postings never overwrite each other's balance.
    Must be called from within an active transaction.atomic() block.
    """
    lines = list(journal_entry.lines.using(db_alias).select_related('account').all())
    if not lines:
        return
    # Lock accounts in a deterministic order to avoid deadlocks
    account_ids = sorted({line.account_id for line in lines})
    locked_accounts = {
        acc.pk: acc
        for acc in Account.objects.using(db_alias).select_for_update().filter(pk__in=account_ids)
    }
    for line in lines:
        account = locked_accounts[line.account_id]
        account.update_balance(line.debit_amount, line.credit_amount)
        account.save(using=db_alias, update_fields=['current_balance'])


def _get_or_create_account(company, code, name, name_ar, account_type, db_alias):
    """Get an account by code, or create it as a system account."""
    try:
        return Account.objects.using(db_alias).get(company=company, code=code)
    except Account.DoesNotExist:
        return Account.objects.using(db_alias).create(
            company=company,
            code=code,
            name=name,
            name_ar=name_ar,
            account_type=account_type,
            is_active=True,
            is_system=True,
        )


def _get_current_fiscal_year(company, db_alias):
    """Get the current active fiscal year, or None."""
    return FiscalYear.objects.using(db_alias).filter(
        company=company,
        is_current=True,
        is_closed=False,
    ).first()


def _next_journal_number(company, entry_type_prefix, db_alias):
    """Generate a journal entry number like JV-INV-00001."""
    from erp.models import JournalEntry
    count = JournalEntry.objects.using(db_alias).filter(
        company=company,
        entry_number__startswith=f'JV-{entry_type_prefix}-',
    ).count()
    return f'JV-{entry_type_prefix}-{str(count + 1).zfill(5)}'


def create_invoice_journal_entry(invoice, user):
    """
    Create journal entry for an invoice.

    DR  Accounts Receivable   total_amount
    CR  Sales Revenue         subtotal
    CR  Tax Payable           tax_amount  (if > 0)
    """
    if invoice.total_amount <= 0:
        return None

    db_alias = get_current_db_alias()
    company = invoice.company

    with transaction.atomic(using=db_alias):
        ar_account = _get_or_create_account(
            company, '1200', 'Accounts Receivable', 'ذمم مدينة', 'asset', db_alias
        )
        revenue_account = _get_or_create_account(
            company, '4000', 'Sales Revenue', 'إيرادات المبيعات', 'income', db_alias
        )

        fiscal_year = _get_current_fiscal_year(company, db_alias)
        entry_number = _next_journal_number(company, 'INV', db_alias)

        journal_entry = JournalEntry.objects.using(db_alias).create(
            company=company,
            entry_number=entry_number,
            entry_date=invoice.invoice_date,
            entry_type=JournalEntry.EntryType.INVOICE,
            description=f'فاتورة {invoice.invoice_number} - {invoice.customer.name}',
            reference=invoice.invoice_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        rate = invoice.exchange_rate_at_date

        # DR Accounts Receivable
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=ar_account,
            description=f'ذمم مدينة - {invoice.customer.name}',
            debit_amount=_to_base(invoice.total_amount, rate),
            credit_amount=Decimal('0'),
            reference_type='invoice',
            reference_id=invoice.pk,
        )

        # CR Sales Revenue (subtotal, before tax)
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=revenue_account,
            description=f'إيرادات مبيعات - {invoice.invoice_number}',
            debit_amount=Decimal('0'),
            credit_amount=_to_base(invoice.subtotal, rate),
            reference_type='invoice',
            reference_id=invoice.pk,
        )

        # CR Tax Payable (if tax exists)
        if invoice.tax_amount > 0:
            tax_account = _get_or_create_account(
                company, '2100', 'Tax Payable', 'ضريبة مستحقة', 'liability', db_alias
            )
            JournalEntryLine.objects.using(db_alias).create(
                journal_entry=journal_entry,
                account=tax_account,
                description=f'ضريبة القيمة المضافة - {invoice.invoice_number}',
                debit_amount=Decimal('0'),
                credit_amount=_to_base(invoice.tax_amount, rate),
                reference_type='invoice',
                reference_id=invoice.pk,
            )

        # Recalculate totals
        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

        # Update account balances
        _update_account_balances(journal_entry, db_alias)

    return journal_entry


def create_payment_journal_entry(payment, user):
    """
    Create journal entry for a payment received.

    DR  Cash / Bank           amount
    CR  Accounts Receivable   amount
    """
    if payment.amount <= 0:
        return None

    db_alias = get_current_db_alias()
    company = payment.company

    with transaction.atomic(using=db_alias):
        # Determine bank/cash account from payment method, or use default
        if payment.payment_method and payment.payment_method.account:
            bank_account = payment.payment_method.account
        else:
            bank_account = _get_or_create_account(
                company, '1100', 'Cash', 'الصندوق', 'asset', db_alias
            )

        ar_account = _get_or_create_account(
            company, '1200', 'Accounts Receivable', 'ذمم مدينة', 'asset', db_alias
        )

        fiscal_year = _get_current_fiscal_year(company, db_alias)
        entry_number = _next_journal_number(company, 'PAY', db_alias)

        journal_entry = JournalEntry.objects.using(db_alias).create(
            company=company,
            entry_number=entry_number,
            entry_date=payment.payment_date,
            entry_type=JournalEntry.EntryType.PAYMENT,
            description=f'دفعة {payment.payment_number} - {payment.customer.name}',
            reference=payment.payment_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        rate = payment.exchange_rate_at_date
        base_amount = _to_base(payment.amount, rate)

        # DR Cash / Bank
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=bank_account,
            description=f'دفعة مستلمة - {payment.payment_number}',
            debit_amount=base_amount,
            credit_amount=Decimal('0'),
            reference_type='payment',
            reference_id=payment.pk,
        )

        # CR Accounts Receivable
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=ar_account,
            description=f'تحصيل من {payment.customer.name}',
            debit_amount=Decimal('0'),
            credit_amount=base_amount,
            reference_type='payment',
            reference_id=payment.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

        # Update account balances
        _update_account_balances(journal_entry, db_alias)

    return journal_entry


def create_expense_journal_entry(expense, user):
    """
    Create journal entry for an expense.

    DR  Expense Account       amount
    DR  Tax Receivable        tax_amount  (if > 0)
    CR  Cash / AP             total_amount
    """
    if expense.total_amount <= 0:
        return None

    db_alias = get_current_db_alias()
    company = expense.company

    with transaction.atomic(using=db_alias):
        # Use the expense category's linked account, or a default
        if expense.account:
            expense_account = expense.account
        elif expense.category and expense.category.account:
            expense_account = expense.category.account
        else:
            expense_account = _get_or_create_account(
                company, '5000', 'General Expenses', 'مصاريف عامة', 'expense', db_alias
            )

        # Cash or AP depending on payment
        if expense.payment_method and expense.payment_method.account:
            cash_account = expense.payment_method.account
        else:
            cash_account = _get_or_create_account(
                company, '1100', 'Cash', 'الصندوق', 'asset', db_alias
            )

        fiscal_year = _get_current_fiscal_year(company, db_alias)
        entry_number = _next_journal_number(company, 'EXP', db_alias)

        journal_entry = JournalEntry.objects.using(db_alias).create(
            company=company,
            entry_number=entry_number,
            entry_date=expense.expense_date,
            entry_type=JournalEntry.EntryType.EXPENSE,
            description=f'مصروف {expense.expense_number} - {expense.description[:50]}',
            reference=expense.expense_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        rate = expense.exchange_rate_at_date

        # DR Expense
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=expense_account,
            description=expense.description[:255],
            debit_amount=_to_base(expense.amount, rate),
            credit_amount=Decimal('0'),
            reference_type='expense',
            reference_id=expense.pk,
        )

        # DR Tax Receivable (if tax)
        if expense.tax_amount > 0:
            tax_recv_account = _get_or_create_account(
                company, '1300', 'Input Tax (VAT Receivable)', 'ضريبة مدخلات', 'asset', db_alias
            )
            JournalEntryLine.objects.using(db_alias).create(
                journal_entry=journal_entry,
                account=tax_recv_account,
                description=f'ضريبة مدخلات - {expense.expense_number}',
                debit_amount=_to_base(expense.tax_amount, rate),
                credit_amount=Decimal('0'),
                reference_type='expense',
                reference_id=expense.pk,
            )

        # CR Cash / AP
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=cash_account,
            description=f'صرف مصروف - {expense.expense_number}',
            debit_amount=Decimal('0'),
            credit_amount=_to_base(expense.total_amount, rate),
            reference_type='expense',
            reference_id=expense.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

        # Update account balances
        _update_account_balances(journal_entry, db_alias)

    return journal_entry


# =========================================================================
# Supplier-side (Accounts Payable) journal entries
# =========================================================================

def create_supplier_invoice_journal_entry(supplier_invoice, user):
    """
    Create journal entry for a supplier invoice (bill).

    DR  Purchases / COGS      subtotal
    DR  Input Tax (VAT)       tax_amount  (if > 0)
    CR  Accounts Payable      total_amount
    """
    if supplier_invoice.total_amount <= 0:
        return None

    db_alias = get_current_db_alias()
    company = supplier_invoice.company

    with transaction.atomic(using=db_alias):
        purchases_account = _get_or_create_account(
            company, '5100', 'Purchases / COGS', 'المشتريات', 'expense', db_alias
        )
        ap_account = _get_or_create_account(
            company, '2000', 'Accounts Payable', 'ذمم دائنة', 'liability', db_alias
        )

        fiscal_year = _get_current_fiscal_year(company, db_alias)
        entry_number = _next_journal_number(company, 'SINV', db_alias)

        journal_entry = JournalEntry.objects.using(db_alias).create(
            company=company,
            entry_number=entry_number,
            entry_date=supplier_invoice.invoice_date,
            entry_type=JournalEntry.EntryType.INVOICE,
            description=f'فاتورة مورد {supplier_invoice.invoice_number} - {supplier_invoice.supplier.name}',
            reference=supplier_invoice.invoice_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        rate = supplier_invoice.exchange_rate_at_date

        # DR Purchases / COGS
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=purchases_account,
            description=f'مشتريات - {supplier_invoice.supplier.name}',
            debit_amount=_to_base(supplier_invoice.subtotal, rate),
            credit_amount=Decimal('0'),
            reference_type='supplier_invoice',
            reference_id=supplier_invoice.pk,
        )

        # DR Input Tax (if tax)
        if supplier_invoice.tax_amount > 0:
            tax_input_account = _get_or_create_account(
                company, '1300', 'Input Tax (VAT Receivable)', 'ضريبة مدخلات', 'asset', db_alias
            )
            JournalEntryLine.objects.using(db_alias).create(
                journal_entry=journal_entry,
                account=tax_input_account,
                description=f'ضريبة مدخلات - {supplier_invoice.invoice_number}',
                debit_amount=_to_base(supplier_invoice.tax_amount, rate),
                credit_amount=Decimal('0'),
                reference_type='supplier_invoice',
                reference_id=supplier_invoice.pk,
            )

        # CR Accounts Payable
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=ap_account,
            description=f'ذمم دائنة - {supplier_invoice.supplier.name}',
            debit_amount=Decimal('0'),
            credit_amount=_to_base(supplier_invoice.total_amount, rate),
            reference_type='supplier_invoice',
            reference_id=supplier_invoice.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

        # Update account balances
        _update_account_balances(journal_entry, db_alias)

    return journal_entry


def create_supplier_payment_journal_entry(supplier_payment, user):
    """
    Create journal entry for a supplier payment.

    DR  Accounts Payable      amount
    CR  Cash / Bank           amount
    """
    if supplier_payment.amount <= 0:
        return None

    db_alias = get_current_db_alias()
    company = supplier_payment.company

    with transaction.atomic(using=db_alias):
        ap_account = _get_or_create_account(
            company, '2000', 'Accounts Payable', 'ذمم دائنة', 'liability', db_alias
        )

        if supplier_payment.payment_method and supplier_payment.payment_method.account:
            bank_account = supplier_payment.payment_method.account
        else:
            bank_account = _get_or_create_account(
                company, '1100', 'Cash', 'الصندوق', 'asset', db_alias
            )

        fiscal_year = _get_current_fiscal_year(company, db_alias)
        entry_number = _next_journal_number(company, 'SPAY', db_alias)

        journal_entry = JournalEntry.objects.using(db_alias).create(
            company=company,
            entry_number=entry_number,
            entry_date=supplier_payment.payment_date,
            entry_type=JournalEntry.EntryType.PAYMENT,
            description=f'دفعة مورد {supplier_payment.payment_number} - {supplier_payment.supplier.name}',
            reference=supplier_payment.payment_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        rate = supplier_payment.exchange_rate_at_date
        base_amount = _to_base(supplier_payment.amount, rate)

        # DR Accounts Payable
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=ap_account,
            description=f'سداد ذمم دائنة - {supplier_payment.supplier.name}',
            debit_amount=base_amount,
            credit_amount=Decimal('0'),
            reference_type='supplier_payment',
            reference_id=supplier_payment.pk,
        )

        # CR Cash / Bank
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=bank_account,
            description=f'دفعة لمورد - {supplier_payment.payment_number}',
            debit_amount=Decimal('0'),
            credit_amount=base_amount,
            reference_type='supplier_payment',
            reference_id=supplier_payment.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

        # Update account balances
        _update_account_balances(journal_entry, db_alias)

    return journal_entry


def create_purchase_order_journal_entry(purchase_order, user):
    """
    Create accrual journal entry when a PO is approved.

    DR  Goods Received Not Invoiced    total_amount
    CR  Accrued Liabilities            total_amount
    """
    if purchase_order.total_amount <= 0:
        return None

    db_alias = get_current_db_alias()
    company = purchase_order.company

    with transaction.atomic(using=db_alias):
        grni_account = _get_or_create_account(
            company, '1400', 'Goods Received Not Invoiced', 'بضاعة مستلمة بدون فاتورة', 'asset', db_alias
        )
        accrued_account = _get_or_create_account(
            company, '2200', 'Accrued Liabilities', 'مصاريف مستحقة', 'liability', db_alias
        )

        fiscal_year = _get_current_fiscal_year(company, db_alias)
        entry_number = _next_journal_number(company, 'PO', db_alias)

        journal_entry = JournalEntry.objects.using(db_alias).create(
            company=company,
            entry_number=entry_number,
            entry_date=purchase_order.po_date,
            entry_type=JournalEntry.EntryType.ADJUSTMENT,
            description=f'أمر شراء {purchase_order.po_number} - {purchase_order.supplier.name}',
            reference=purchase_order.po_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.POSTED,
            posted_by=user,
            posted_at=timezone.now(),
            created_by=user,
        )

        # PO has no exchange_rate_at_date snapshot — use current currency rate
        rate = purchase_order.currency.exchange_rate if purchase_order.currency_id else Decimal('1')
        base_total = _to_base(purchase_order.total_amount, rate)

        # DR Goods Received Not Invoiced
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=grni_account,
            description=f'أمر شراء - {purchase_order.po_number}',
            debit_amount=base_total,
            credit_amount=Decimal('0'),
            reference_type='purchase_order',
            reference_id=purchase_order.pk,
        )

        # CR Accrued Liabilities
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=accrued_account,
            description=f'التزام مستحق - {purchase_order.po_number}',
            debit_amount=Decimal('0'),
            credit_amount=base_total,
            reference_type='purchase_order',
            reference_id=purchase_order.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

        # Update account balances
        _update_account_balances(journal_entry, db_alias)

    return journal_entry
