"""
ERP Views – Credit/Debit Notes

Issue credit or debit notes linked to existing invoices.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from erp.models import Invoice, InvoiceLine, JournalEntry, JournalEntryLine, Account
from erp.models.core import FiscalYear
from erp.services import get_invoice_number
from erp.services.accounting import _get_or_create_account
from erp.services.inventory import adjust_inventory_for_invoice
from erp.services.sequence import SequenceService
from tenants.routers import get_current_db_alias
from ._common import (
    render, get_object_or_404, redirect, messages, get_user_company, staff_member_required,
)


def _already_credited_qty(invoice, line):
    """Return the total quantity already credited for a given invoice line
    across all existing credit notes that reference this invoice."""
    return InvoiceLine.objects.filter(
        invoice__company=invoice.company,
        invoice__invoice_type='credit',
        invoice__reference=f'CN for {invoice.invoice_number}',
        product=line.product,
        description=line.description,
    ).aggregate(total=Coalesce(Sum('quantity'), Decimal('0')))['total']

_logger = logging.getLogger('erp.finance')


@staff_member_required
def credit_note_create(request, pk):
    """Create a credit note from an existing invoice."""
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        line_ids = request.POST.getlist('lines')

        cn = Invoice.objects.create(
            company=company,
            customer=invoice.customer,
            invoice_number=get_invoice_number(company),
            invoice_type='credit',
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date(),
            reference=f'CN for {invoice.invoice_number}',
            currency=invoice.currency,
            status='draft',
            notes=reason,
        )

        source_lines = invoice.lines.all()
        if line_ids:
            source_lines = source_lines.filter(pk__in=line_ids)

        lines_added = 0
        for line in source_lines:
            # Guard against double-crediting: cap at remaining creditable qty
            already_credited = _already_credited_qty(invoice, line)
            max_creditable = line.quantity - already_credited
            if max_creditable <= Decimal('0'):
                continue  # This line has been fully credited already

            qty = request.POST.get(f'qty_{line.pk}')
            quantity = min(Decimal(qty), max_creditable) if qty else max_creditable
            if quantity <= Decimal('0'):
                continue

            InvoiceLine.objects.create(
                invoice=cn,
                product=line.product,
                service_pricing=line.service_pricing,
                description=line.description,
                quantity=quantity,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
                tax_rate=line.tax_rate,
                account=line.account,
            )
            lines_added += 1

        if lines_added == 0:
            cn.delete()
            messages.error(request, 'جميع البنود في هذه الفاتورة تم إنشاء إشعارات دائنة لها مسبقاً.')
            return redirect('erp:invoice_detail', pk=invoice.pk)

        cn.calculate_totals()
        cn.save()

        # Create journal entry for credit note
        _create_credit_debit_journal(cn, request.user, note_type='credit')

        # Reverse inventory: restock returned items
        try:
            adjust_inventory_for_invoice(cn, direction='in')
        except Exception as exc:
            _logger.warning('Credit note %s: inventory reversal failed: %s', cn.invoice_number, exc)

        messages.success(request, f'تم إنشاء إشعار دائن {cn.invoice_number} بنجاح.')
        return redirect('erp:invoice_detail', pk=cn.pk)

    return render(request, 'erp/invoices/credit_debit_form.html', {
        'invoice': invoice,
        'lines': invoice.lines.all(),
        'note_type': 'credit',
        'note_type_ar': 'إشعار دائن',
    })


@staff_member_required
def debit_note_create(request, pk):
    """Create a debit note from an existing invoice."""
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        line_ids = request.POST.getlist('lines')

        dn = Invoice.objects.create(
            company=company,
            customer=invoice.customer,
            invoice_number=get_invoice_number(company),
            invoice_type='debit',
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date(),
            reference=f'DN for {invoice.invoice_number}',
            currency=invoice.currency,
            status='draft',
            notes=reason,
        )

        source_lines = invoice.lines.all()
        if line_ids:
            source_lines = source_lines.filter(pk__in=line_ids)

        for line in source_lines:
            qty = request.POST.get(f'qty_{line.pk}')
            quantity = min(Decimal(qty), line.quantity) if qty else line.quantity
            InvoiceLine.objects.create(
                invoice=dn,
                product=line.product,
                service_pricing=line.service_pricing,
                description=line.description,
                quantity=quantity,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
                tax_rate=line.tax_rate,
                account=line.account,
            )

        dn.calculate_totals()
        dn.save()

        # Create journal entry for debit note
        _create_credit_debit_journal(dn, request.user, note_type='debit')

        messages.success(request, f'تم إنشاء إشعار مدين {dn.invoice_number} بنجاح.')
        return redirect('erp:invoice_detail', pk=dn.pk)

    return render(request, 'erp/invoices/credit_debit_form.html', {
        'invoice': invoice,
        'lines': invoice.lines.all(),
        'note_type': 'debit',
        'note_type_ar': 'إشعار مدين',
    })


def _create_credit_debit_journal(note, user, note_type='credit'):
    """Create and post a journal entry for a credit or debit note.

    Credit Note (reverses a sale):
        DR  Sales Revenue (4000)       subtotal
        DR  Tax Payable (2100)         tax_amount  [if any]
        CR  Accounts Receivable (1200) total_amount

    Debit Note (additional charge):
        DR  Accounts Receivable (1200) total_amount
        CR  Tax Payable (2100)         tax_amount  [if any]
        CR  Sales Revenue (4000)       subtotal
    """
    company = note.company
    ZERO = Decimal('0')

    if note.total_amount <= ZERO:
        _logger.warning('Skipping journal entry for %s %s: total_amount is zero', note_type, note.invoice_number)
        return None

    db_alias = get_current_db_alias()

    fiscal_year = FiscalYear.objects.filter(
        company=company, is_current=True, is_closed=False,
    ).first()

    entry_number = SequenceService.get_next_number(company, 'journal_entry')
    label = 'إشعار دائن' if note_type == 'credit' else 'إشعار مدين'

    with transaction.atomic():
        # Use _get_or_create_account so missing accounts are created rather than silently skipped
        ar_account = _get_or_create_account(
            company, '1200', 'Accounts Receivable', 'ذمم مدينة', 'asset', db_alias
        )
        revenue_account = _get_or_create_account(
            company, '4000', 'Sales Revenue', 'إيرادات المبيعات', 'income', db_alias
        )

        je = JournalEntry.objects.create(
            company=company,
            entry_number=entry_number,
            entry_date=note.invoice_date,
            entry_type=JournalEntry.EntryType.INVOICE,
            description=f'{label} {note.invoice_number} - {note.customer.name}',
            reference=note.reference or note.invoice_number,
            fiscal_year=fiscal_year,
            status=JournalEntry.Status.DRAFT,
            created_by=user,
        )

        if note_type == 'credit':
            # DR Revenue — reduce income
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=revenue_account,
                description=f'{label} - {note.customer.name}',
                debit_amount=note.subtotal,
                credit_amount=ZERO,
                reference_type='invoice',
                reference_id=note.pk,
            )
            if note.tax_amount > ZERO:
                tax_account = _get_or_create_account(
                    company, '2100', 'Tax Payable', 'ضريبة مستحقة', 'liability', db_alias
                )
                JournalEntryLine.objects.create(
                    journal_entry=je,
                    account=tax_account,
                    description=f'ضريبة {label} - {note.customer.name}',
                    debit_amount=note.tax_amount,
                    credit_amount=ZERO,
                    reference_type='invoice',
                    reference_id=note.pk,
                )
            # CR Accounts Receivable — reduce what customer owes
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=ar_account,
                description=f'{label} - {note.customer.name}',
                debit_amount=ZERO,
                credit_amount=note.total_amount,
                reference_type='invoice',
                reference_id=note.pk,
            )
        else:
            # DR Accounts Receivable — customer owes more
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=ar_account,
                description=f'{label} - {note.customer.name}',
                debit_amount=note.total_amount,
                credit_amount=ZERO,
                reference_type='invoice',
                reference_id=note.pk,
            )
            if note.tax_amount > ZERO:
                tax_account = _get_or_create_account(
                    company, '2100', 'Tax Payable', 'ضريبة مستحقة', 'liability', db_alias
                )
                JournalEntryLine.objects.create(
                    journal_entry=je,
                    account=tax_account,
                    description=f'ضريبة {label} - {note.customer.name}',
                    debit_amount=ZERO,
                    credit_amount=note.tax_amount,
                    reference_type='invoice',
                    reference_id=note.pk,
                )
            # CR Revenue
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=revenue_account,
                description=f'{label} - {note.customer.name}',
                debit_amount=ZERO,
                credit_amount=note.subtotal,
                reference_type='invoice',
                reference_id=note.pk,
            )

        je.calculate_totals()
        je.save(update_fields=['total_debit', 'total_credit'])
        je.post(user)

    return je
