"""
ERP Services - Automatic Journal Entry Generation

Creates double-entry journal entries when invoices, payments, and
expenses are recorded.

Standard accounting entries:
  Invoice created:
    DR  Accounts Receivable    (total_amount)
    CR  Sales Revenue          (subtotal)
    CR  Tax Payable            (tax_amount)

  Payment received:
    DR  Cash / Bank            (amount)
    CR  Accounts Receivable    (amount)

  Expense recorded:
    DR  Expense Account        (amount)
    DR  Tax Receivable         (tax_amount)   [if any]
    CR  Cash / Accounts Payable (total_amount)
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from tenants.routers import get_current_db_alias
from erp.models import JournalEntry, JournalEntryLine, Account, FiscalYear


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
    today = timezone.now().date()
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

        # DR Accounts Receivable
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=ar_account,
            description=f'ذمم مدينة - {invoice.customer.name}',
            debit_amount=invoice.total_amount,
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
            credit_amount=invoice.subtotal,
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
                credit_amount=invoice.tax_amount,
                reference_type='invoice',
                reference_id=invoice.pk,
            )

        # Recalculate totals
        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

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

        # DR Cash / Bank
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=bank_account,
            description=f'دفعة مستلمة - {payment.payment_number}',
            debit_amount=payment.amount,
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
            credit_amount=payment.amount,
            reference_type='payment',
            reference_id=payment.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

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

        # DR Expense
        JournalEntryLine.objects.using(db_alias).create(
            journal_entry=journal_entry,
            account=expense_account,
            description=expense.description[:255],
            debit_amount=expense.amount,
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
                debit_amount=expense.tax_amount,
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
            credit_amount=expense.total_amount,
            reference_type='expense',
            reference_id=expense.pk,
        )

        journal_entry.calculate_totals()
        journal_entry.save(update_fields=['total_debit', 'total_credit'])

    return journal_entry
