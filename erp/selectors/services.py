"""
Selectors – Quotes, Service Categories & Services
"""

from django.db.models import Q

from erp.models import ServiceCategory, ServicePricing, Quote

__all__ = [
    "get_quote_list",
    "get_quote_detail_context",
    "get_service_category_list",
    "get_service_list",
    "get_service_detail_context",
]


def get_quote_list(company, *, status=None, limit=100):
    qs = Quote.objects.filter(company=company).select_related("customer", "lead")
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-quote_date")[:limit]


def get_quote_detail_context(quote):
    return {
        "lines": quote.lines.all(),
    }


def get_service_category_list(company):
    return ServiceCategory.objects.filter(company=company)


def get_service_list(company, *, search=None, category=None, limit=200):
    qs = ServicePricing.objects.filter(company=company).select_related("category", "currency", "tax_rate")
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(name_ar__icontains=search))
    if category:
        qs = qs.filter(category_id=category)
    return qs.order_by("name")[:limit]


def get_service_detail_context(service):
    """Return empty dict — expand as needed."""
    return {}
