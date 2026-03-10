"""
ERP Views – Credit/Debit Notes

Issue credit or debit notes linked to existing invoices.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from erp.models import Invoice, InvoiceLine, JournalEntry, JournalEntryLine, Account
from erp.models.core import FiscalYear
from erp.services import get_invoice_number
from erp.services.sequence import SequenceService
from ._common import (
    render, get_object_or_404, redirect, messages, get_user_company, staff_member_required,
)


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

        for line in source_lines:
            qty = request.POST.get(f'qty_{line.pk}')
            quantity = min(Decimal(qty), line.quantity) if qty else line.quantity
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

        cn.calculate_totals()
        cn.save()

        # Create journal entry for credit note
        _create_credit_debit_journal(cn, request.user, note_type='credit')

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
    """Create a journal entry for a credit or debit note.

    Credit Note (reverses a sale):
        DR  Revenue / Accounts Receivable reduction
        CR  Accounts Receivable / Revenue reduction
      Effectively: DR 4000 (Revenue)  CR 1100 (AR) — reverses original invoice

    Debit Note (additional charge):
        DR  Accounts Receivable   CR  Revenue
    """
    company = note.company
    ZERO = Decimal('0')

    if note.total_amount <= ZERO:
        return None

    # Resolve accounts
    ar_account = (
        Account.objects.filter(company=company, code='1100', is_active=True).first()
    )
    revenue_account = (
        Account.objects.filter(company=company, code='4000', is_active=True).first()
    )
    vat_account = (
        Account.objects.filter(company=company, code='2200', is_active=True).first()
    )

    if not ar_account or not revenue_account:
        return None  # Silently skip if accounts not set up

    fiscal_year = FiscalYear.objects.filter(
        company=company, is_current=True
    ).first()

    entry_number = SequenceService.get_next_number(company, 'journal_entry')

    label = 'إشعار دائن' if note_type == 'credit' else 'إشعار مدين'

    with transaction.atomic():
        je = JournalEntry.objects.create(
            company=company,
            entry_number=entry_number,
            entry_date=note.invoice_date,
            entry_type='invoice',
            description=f'{label} {note.invoice_number} - {note.customer.name}',
            reference=note.reference or note.invoice_number,
            fiscal_year=fiscal_year,
            status='draft',
            created_by=user,
        )

        if note_type == 'credit':
            # Credit note reverses original sale:
            # DR Revenue (reduce income)
            # CR Accounts Receivable (reduce what customer owes)
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=revenue_account,
                description=f'{label} - {note.customer.name}',
                debit_amount=note.subtotal,
                credit_amount=ZERO,
                reference_type='invoice',
                reference_id=note.pk,
            )
            if note.tax_amount > ZERO and vat_account:
                JournalEntryLine.objects.create(
                    journal_entry=je,
                    account=vat_account,
                    description=f'ضريبة {label} - {note.customer.name}',
                    debit_amount=note.tax_amount,
                    credit_amount=ZERO,
                    reference_type='invoice',
                    reference_id=note.pk,
                )
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
            # Debit note = additional charge:
            # DR Accounts Receivable
            # CR Revenue
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=ar_account,
                description=f'{label} - {note.customer.name}',
                debit_amount=note.total_amount,
                credit_amount=ZERO,
                reference_type='invoice',
                reference_id=note.pk,
            )
            if note.tax_amount > ZERO and vat_account:
                JournalEntryLine.objects.create(
                    journal_entry=je,
                    account=vat_account,
                    description=f'ضريبة {label} - {note.customer.name}',
                    debit_amount=ZERO,
                    credit_amount=note.tax_amount,
                    reference_type='invoice',
                    reference_id=note.pk,
                )
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
