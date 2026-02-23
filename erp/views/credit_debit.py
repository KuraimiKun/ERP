"""
ERP Views – Credit/Debit Notes

Issue credit or debit notes linked to existing invoices.
"""

from django.utils import timezone

from erp.models import Invoice, InvoiceLine
from erp.services import get_invoice_number
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required,
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
            quantity = min(float(qty), float(line.quantity)) if qty else float(line.quantity)
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
            quantity = min(float(qty), float(line.quantity)) if qty else float(line.quantity)
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

        messages.success(request, f'تم إنشاء إشعار مدين {dn.invoice_number} بنجاح.')
        return redirect('erp:invoice_detail', pk=dn.pk)

    return render(request, 'erp/invoices/credit_debit_form.html', {
        'invoice': invoice,
        'lines': invoice.lines.all(),
        'note_type': 'debit',
        'note_type_ar': 'إشعار مدين',
    })
