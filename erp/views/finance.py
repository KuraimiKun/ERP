"""
ERP Views – Finance

Invoices, Payments, Expenses, Accounts (Chart of Accounts), Tax Rates,
Payment Methods, Expense Categories, Currencies, Fiscal Years, and
Financial Reports.
"""

from django.db.models import Sum, Q
from django.utils import timezone

from erp.models import (
    Invoice, Payment, PaymentAllocation, Expense, ExpenseCategory,
    Account, TaxRate, PaymentMethod, Currency, FiscalYear,
)
from erp.services import get_invoice_number, get_payment_number, get_expense_number
from erp.forms import (
    InvoiceForm, InvoiceLineFormSet,
    PaymentForm, ExpenseForm,
    AccountForm, TaxRateForm, PaymentMethodForm, ExpenseCategoryForm,
    CurrencyForm, FiscalYearForm,
)
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required,
)


# ── Invoices ────────────────────────────────────────────────────────────────

@staff_member_required
def invoice_list(request):
    company = get_user_company(request.user)
    invoices = Invoice.objects.filter(company=company).select_related('customer').order_by('-invoice_date')

    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)

    search = request.GET.get('search')
    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(customer__name__icontains=search)
        )

    return render(request, 'erp/invoices/list.html', {
        'invoices': invoices,
        'statuses': Invoice.Status.choices,
    })


@staff_member_required
def invoice_detail(request, pk):
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)

    return render(request, 'erp/invoices/detail.html', {
        'invoice': invoice,
        'lines': invoice.lines.all(),
        'payments': invoice.payment_allocations.select_related('payment').all(),
    })


@staff_member_required
def invoice_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = InvoiceForm(request.POST, company=company)
        formset = InvoiceLineFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.company = company
            invoice.invoice_number = get_invoice_number(company)
            invoice.save()

            formset.instance = invoice
            formset.save()

            invoice.calculate_totals()
            invoice.save()

            # Auto-generate journal entry
            from erp.services.accounting import create_invoice_journal_entry
            create_invoice_journal_entry(invoice, request.user)

            messages.success(request, f'Invoice {invoice.invoice_number} created successfully.')
            return redirect('erp:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(company=company)
        formset = InvoiceLineFormSet()

    return render(request, 'erp/invoices/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Create Invoice',
        'submit_text': 'Create Invoice',
    })


