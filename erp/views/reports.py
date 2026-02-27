"""
ERP Views – Financial Reports & Aging

Profit & Loss, Balance Sheet, Trial Balance, Cash Flow, AR/AP Aging.
"""

from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Q, F, Value, CharField
from django.db.models.functions import Coalesce
from django.utils import timezone

from erp.models import (
    Account, JournalEntry, JournalEntryLine,
    Invoice, Expense, Payment,
    FiscalYear,
)
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_date_range(request, company):
    """Extract date range from GET params or default to current fiscal year."""
    from datetime import date as dt_date
    today = dt_date.today()
    start = request.GET.get('start')
    end = request.GET.get('end')

    if start and end:
        try:
            start = dt_date.fromisoformat(start)
            end = dt_date.fromisoformat(end)
        except (ValueError, TypeError):
            start = today.replace(month=1, day=1)
            end = today
    else:
        # Try current fiscal year
        fy = FiscalYear.objects.filter(company=company, is_current=True).first()
        if fy:
            start = fy.start_date
            end = fy.end_date
        else:
            start = today.replace(month=1, day=1)
            end = today

    return start, end


def _get_account_balances(company, start_date, end_date, account_types=None):
    """
    Aggregate posted journal entry lines by account for a date range.
    Returns dict of {account_id: {account, debit, credit, balance}}.
    """
    qs = JournalEntryLine.objects.filter(
        journal_entry__company=company,
        journal_entry__status='posted',
        journal_entry__entry_date__gte=start_date,
        journal_entry__entry_date__lte=end_date,
    ).select_related('account')

    if account_types:
        qs = qs.filter(account__account_type__in=account_types)

    qs = qs.values(
        'account__id', 'account__code', 'account__name',
        'account__name_ar', 'account__account_type',
    ).annotate(
        total_debit=Coalesce(Sum('debit_amount'), Decimal('0')),
        total_credit=Coalesce(Sum('credit_amount'), Decimal('0')),
    ).order_by('account__code')

    results = []
    for row in qs:
        acct_type = row['account__account_type']
        debit = row['total_debit']
        credit = row['total_credit']
        # Normal balance: assets/expenses are debit-normal, liabilities/equity/income are credit-normal
        if acct_type in ('asset', 'expense'):
            balance = debit - credit
        else:
            balance = credit - debit
        results.append({
            'id': row['account__id'],
            'code': row['account__code'],
            'name': row['account__name'],
            'name_ar': row['account__name_ar'],
            'account_type': acct_type,
            'debit': debit,
            'credit': credit,
            'balance': balance,
        })
    return results


# ── Trial Balance ───────────────────────────────────────────────────────────

@staff_member_required
def trial_balance(request):
    company = get_user_company(request.user)
    start_date, end_date = _parse_date_range(request, company)

    accounts = _get_account_balances(company, start_date, end_date)

    total_debit = sum(a['debit'] for a in accounts)
    total_credit = sum(a['credit'] for a in accounts)

    return render(request, 'erp/finance/trial_balance.html', {
        'accounts': accounts,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'is_balanced': total_debit == total_credit,
        'start_date': start_date,
        'end_date': end_date,
    })


# ── Profit & Loss ──────────────────────────────────────────────────────────

@staff_member_required
def profit_and_loss(request):
    company = get_user_company(request.user)
    start_date, end_date = _parse_date_range(request, company)

    income_accounts = _get_account_balances(company, start_date, end_date, ['income'])
    expense_accounts = _get_account_balances(company, start_date, end_date, ['expense'])

    total_income = sum(a['balance'] for a in income_accounts)
    total_expenses = sum(a['balance'] for a in expense_accounts)
    net_profit = total_income - total_expenses

    return render(request, 'erp/finance/profit_and_loss.html', {
        'income_accounts': income_accounts,
        'expense_accounts': expense_accounts,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'start_date': start_date,
        'end_date': end_date,
    })


# ── Balance Sheet ───────────────────────────────────────────────────────────

