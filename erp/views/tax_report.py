"""
ERP Views – Tax Reports / VAT Returns

Aggregates VAT collected vs VAT paid and produces a summary.
"""

from datetime import date

from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.models import InvoiceLine, SupplierInvoiceLine
from ._common import (
    render,
    get_user_company,
    staff_member_required,
)


@staff_member_required
@cache_page(60 * 60)  # 1 hour
@vary_on_cookie
def tax_report(request):
    """VAT / Tax report showing collected vs paid tax."""
    company = get_user_company(request.user)

    # Date filters
    year = int(request.GET.get("year", date.today().year))
    quarter = request.GET.get("quarter", "")  # '', '1', '2', '3', '4'

    if quarter:
        q = int(quarter)
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 2
        date_start = date(year, start_month, 1)
        if end_month == 12:
            date_end = date(year + 1, 1, 1)
        else:
            date_end = date(year, end_month + 1, 1)
    else:
        date_start = date(year, 1, 1)
        date_end = date(year + 1, 1, 1)

    zero = Coalesce(Sum("tax_amount"), 0, output_field=DecimalField())

    # ----- VAT Collected (sales invoices posted / not cancelled) -----
    sales_base = InvoiceLine.objects.filter(
        invoice__company=company,
        invoice__invoice_date__gte=date_start,
        invoice__invoice_date__lt=date_end,
    ).exclude(invoice__status="cancelled")

    vat_collected_total = sales_base.aggregate(total=zero)["total"]

    vat_collected_by_rate = (
        sales_base.values(rate_name=F("tax_rate__name"), rate_pct=F("tax_rate__rate"))
        .annotate(total_tax=zero)
        .order_by("-total_tax")
    )

    vat_collected_monthly = (
        sales_base.annotate(month=TruncMonth("invoice__invoice_date"))
        .values("month")
        .annotate(total_tax=zero)
        .order_by("month")
    )

    # ----- VAT Paid (supplier invoices posted / not cancelled) -----
    purchase_base = SupplierInvoiceLine.objects.filter(
        invoice__company=company,
        invoice__invoice_date__gte=date_start,
        invoice__invoice_date__lt=date_end,
    ).exclude(invoice__status="cancelled")

    vat_paid_total = purchase_base.aggregate(total=zero)["total"]

    vat_paid_by_rate = (
        purchase_base.values(rate_name=F("tax_rate__name"), rate_pct=F("tax_rate__rate"))
        .annotate(total_tax=zero)
        .order_by("-total_tax")
    )

    vat_paid_monthly = (
        purchase_base.annotate(month=TruncMonth("invoice__invoice_date"))
        .values("month")
        .annotate(total_tax=zero)
        .order_by("month")
    )

    net_vat = vat_collected_total - vat_paid_total

    # Year range for dropdown
    current_year = date.today().year
    years = range(current_year - 5, current_year + 2)

    return render(
        request,
        "erp/tax_report/report.html",
        {
            "year": year,
            "quarter": quarter,
            "years": years,
            "date_start": date_start,
            "date_end": date_end,
            "vat_collected_total": vat_collected_total,
            "vat_collected_by_rate": vat_collected_by_rate,
            "vat_collected_monthly": vat_collected_monthly,
            "vat_paid_total": vat_paid_total,
            "vat_paid_by_rate": vat_paid_by_rate,
            "vat_paid_monthly": vat_paid_monthly,
            "net_vat": net_vat,
        },
    )