@staff_member_required
def invoice_edit(request, pk):
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)

    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice, company=company)
        formset = InvoiceLineFormSet(request.POST, instance=invoice)

        if form.is_valid() and formset.is_valid():
            invoice = form.save()
            formset.save()

            invoice.calculate_totals()
            invoice.save()

            messages.success(request, f'Invoice {invoice.invoice_number} updated successfully.')
            return redirect('erp:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice, company=company)
        formset = InvoiceLineFormSet(instance=invoice)

    return render(request, 'erp/invoices/form.html', {
        'form': form,
        'formset': formset,
        'invoice': invoice,
        'title': f'Edit Invoice: {invoice.invoice_number}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def invoice_delete(request, pk):
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)

    if request.method == 'POST':
        number = invoice.invoice_number
        invoice.delete()
        messages.success(request, f'Invoice {number} deleted successfully.')
        return redirect('erp:invoice_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': invoice,
        'object_type': 'Invoice',
        'cancel_url': reverse('erp:invoice_detail', args=[pk]),
    })


# ── Payments ────────────────────────────────────────────────────────────────

@staff_member_required
def payment_list(request):
    company = get_user_company(request.user)
    payments = Payment.objects.filter(company=company).select_related('customer', 'payment_method', 'currency')

    payment_type = request.GET.get('type')
    if payment_type:
        payments = payments.filter(payment_type=payment_type)

    return render(request, 'erp/payments/list.html', {
        'payments': payments.order_by('-payment_date')[:100],
        'payment_types': Payment.PaymentType.choices,
    })


@staff_member_required
def payment_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = PaymentForm(request.POST, company=company)
        if form.is_valid():
            invoice = form.cleaned_data.get('invoice')
            payment = form.save(commit=False)
            payment.company = company
            payment.payment_number = get_payment_number(company)
            payment.save()

            # Allocate payment to invoice if selected
            if invoice:
                alloc_amount = min(payment.amount, invoice.balance_due)
                PaymentAllocation.objects.create(
                    payment=payment,
                    invoice=invoice,
                    amount=alloc_amount,
                )
                # Update payment allocated amounts
                payment.allocated_amount = alloc_amount
                payment.save()

                # Update invoice paid_amount and status
                invoice.paid_amount += alloc_amount
                invoice.balance_due = invoice.total_amount - invoice.paid_amount
                if invoice.balance_due <= 0:
                    invoice.status = Invoice.Status.PAID
                    invoice.balance_due = 0
                elif invoice.paid_amount > 0:
                    invoice.status = Invoice.Status.PARTIAL
                invoice.save()

            # Auto-generate journal entry
            from erp.services.accounting import create_payment_journal_entry
            create_payment_journal_entry(payment, request.user)

            messages.success(request, f'تم تسجيل الدفعة {payment.payment_number} بنجاح.')
            return redirect('erp:payment_detail', pk=payment.pk)
    else:
        form = PaymentForm(company=company)
        # Pre-fill from query params (e.g. coming from invoice detail)
        invoice_id = request.GET.get('invoice')
        customer_id = request.GET.get('customer')
        if invoice_id:
            try:
                inv = Invoice.objects.get(pk=invoice_id, company=company)
                form.initial['invoice'] = inv.pk
                form.initial['customer'] = inv.customer_id
                form.initial['amount'] = inv.balance_due
                form.initial['currency'] = inv.currency_id
                # Re-filter invoices to this customer
                form.fields['invoice'].queryset = Invoice.objects.filter(
                    company=company,
                    customer=inv.customer,
                    status__in=['sent', 'partial', 'overdue', 'draft'],
                ).select_related('customer').order_by('-invoice_date')
            except Invoice.DoesNotExist:
                pass
        elif customer_id:
            form.initial['customer'] = customer_id

    return render(request, 'erp/payments/form.html', {
        'form': form,
        'title': 'تسجيل دفعة',
        'submit_text': 'تسجيل الدفعة',
    })


@staff_member_required
def payment_detail(request, pk):
    company = get_user_company(request.user)
    payment = get_object_or_404(Payment, pk=pk, company=company)

    return render(request, 'erp/payments/detail.html', {
        'payment': payment,
        'allocations': payment.allocations.select_related('invoice'),
    })


@staff_member_required
def payment_delete(request, pk):
    company = get_user_company(request.user)
    payment = get_object_or_404(Payment, pk=pk, company=company)

    if request.method == 'POST':
        number = payment.payment_number
        payment.delete()
        messages.success(request, f'Payment {number} deleted successfully.')
        return redirect('erp:payment_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': payment,
        'object_type': 'Payment',
        'cancel_url': reverse('erp:payment_detail', args=[pk]),
    })


# ── Expenses ────────────────────────────────────────────────────────────────

@staff_member_required
def expense_list(request):
    company = get_user_company(request.user)
    expenses = Expense.objects.filter(company=company).select_related('category', 'employee', 'created_by')

    status = request.GET.get('status')
    if status:
        expenses = expenses.filter(status=status)

    return render(request, 'erp/expenses/list.html', {
        'expenses': expenses.order_by('-expense_date')[:100],
        'statuses': Expense.Status.choices,
    })


@staff_member_required
def expense_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.company = company
            expense.created_by = request.user
            expense.expense_number = get_expense_number(company)
            expense.save()

            # Auto-generate journal entry
            from erp.services.accounting import create_expense_journal_entry
            create_expense_journal_entry(expense, request.user)

            messages.success(request, 'Expense submitted successfully.')
            return redirect('erp:expense_list')
    else:
        form = ExpenseForm(company=company)

    return render(request, 'erp/expenses/form.html', {
        'form': form,
        'title': 'Submit Expense',
        'submit_text': 'Submit Expense',
    })


