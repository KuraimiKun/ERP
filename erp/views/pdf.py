"""
ERP Views – PDF Generation

PDF views for invoices, quotes, purchase orders, and payslips.
"""

from erp.models import Invoice, Quote, PurchaseOrder, Payroll
from erp.services.pdf import render_to_pdf
from ._common import get_object_or_404, get_user_company, staff_member_required


@staff_member_required
def invoice_pdf(request, pk):
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    ctx = {
        "company": company,
        "invoice": invoice,
        "lines": invoice.lines.all(),
    }
    doc_type = {
        "credit": "credit_note",
        "debit": "debit_note",
        "proforma": "proforma",
    }.get(invoice.invoice_type, "invoice")
    return render_to_pdf(
        "erp/pdf/invoice_pdf.html",
        ctx,
        filename=f"{doc_type}_{invoice.invoice_number}.pdf",
    )


@staff_member_required
def quote_pdf(request, pk):
    company = get_user_company(request.user)
    quote = get_object_or_404(Quote, pk=pk, company=company)
    ctx = {
        "company": company,
        "quote": quote,
        "lines": quote.lines.all(),
    }
    return render_to_pdf(
        "erp/pdf/quote_pdf.html",
        ctx,
        filename=f"quote_{quote.quote_number}.pdf",
    )


@staff_member_required
def purchase_order_pdf(request, pk):
    company = get_user_company(request.user)
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    ctx = {
        "company": company,
        "order": order,
        "lines": order.lines.all(),
    }
    return render_to_pdf(
        "erp/pdf/po_pdf.html",
        ctx,
        filename=f"po_{order.po_number}.pdf",
    )


@staff_member_required
def payslip_pdf(request, pk):
    company = get_user_company(request.user)
    payroll = get_object_or_404(Payroll, pk=pk)
    # Verify employee belongs to this company
    if payroll.employee.company != company:
        from django.http import Http404

        raise Http404
    ctx = {
        "company": company,
        "payroll": payroll,
    }
    return render_to_pdf(
        "erp/pdf/payslip_pdf.html",
        ctx,
        filename=f"payslip_{payroll.employee.employee_id}_{payroll.period_start}.pdf",
    )
