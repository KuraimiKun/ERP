"""
Selectors – Customers
"""

from django.db.models import Q

from erp.models import Customer

__all__ = [
    'get_customer_list',
    'get_customer_detail_context',
]


def get_customer_list(company, *, customer_type=None, search=None):
    """Return a filtered/searchable customer queryset."""
    qs = Customer.objects.filter(company=company).order_by('name')
    if customer_type:
        qs = qs.filter(customer_type=customer_type)
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(email__icontains=search)
            | Q(customer_id__icontains=search)
        )
    return qs


def get_customer_detail_context(customer, limit=10):
    """Return related objects for the customer detail view."""
    return {
        'invoices': customer.invoices.order_by('-invoice_date')[:limit],
        'payments': customer.payments.order_by('-payment_date')[:limit],
        'quotes': customer.quotes.order_by('-quote_date')[:limit],
        'interactions': customer.interactions.order_by('-interaction_date')[:limit],
    }