@staff_member_required
def expense_edit(request, pk):
    company = get_user_company(request.user)
    expense = get_object_or_404(Expense, pk=pk, company=company)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, instance=expense, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
            return redirect('erp:expense_list')
    else:
        form = ExpenseForm(instance=expense, company=company)

    return render(request, 'erp/expenses/form.html', {
        'form': form,
        'expense': expense,
        'title': 'Edit Expense',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def expense_delete(request, pk):
    company = get_user_company(request.user)
    expense = get_object_or_404(Expense, pk=pk, company=company)

    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
        return redirect('erp:expense_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': expense,
        'object_type': 'Expense',
        'cancel_url': reverse('erp:expense_list'),
    })


# ── Accounts (Chart of Accounts) ───────────────────────────────────────────

@staff_member_required
def account_list(request):
    company = get_user_company(request.user)
    accounts = Account.objects.filter(company=company) if company else Account.objects.none()

    account_type = request.GET.get('type')
    if account_type:
        accounts = accounts.filter(account_type=account_type)

    account_types = {}
    for acc in accounts:
        if acc.account_type not in account_types:
            account_types[acc.account_type] = []
        account_types[acc.account_type].append(acc)

    return render(request, 'erp/accounts/list.html', {
        'accounts': accounts,
        'account_types': account_types,
        'company': company,
    })


@staff_member_required
def account_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = AccountForm(request.POST, company=company)
        if form.is_valid():
            account = form.save(commit=False)
            account.company = company
            account.save()
            messages.success(request, f'Account "{account.code} - {account.name}" created successfully.')
            return redirect('erp:account_list')
    else:
        form = AccountForm(company=company)

    return render(request, 'erp/accounts/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def account_edit(request, pk):
    company = get_user_company(request.user)
    account = get_object_or_404(Account, pk=pk, company=company)

    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Account "{account.code} - {account.name}" updated successfully.')
            return redirect('erp:account_list')
    else:
        form = AccountForm(instance=account, company=company)

    return render(request, 'erp/accounts/form.html', {
        'form': form,
        'account': account,
        'company': company,
    })


@staff_member_required
def account_delete(request, pk):
    company = get_user_company(request.user)
    account = get_object_or_404(Account, pk=pk, company=company)

    if request.method == 'POST':
        if account.is_system:
            messages.error(request, 'System accounts cannot be deleted.')
        else:
            account.delete()
            messages.success(request, 'Account deleted successfully.')
        return redirect('erp:account_list')

    return redirect('erp:account_list')


# ── Tax Rates ───────────────────────────────────────────────────────────────

@staff_member_required
def tax_rate_list(request):
    company = get_user_company(request.user)
    tax_rates = TaxRate.objects.filter(company=company) if company else TaxRate.objects.none()

    return render(request, 'erp/tax_rates/list.html', {
        'tax_rates': tax_rates,
        'company': company,
    })


@staff_member_required
def tax_rate_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = TaxRateForm(request.POST, company=company)
        if form.is_valid():
            tax_rate = form.save(commit=False)
            tax_rate.company = company
            tax_rate.save()
            messages.success(request, f'Tax rate "{tax_rate.name}" created successfully.')
            return redirect('erp:tax_rate_list')
    else:
        form = TaxRateForm(company=company)

    return render(request, 'erp/tax_rates/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def tax_rate_edit(request, pk):
    company = get_user_company(request.user)
    tax_rate = get_object_or_404(TaxRate, pk=pk, company=company)

    if request.method == 'POST':
        form = TaxRateForm(request.POST, instance=tax_rate, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tax rate "{tax_rate.name}" updated successfully.')
            return redirect('erp:tax_rate_list')
    else:
        form = TaxRateForm(instance=tax_rate, company=company)

    return render(request, 'erp/tax_rates/form.html', {
        'form': form,
        'tax_rate': tax_rate,
        'company': company,
    })


@staff_member_required
def tax_rate_delete(request, pk):
    company = get_user_company(request.user)
    tax_rate = get_object_or_404(TaxRate, pk=pk, company=company)

    if request.method == 'POST':
        tax_rate.delete()
        messages.success(request, 'Tax rate deleted successfully.')
        return redirect('erp:tax_rate_list')

    return redirect('erp:tax_rate_list')


# ── Payment Methods ─────────────────────────────────────────────────────────

@staff_member_required
def payment_method_list(request):
    company = get_user_company(request.user)
    payment_methods = PaymentMethod.objects.filter(company=company) if company else PaymentMethod.objects.none()

    return render(request, 'erp/payment_methods/list.html', {
        'payment_methods': payment_methods,
        'company': company,
    })


@staff_member_required
def payment_method_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = PaymentMethodForm(request.POST, company=company)
        if form.is_valid():
            payment_method = form.save(commit=False)
            payment_method.company = company
            payment_method.save()
            messages.success(request, f'Payment method "{payment_method.name}" created successfully.')
            return redirect('erp:payment_method_list')
    else:
        form = PaymentMethodForm(company=company)

    return render(request, 'erp/payment_methods/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def payment_method_edit(request, pk):
    company = get_user_company(request.user)
    payment_method = get_object_or_404(PaymentMethod, pk=pk, company=company)

    if request.method == 'POST':
        form = PaymentMethodForm(request.POST, instance=payment_method, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Payment method "{payment_method.name}" updated successfully.')
            return redirect('erp:payment_method_list')
    else:
        form = PaymentMethodForm(instance=payment_method, company=company)

    return render(request, 'erp/payment_methods/form.html', {
        'form': form,
        'payment_method': payment_method,
        'company': company,
    })


@staff_member_required
def payment_method_delete(request, pk):
    company = get_user_company(request.user)
    payment_method = get_object_or_404(PaymentMethod, pk=pk, company=company)

    if request.method == 'POST':
        payment_method.delete()
        messages.success(request, 'Payment method deleted successfully.')
        return redirect('erp:payment_method_list')

    return redirect('erp:payment_method_list')


# ── Expense Categories ──────────────────────────────────────────────────────

@staff_member_required
def expense_category_list(request):
    company = get_user_company(request.user)
    expense_categories = ExpenseCategory.objects.filter(company=company) if company else ExpenseCategory.objects.none()

    return render(request, 'erp/expense_categories/list.html', {
        'expense_categories': expense_categories,
        'company': company,
    })


@staff_member_required
def expense_category_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, company=company)
        if form.is_valid():
            expense_category = form.save(commit=False)
            expense_category.company = company
            expense_category.save()
            messages.success(request, f'Expense category "{expense_category.name}" created successfully.')
            return redirect('erp:expense_category_list')
    else:
        form = ExpenseCategoryForm(company=company)

    return render(request, 'erp/expense_categories/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def expense_category_edit(request, pk):
    company = get_user_company(request.user)
    expense_category = get_object_or_404(ExpenseCategory, pk=pk, company=company)

    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=expense_category, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Expense category "{expense_category.name}" updated successfully.')
            return redirect('erp:expense_category_list')
    else:
        form = ExpenseCategoryForm(instance=expense_category, company=company)

    return render(request, 'erp/expense_categories/form.html', {
        'form': form,
        'expense_category': expense_category,
        'company': company,
    })


@staff_member_required
def expense_category_delete(request, pk):
    company = get_user_company(request.user)
    expense_category = get_object_or_404(ExpenseCategory, pk=pk, company=company)

    if request.method == 'POST':
        expense_category.delete()
        messages.success(request, 'Expense category deleted successfully.')
        return redirect('erp:expense_category_list')

    return redirect('erp:expense_category_list')


# ── Currencies ──────────────────────────────────────────────────────────────

@staff_member_required
def currency_list(request):
    company = get_user_company(request.user)
    currencies = Currency.objects.all()

    return render(request, 'erp/currencies/list.html', {
        'currencies': currencies,
        'company': company,
    })


@staff_member_required
def currency_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            currency = form.save()
            messages.success(request, f'Currency "{currency.code}" created successfully.')
            return redirect('erp:currency_list')
    else:
        form = CurrencyForm()

    return render(request, 'erp/currencies/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def currency_edit(request, pk):
    company = get_user_company(request.user)
    currency = get_object_or_404(Currency, pk=pk)

    if request.method == 'POST':
        form = CurrencyForm(request.POST, instance=currency)
        if form.is_valid():
            form.save()
            messages.success(request, f'Currency "{currency.code}" updated successfully.')
            return redirect('erp:currency_list')
    else:
        form = CurrencyForm(instance=currency)

    return render(request, 'erp/currencies/form.html', {
        'form': form,
        'currency': currency,
        'company': company,
    })


@staff_member_required
def currency_delete(request, pk):
    currency = get_object_or_404(Currency, pk=pk)

    if request.method == 'POST':
        currency.delete()
        messages.success(request, 'Currency deleted successfully.')
        return redirect('erp:currency_list')

    return redirect('erp:currency_list')


# ── Fiscal Years ────────────────────────────────────────────────────────────

@staff_member_required
def fiscal_year_list(request):
    company = get_user_company(request.user)
    fiscal_years = FiscalYear.objects.filter(company=company) if company else FiscalYear.objects.none()

    return render(request, 'erp/fiscal_years/list.html', {
        'fiscal_years': fiscal_years,
        'company': company,
    })


@staff_member_required
def fiscal_year_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = FiscalYearForm(request.POST, company=company)
        if form.is_valid():
            fiscal_year = form.save(commit=False)
            fiscal_year.company = company
            fiscal_year.save()
            messages.success(request, f'Fiscal year "{fiscal_year.name}" created successfully.')
            return redirect('erp:fiscal_year_list')
    else:
        form = FiscalYearForm(company=company)

    return render(request, 'erp/fiscal_years/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def fiscal_year_edit(request, pk):
    company = get_user_company(request.user)
    fiscal_year = get_object_or_404(FiscalYear, pk=pk, company=company)

    if request.method == 'POST':
        form = FiscalYearForm(request.POST, instance=fiscal_year, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Fiscal year "{fiscal_year.name}" updated successfully.')
            return redirect('erp:fiscal_year_list')
    else:
        form = FiscalYearForm(instance=fiscal_year, company=company)

    return render(request, 'erp/fiscal_years/form.html', {
        'form': form,
        'fiscal_year': fiscal_year,
        'company': company,
    })


@staff_member_required
def fiscal_year_delete(request, pk):
    company = get_user_company(request.user)
    fiscal_year = get_object_or_404(FiscalYear, pk=pk, company=company)

    if request.method == 'POST':
        fiscal_year.delete()
        messages.success(request, 'Fiscal year deleted successfully.')
        return redirect('erp:fiscal_year_list')

    return redirect('erp:fiscal_year_list')


# ── Financial Reports ───────────────────────────────────────────────────────

@staff_member_required
def financial_reports(request):
    """Financial reports overview page."""
    company = get_user_company(request.user)
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    context = {
        'company': company,
        'today': today,
    }

    if company:
        context['monthly_revenue'] = Invoice.objects.filter(
            company=company, status='paid', invoice_date__gte=start_of_month
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        context['yearly_revenue'] = Invoice.objects.filter(
            company=company, status='paid', invoice_date__gte=start_of_year
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        context['monthly_expenses'] = Expense.objects.filter(
            company=company, expense_date__gte=start_of_month
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        context['yearly_expenses'] = Expense.objects.filter(
            company=company, expense_date__gte=start_of_year
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        context['monthly_profit'] = context['monthly_revenue'] - context['monthly_expenses']
        context['yearly_profit'] = context['yearly_revenue'] - context['yearly_expenses']

        context['total_receivables'] = Invoice.objects.filter(
            company=company, status__in=['sent', 'partial', 'overdue']
        ).aggregate(total=Sum('balance_due'))['total'] or 0

        context['recent_invoices'] = Invoice.objects.filter(company=company).order_by('-invoice_date')[:5]
        context['recent_payments'] = Payment.objects.filter(company=company).order_by('-payment_date')[:5]
        context['recent_expenses'] = Expense.objects.filter(company=company).order_by('-expense_date')[:5]
        context['accounts'] = Account.objects.filter(
            company=company, is_active=True
        ).order_by('account_type', 'code')[:10]

    return render(request, 'erp/finance/reports.html', context)
