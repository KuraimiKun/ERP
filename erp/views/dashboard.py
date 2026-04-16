"""
ERP Views – Dashboard
"""

from decimal import Decimal
from datetime import timedelta

from django.http import JsonResponse
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.models import (
    Invoice, Expense, Customer, Lead, Quote, Employee, LeaveRequest,
    Task, Payment,
)
from ._common import render, get_user_company, staff_member_required

# Reusable expressions: amount fields multiplied by their exchange rate snapshot
# to give a sum in base currency.
_INV_TOTAL_BASE = ExpressionWrapper(
    F('total_amount') * F('exchange_rate_at_date'),
    output_field=DecimalField(max_digits=20, decimal_places=6),
)
_INV_BALANCE_BASE = ExpressionWrapper(
    F('balance_due') * F('exchange_rate_at_date'),
    output_field=DecimalField(max_digits=20, decimal_places=6),
)
_EXP_TOTAL_BASE = ExpressionWrapper(
    F('total_amount') * F('exchange_rate_at_date'),
    output_field=DecimalField(max_digits=20, decimal_places=6),
)
# Quotes have no exchange_rate_at_date snapshot — use live currency rate
_QUOTE_TOTAL_BASE = ExpressionWrapper(
    F('total_amount') * F('currency__exchange_rate'),
    output_field=DecimalField(max_digits=20, decimal_places=6),
)


def _per_company_cache(timeout):
    """Decorator: cache_page with a per-company key prefix."""
    import functools

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            company = get_user_company(request.user)
            prefix = f"co{company.pk}" if company else "co0"
            return cache_page(timeout, key_prefix=prefix)(view_func)(request, *args, **kwargs)
        return wrapper
    return decorator


@staff_member_required
@_per_company_cache(60 * 5)
@vary_on_cookie
def dashboard(request):
    """Main ERP dashboard view."""
    company = get_user_company(request.user)
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    context = {
        'company': company,
        'today': today,
    }

    if company:
        # Revenue / receivables metrics — single DB round-trip via conditional
        # aggregation instead of four separate queries.
        _revenue_statuses = ['sent', 'partial', 'paid']
        _open_statuses = ['sent', 'partial', 'overdue']
        inv_stats = Invoice.objects.filter(company=company).aggregate(
            monthly_revenue=Coalesce(Sum(
                _INV_TOTAL_BASE,
                filter=Q(invoice_date__gte=start_of_month, status__in=_revenue_statuses),
            ), Decimal('0')),
            yearly_revenue=Coalesce(Sum(
                _INV_TOTAL_BASE,
                filter=Q(invoice_date__gte=start_of_year, status__in=_revenue_statuses),
            ), Decimal('0')),
            outstanding_receivables=Coalesce(Sum(
                _INV_BALANCE_BASE,
                filter=Q(status__in=_open_statuses),
            ), Decimal('0')),
            overdue_count=Count('id', filter=Q(status='overdue')),
        )
        monthly_revenue = inv_stats['monthly_revenue'] or Decimal('0')
        yearly_revenue = inv_stats['yearly_revenue'] or Decimal('0')
        outstanding_receivables = inv_stats['outstanding_receivables'] or Decimal('0')
        overdue_invoices = inv_stats['overdue_count'] or 0

        monthly_expenses = Expense.objects.filter(
            company=company,
            expense_date__gte=start_of_month,
            status='approved'
        ).aggregate(total=Coalesce(Sum(_EXP_TOTAL_BASE), Decimal('0')))['total']

        total_customers = Customer.objects.filter(company=company, is_active=True).count()
        new_customers_month = Customer.objects.filter(
            company=company,
            created_at__gte=start_of_month
        ).count()

        total_leads = Lead.objects.filter(company=company).exclude(status__in=['won', 'lost']).count()
        new_leads_month = Lead.objects.filter(
            company=company,
            created_at__gte=start_of_month
        ).count()

        pending_quotes = Quote.objects.filter(
            company=company,
            status__in=['draft', 'sent', 'viewed']
        ).count()
        quotes_value = Quote.objects.filter(
            company=company,
            status__in=['draft', 'sent', 'viewed']
        ).aggregate(total=Coalesce(Sum(_QUOTE_TOTAL_BASE), Decimal('0')))['total']

        total_employees = Employee.objects.filter(company=company, employment_status='active').count()
        pending_leave_requests = LeaveRequest.objects.filter(
            employee__company=company,
            status='pending'
        ).count()

        pending_tasks = Task.objects.filter(
            company=company,
            status__in=['todo', 'in_progress']
        ).count()
        overdue_tasks = Task.objects.filter(
            company=company,
            status__in=['todo', 'in_progress'],
            due_date__lt=timezone.now()
        ).count()

        recent_invoices = Invoice.objects.filter(
            company=company
        ).select_related('customer').order_by('-invoice_date')[:5]

        recent_payments = Payment.objects.filter(
            company=company
        ).select_related('customer').order_by('-payment_date')[:5]

        upcoming_tasks = Task.objects.filter(
            company=company,
            status__in=['todo', 'in_progress']
        ).order_by('due_date')[:5]

        recent_leads = Lead.objects.filter(
            company=company
        ).order_by('-created_at')[:5]

        context.update({
            'monthly_revenue': monthly_revenue,
            'yearly_revenue': yearly_revenue,
            'outstanding_receivables': outstanding_receivables,
            'overdue_invoices': overdue_invoices,
            'monthly_expenses': monthly_expenses,
            'total_customers': total_customers,
            'new_customers_month': new_customers_month,
            'total_leads': total_leads,
            'new_leads_month': new_leads_month,
            'pending_quotes': pending_quotes,
            'quotes_value': quotes_value,
            'total_employees': total_employees,
            'pending_leave_requests': pending_leave_requests,
            'pending_tasks': pending_tasks,
            'overdue_tasks': overdue_tasks,
            'recent_invoices': recent_invoices,
            'recent_payments': recent_payments,
            'upcoming_tasks': upcoming_tasks,
            'recent_leads': recent_leads,
        })

    return render(request, 'erp/dashboard.html', context)


@staff_member_required
@_per_company_cache(60 * 10)
@vary_on_cookie
def dashboard_charts_data(request):
    """API endpoint for dashboard chart data."""
    company = get_user_company(request.user)
    today = timezone.now().date()

    six_months_ago = today - timedelta(days=180)
    monthly_revenue = Invoice.objects.filter(
        company=company,
        invoice_date__gte=six_months_ago,
        status__in=['sent', 'partial', 'paid']
    ).annotate(
        month=TruncMonth('invoice_date')
    ).values('month').annotate(
        total=Coalesce(Sum(_INV_TOTAL_BASE), Decimal('0'))
    ).order_by('month')

    revenue_by_status = Invoice.objects.filter(
        company=company,
        invoice_date__gte=six_months_ago
    ).values('status').annotate(
        total=Coalesce(Sum(_INV_TOTAL_BASE), Decimal('0')),
        count=Count('id')
    )

    leads_by_source = Lead.objects.filter(
        company=company
    ).values('source').annotate(
        count=Count('id')
    )

    expenses_by_category = Expense.objects.filter(
        company=company,
        expense_date__gte=six_months_ago,
        status='approved'
    ).values('category__name').annotate(
        total=Coalesce(Sum(_EXP_TOTAL_BASE), Decimal('0'))
    ).order_by('-total')[:10]

    return JsonResponse({
        'monthly_revenue': list(monthly_revenue),
        'revenue_by_status': list(revenue_by_status),
        'leads_by_source': list(leads_by_source),
        'expenses_by_category': list(expenses_by_category),
    })
