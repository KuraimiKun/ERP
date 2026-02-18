"""
Selectors – Finance

Invoices, Payments, Expenses, Accounts, Tax Rates, Payment Methods,
Expense Categories, Currencies, Fiscal Years, Financial Reports.
"""

from django.db.models import Sum, Q
from django.utils import timezone

from erp.models import (
    Invoice, Payment, Expense, ExpenseCategory,
    Account, TaxRate, PaymentMethod, Currency, FiscalYear,
)

__all__ = [
    # Invoices
    'get_invoice_list',
    'get_invoice_detail_context',
    # Payments
    'get_payment_list',
    'get_payment_detail_context',
    # Expenses
    'get_expense_list',
    # Accounts
    'get_account_list',
    'get_account_types_map',
    # Tax Rates
    'get_tax_rate_list',
    # Payment Methods
    'get_payment_method_list',
    # Expense Categories
    'get_expense_category_list',
    # Currencies
    'get_currency_list',
    # Fiscal Years
    'get_fiscal_year_list',
    # Reports
    'get_financial_report_context',
]


# ── Invoices ────────────────────────────────────────────────────────────────

def get_invoice_list(company, *, status=None, search=None):
    qs = (
        Invoice.objects.filter(company=company)
        .select_related('customer')
        .order_by('-invoice_date')
    )
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(invoice_number__icontains=search)
            | Q(customer__name__icontains=search)
        )
    return qs


def get_invoice_detail_context(invoice):
    return {
        'lines': invoice.lines.all(),
        'payments': invoice.payment_allocations.select_related('payment').all(),
    }


# ── Payments ────────────────────────────────────────────────────────────────

def get_payment_list(company, *, payment_type=None, limit=100):
    qs = (
        Payment.objects.filter(company=company)
        .select_related('customer', 'payment_method', 'currency')
    )
    if payment_type:
        qs = qs.filter(payment_type=payment_type)
    return qs.order_by('-payment_date')[:limit]


def get_payment_detail_context(payment):
    return {
        'allocations': payment.allocations.select_related('invoice'),
    }


# ── Expenses ────────────────────────────────────────────────────────────────

def get_expense_list(company, *, status=None, limit=100):
    qs = (
        Expense.objects.filter(company=company)
        .select_related('category', 'employee', 'created_by')
    )
    if status:
        qs = qs.filter(status=status)
    return qs.order_by('-expense_date')[:limit]


# ── Accounts ────────────────────────────────────────────────────────────────

def get_account_list(company):
    if not company:
        return Account.objects.none()
    return Account.objects.filter(company=company)


def get_account_types_map(accounts_qs):
    """Group an accounts queryset by account_type into a dict."""
    result = {}
    for acc in accounts_qs:
        result.setdefault(acc.account_type, []).append(acc)
    return result


# ── Tax Rates ───────────────────────────────────────────────────────────────

def get_tax_rate_list(company):
    if not company:
        return TaxRate.objects.none()
    return TaxRate.objects.filter(company=company)


# ── Payment Methods ─────────────────────────────────────────────────────────

def get_payment_method_list(company):
    if not company:
        return PaymentMethod.objects.none()
    return PaymentMethod.objects.filter(company=company)


# ── Expense Categories ──────────────────────────────────────────────────────

def get_expense_category_list(company):
    if not company:
        return ExpenseCategory.objects.none()
    return ExpenseCategory.objects.filter(company=company)


# ── Currencies ──────────────────────────────────────────────────────────────

def get_currency_list():
    return Currency.objects.all()


# ── Fiscal Years ────────────────────────────────────────────────────────────

def get_fiscal_year_list(company):
    if not company:
        return FiscalYear.objects.none()
    return FiscalYear.objects.filter(company=company)


# ── Financial Reports ───────────────────────────────────────────────────────

def get_financial_report_context(company):
    """Return aggregated data for the financial reports page."""
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    monthly_revenue = Invoice.objects.filter(
        company=company, status='paid', invoice_date__gte=start_of_month,
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    yearly_revenue = Invoice.objects.filter(
        company=company, status='paid', invoice_date__gte=start_of_year,
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    monthly_expenses = Expense.objects.filter(
        company=company, expense_date__gte=start_of_month,
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    yearly_expenses = Expense.objects.filter(
        company=company, expense_date__gte=start_of_year,
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    total_receivables = Invoice.objects.filter(
        company=company, status__in=['sent', 'partial', 'overdue'],
    ).aggregate(total=Sum('balance_due'))['total'] or 0

    return {
        'monthly_revenue': monthly_revenue,
        'yearly_revenue': yearly_revenue,
        'monthly_expenses': monthly_expenses,
        'yearly_expenses': yearly_expenses,
        'monthly_profit': monthly_revenue - monthly_expenses,
        'yearly_profit': yearly_revenue - yearly_expenses,
        'total_receivables': total_receivables,
        'recent_invoices': Invoice.objects.filter(company=company).order_by('-invoice_date')[:5],
        'recent_payments': Payment.objects.filter(company=company).order_by('-payment_date')[:5],
        'recent_expenses': Expense.objects.filter(company=company).order_by('-expense_date')[:5],
        'accounts': Account.objects.filter(
            company=company, is_active=True,
        ).order_by('account_type', 'code')[:10],
    }
