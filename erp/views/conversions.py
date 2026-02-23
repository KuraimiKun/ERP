"""
ERP Views – Conversions

Quote → Invoice conversion and Lead → Customer conversion.
"""

from django.utils import timezone

from erp.models import (
    Invoice, InvoiceLine, Quote, Lead, Customer,
)
from erp.services import get_invoice_number, get_customer_id
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required,
)


# ── Quote → Invoice ────────────────────────────────────────────────────────

@staff_member_required
def quote_convert_to_invoice(request, pk):
    """Convert an accepted quote into a draft invoice."""
    company = get_user_company(request.user)
    quote = get_object_or_404(Quote, pk=pk, company=company)

    if quote.converted_to_invoice:
        messages.warning(request, f'عرض السعر {quote.quote_number} تم تحويله مسبقاً إلى الفاتورة {quote.converted_to_invoice.invoice_number}.')
        return redirect('erp:invoice_detail', pk=quote.converted_to_invoice.pk)

    if request.method == 'POST':
        # Must have a customer — use quote's customer or create from lead
        customer = quote.customer
        if not customer and quote.lead and quote.lead.converted_customer:
            customer = quote.lead.converted_customer
        if not customer:
            messages.error(request, 'يجب تحويل العميل المحتمل إلى عميل حقيقي أولاً أو ربط العرض بعميل.')
            return redirect('erp:quote_detail', pk=quote.pk)

        # Create invoice
        invoice = Invoice.objects.create(
            company=company,
            customer=customer,
            invoice_number=get_invoice_number(company),
            invoice_type='standard',
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date(),
            reference=f'Quote: {quote.quote_number}',
            currency=quote.currency,
            status='draft',
            notes=quote.notes or '',
            terms=quote.terms or '',
        )

        # Copy lines
        for ql in quote.lines.all():
            InvoiceLine.objects.create(
                invoice=invoice,
                product=ql.product,
                service_pricing=ql.service_pricing,
                description=ql.description,
                quantity=ql.quantity,
                unit_price=ql.unit_price,
                discount_percent=ql.discount_percent,
                tax_rate=ql.tax_rate,
            )

        invoice.calculate_totals()
        invoice.save()

        # Link quote to invoice
        quote.converted_to_invoice = invoice
        quote.status = 'accepted'
        quote.save(update_fields=['converted_to_invoice', 'status'])

        messages.success(request, f'تم تحويل عرض السعر {quote.quote_number} إلى الفاتورة {invoice.invoice_number}.')
        return redirect('erp:invoice_edit', pk=invoice.pk)

    return render(request, 'erp/quotes/convert_confirm.html', {
        'quote': quote,
    })


# ── Lead → Customer ────────────────────────────────────────────────────────

@staff_member_required
def lead_convert_to_customer(request, pk):
    """Convert a lead into a customer."""
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)

    if lead.converted_customer:
        messages.info(request, f'تم تحويل هذا العميل المحتمل مسبقاً إلى {lead.converted_customer.name}.')
        return redirect('erp:customer_detail', pk=lead.converted_customer.pk)

    if request.method == 'POST':
        name = request.POST.get('name') or f'{lead.first_name} {lead.last_name}'
        customer_type = request.POST.get('customer_type', 'individual')

        currency = company.base_currency

        customer = Customer.objects.create(
            company=company,
            customer_id=get_customer_id(company),
            name=name,
            customer_type=customer_type,
            email=lead.email or '',
            phone=lead.phone or '',
            mobile=lead.mobile or '',
            billing_city=lead.city or '',
            billing_country=lead.country or '',
            billing_address=lead.address or '',
            currency=currency,
            notes=f'تم التحويل من العميل المحتمل: {lead.lead_number}',
            is_active=True,
        )

        # Link lead → customer
        lead.converted_customer = customer
        lead.conversion_date = timezone.now()
        lead.status = Lead.Status.WON
        lead.save(update_fields=['converted_customer', 'conversion_date', 'status'])

        messages.success(request, f'تم تحويل {lead.first_name} {lead.last_name} إلى عميل بنجاح ({customer.customer_id}).')
        return redirect('erp:customer_detail', pk=customer.pk)

    return render(request, 'erp/leads/convert_confirm.html', {
        'lead': lead,
    })