@staff_member_required
def balance_sheet(request):
    company = get_user_company(request.user)
    start_date, end_date = _parse_date_range(request, company)

    # Use start of all time for balance sheet (cumulative)
    from datetime import date as dt_date
    bs_start = dt_date(2000, 1, 1)

    asset_accounts = _get_account_balances(company, bs_start, end_date, ['asset'])
    liability_accounts = _get_account_balances(company, bs_start, end_date, ['liability'])
    equity_accounts = _get_account_balances(company, bs_start, end_date, ['equity'])

    # Calculate retained earnings (income - expense for the period)
    income_accounts = _get_account_balances(company, bs_start, end_date, ['income'])
    expense_accounts = _get_account_balances(company, bs_start, end_date, ['expense'])
    retained_earnings = sum(a['balance'] for a in income_accounts) - sum(a['balance'] for a in expense_accounts)

    total_assets = sum(a['balance'] for a in asset_accounts)
    total_liabilities = sum(a['balance'] for a in liability_accounts)
    total_equity = sum(a['balance'] for a in equity_accounts) + retained_earnings

    return render(request, 'erp/finance/balance_sheet.html', {
        'asset_accounts': asset_accounts,
        'liability_accounts': liability_accounts,
        'equity_accounts': equity_accounts,
        'retained_earnings': retained_earnings,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'balance_check': total_assets - (total_liabilities + total_equity),
        'as_of_date': end_date,
    })


# ── Cash Flow ───────────────────────────────────────────────────────────────

@staff_member_required
def cash_flow(request):
    company = get_user_company(request.user)
    start_date, end_date = _parse_date_range(request, company)

    # Cash accounts (code starts with 1100 or type is asset with cash-like codes)
    cash_account_codes = ['1100', '1000']  # typical cash/bank account codes

    # Operating: payments received, payments made, expenses paid
    payments_received = Payment.objects.filter(
        company=company, payment_date__gte=start_date, payment_date__lte=end_date,
        payment_type='received',
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']

    payments_made_supplier = 0
    try:
        from erp.models import SupplierPayment
        payments_made_supplier = SupplierPayment.objects.filter(
            company=company, payment_date__gte=start_date, payment_date__lte=end_date,
        ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    except Exception:
        pass

    expenses_paid = Expense.objects.filter(
        company=company, expense_date__gte=start_date, expense_date__lte=end_date,
        status__in=['approved', 'paid'],
    ).aggregate(total=Coalesce(Sum('total_amount'), Decimal('0')))['total']

    operating_inflows = payments_received
    operating_outflows = payments_made_supplier + expenses_paid
    net_operating = operating_inflows - operating_outflows

    # Summary
    net_cash_change = net_operating  # simplified — no investing/financing activities tracked yet

    return render(request, 'erp/finance/cash_flow.html', {
        'payments_received': payments_received,
        'payments_made_supplier': payments_made_supplier,
        'expenses_paid': expenses_paid,
        'operating_inflows': operating_inflows,
        'operating_outflows': operating_outflows,
        'net_operating': net_operating,
        'net_cash_change': net_cash_change,
        'start_date': start_date,
        'end_date': end_date,
    })


# ── Aging Reports ───────────────────────────────────────────────────────────

def _calculate_aging_buckets(queryset, date_field='due_date'):
    """Calculate aging buckets for invoices with balance_due > 0."""
    today = timezone.now().date()
    buckets = {
        'current': {'label': 'جاري (غير مستحق)', 'items': [], 'total': Decimal('0')},
        '1_30': {'label': '1-30 يوم', 'items': [], 'total': Decimal('0')},
        '31_60': {'label': '31-60 يوم', 'items': [], 'total': Decimal('0')},
        '61_90': {'label': '61-90 يوم', 'items': [], 'total': Decimal('0')},
        '91_120': {'label': '91-120 يوم', 'items': [], 'total': Decimal('0')},
        'over_120': {'label': 'أكثر من 120 يوم', 'items': [], 'total': Decimal('0')},
    }

    for inv in queryset:
        due = getattr(inv, date_field)
        if not due:
            continue
        days_overdue = (today - due).days

        if days_overdue <= 0:
            bucket = 'current'
        elif days_overdue <= 30:
            bucket = '1_30'
        elif days_overdue <= 60:
            bucket = '31_60'
        elif days_overdue <= 90:
            bucket = '61_90'
        elif days_overdue <= 120:
            bucket = '91_120'
        else:
            bucket = 'over_120'

        buckets[bucket]['items'].append(inv)
        buckets[bucket]['total'] += inv.balance_due

    grand_total = sum(b['total'] for b in buckets.values())
    return buckets, grand_total


@staff_member_required
def aging_receivables(request):
    """Accounts Receivable Aging Report."""
    company = get_user_company(request.user)

    invoices = Invoice.objects.filter(
        company=company,
        status__in=['sent', 'partial', 'overdue'],
        balance_due__gt=0,
    ).select_related('customer', 'currency').order_by('due_date')

    buckets, grand_total = _calculate_aging_buckets(invoices)

    # Summary by customer
    customer_summary = {}
    for inv in invoices:
        cname = inv.customer.name
        if cname not in customer_summary:
            customer_summary[cname] = {'total': Decimal('0'), 'count': 0}
        customer_summary[cname]['total'] += inv.balance_due
        customer_summary[cname]['count'] += 1
    customer_summary = dict(sorted(customer_summary.items(), key=lambda x: x[1]['total'], reverse=True))

    return render(request, 'erp/finance/aging_receivables.html', {
        'buckets': buckets,
        'grand_total': grand_total,
        'customer_summary': customer_summary,
        'invoice_count': invoices.count(),
    })


@staff_member_required
def aging_payables(request):
    """Accounts Payable Aging Report."""
    company = get_user_company(request.user)

    from erp.models import SupplierInvoice
    invoices = SupplierInvoice.objects.filter(
        company=company,
        status__in=['approved', 'partial', 'pending'],
        balance_due__gt=0,
    ).select_related('supplier', 'currency').order_by('due_date')

    buckets, grand_total = _calculate_aging_buckets(invoices)

    # Summary by supplier
    supplier_summary = {}
    for inv in invoices:
        sname = inv.supplier.name
        if sname not in supplier_summary:
            supplier_summary[sname] = {'total': Decimal('0'), 'count': 0}
        supplier_summary[sname]['total'] += inv.balance_due
        supplier_summary[sname]['count'] += 1
    supplier_summary = dict(sorted(supplier_summary.items(), key=lambda x: x[1]['total'], reverse=True))

    return render(request, 'erp/finance/aging_payables.html', {
        'buckets': buckets,
        'grand_total': grand_total,
        'supplier_summary': supplier_summary,
        'invoice_count': invoices.count(),
    })


# ── Account Detail / Ledger ────────────────────────────────────────────────

@staff_member_required
def account_detail(request, pk):
    """Account ledger — shows all posted journal entry lines for an account."""
    company = get_user_company(request.user)
    account = get_object_or_404(Account, pk=pk, company=company)

    start_date, end_date = _parse_date_range(request, company)

    lines = JournalEntryLine.objects.filter(
        account=account,
        journal_entry__company=company,
        journal_entry__status='posted',
        journal_entry__entry_date__gte=start_date,
        journal_entry__entry_date__lte=end_date,
    ).select_related('journal_entry').order_by('journal_entry__entry_date', 'journal_entry__id')

    # Calculate running balance starting from opening balance
    running_balance = account.opening_balance
    ledger_lines = []
    for line in lines:
        if account.account_type in ('asset', 'expense'):
            running_balance += line.debit_amount - line.credit_amount
        else:
            running_balance += line.credit_amount - line.debit_amount
        ledger_lines.append({
            'date': line.journal_entry.entry_date,
            'entry_number': line.journal_entry.entry_number,
            'entry_id': line.journal_entry.pk,
            'entry_type': line.journal_entry.get_entry_type_display(),
            'description': line.description or line.journal_entry.description,
            'reference': line.journal_entry.reference,
            'debit': line.debit_amount,
            'credit': line.credit_amount,
            'balance': running_balance,
        })

    total_debit = sum(l['debit'] for l in ledger_lines)
    total_credit = sum(l['credit'] for l in ledger_lines)

    return render(request, 'erp/accounts/detail.html', {
        'account': account,
        'ledger_lines': ledger_lines,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'closing_balance': running_balance,
        'opening_balance': account.opening_balance,
        'start_date': start_date,
        'end_date': end_date,
        'line_count': len(ledger_lines),
    })
