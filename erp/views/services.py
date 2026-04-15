"""
ERP Views – Quotes, Service Categories & Services (ServicePricing)
"""

from django.db.models import Q
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.models import ServiceCategory, ServicePricing, Quote, Product, TaxRate
from erp.forms import (
    ServiceCategoryForm, ServicePricingForm,
    QuoteForm, QuoteLineFormSet,
)
from erp.services import get_quote_number
from django.utils.translation import gettext as _
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required, paginate_qs, apply_sorting,
)


# ── Quotes ──────────────────────────────────────────────────────────────────

@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def quote_list(request):
    company = get_user_company(request.user)
    quotes = Quote.objects.filter(company=company).select_related('customer', 'lead')

    status = request.GET.get('status')
    if status:
        quotes = quotes.filter(status=status)

    from datetime import date

    quotes, current_sort, current_order = apply_sorting(
        request, quotes,
        allowed_fields=['quote_number', 'quote_date', 'total_amount', 'status'],
        default='-quote_date',
    )
    page_obj, query_string = paginate_qs(request, quotes)

    return render(request, 'erp/quotes/list.html', {
        'quotes': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statuses': Quote.Status.choices,
        'today': date.today(),
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def quote_detail(request, pk):
    company = get_user_company(request.user)
    quote = get_object_or_404(Quote, pk=pk, company=company)

    return render(request, 'erp/quotes/detail.html', {
        'quote': quote,
        'lines': quote.lines.all(),
    })


@staff_member_required
def quote_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = QuoteForm(request.POST, company=company)
        formset = QuoteLineFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            quote = form.save(commit=False)
            quote.company = company
            quote.quote_number = get_quote_number(company)
            quote.save()

            formset.instance = quote
            formset.save()

            quote.calculate_totals()

            messages.success(request, f'Quote {quote.quote_number} created successfully.')
            return redirect('erp:quote_detail', pk=quote.pk)
    else:
        form = QuoteForm(company=company)
        formset = QuoteLineFormSet()

    return render(request, 'erp/quotes/form.html', {
        'form': form,
        'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True),
        'services': ServicePricing.objects.filter(company=company, is_active=True),
        'tax_rates': TaxRate.objects.filter(company=company, is_active=True),
        'title': 'Create Quote',
        'submit_text': 'Create Quote',
    })


@staff_member_required
def quote_edit(request, pk):
    company = get_user_company(request.user)
    quote = get_object_or_404(Quote, pk=pk, company=company)

    if request.method == 'POST':
        form = QuoteForm(request.POST, instance=quote, company=company)
        formset = QuoteLineFormSet(request.POST, instance=quote)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            quote.calculate_totals()

            messages.success(request, f'Quote {quote.quote_number} updated successfully.')
            return redirect('erp:quote_detail', pk=quote.pk)
    else:
        form = QuoteForm(instance=quote, company=company)
        formset = QuoteLineFormSet(instance=quote)

    return render(request, 'erp/quotes/form.html', {
        'form': form,
        'formset': formset,
        'quote': quote,
        'products': Product.objects.filter(company=company, is_active=True),
        'services': ServicePricing.objects.filter(company=company, is_active=True),
        'tax_rates': TaxRate.objects.filter(company=company, is_active=True),
        'title': f'Edit Quote: {quote.quote_number}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def quote_delete(request, pk):
    company = get_user_company(request.user)
    quote = get_object_or_404(Quote, pk=pk, company=company)

    if request.method == 'POST':
        number = quote.quote_number
        quote.delete()
        messages.success(request, f'Quote {number} deleted successfully.')
        return redirect('erp:quote_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': quote,
        'object_type': 'Quote',
        'cancel_url': reverse('erp:quote_detail', args=[pk]),
    })


# ── Service Categories ──────────────────────────────────────────────────────

@staff_member_required
def service_category_list(request):
    company = get_user_company(request.user)
    categories = ServiceCategory.objects.filter(company=company)

    categories, current_sort, current_order = apply_sorting(
        request, categories,
        allowed_fields=['name', 'created_at'],
        default='name',
    )
    page_obj, query_string = paginate_qs(request, categories)

    return render(request, 'erp/service_categories/list.html', {
        'categories': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def service_category_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, _('Service category "%(name)s" created successfully.') % {'name': obj.name})
            return redirect('erp:service_category_list')
    else:
        form = ServiceCategoryForm(company=company)
    return render(request, 'erp/service_categories/form.html', {
        'form': form, 'title': _('Add Service Category'), 'submit_text': _('Save'),
    })


@staff_member_required
def service_category_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(ServiceCategory, pk=pk, company=company)
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, _('Service category updated successfully.'))
            return redirect('erp:service_category_list')
    else:
        form = ServiceCategoryForm(instance=obj, company=company)
    return render(request, 'erp/service_categories/form.html', {
        'form': form, 'title': _('Edit Service Category'), 'submit_text': _('Save Changes'),
    })


@staff_member_required
def service_category_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(ServiceCategory, pk=pk, company=company)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'تم حذف تصنيف الخدمة بنجاح.')
        return redirect('erp:service_category_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': obj, 'object_type': 'تصنيف خدمة',
        'cancel_url': reverse('erp:service_category_list'),
    })


# ── Services (ServicePricing) ──────────────────────────────────────────────

@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def service_list(request):
    company = get_user_company(request.user)
    services = ServicePricing.objects.filter(company=company).select_related('category', 'currency', 'tax_rate')

    search = request.GET.get('search', '').strip()
    if search:
        services = services.filter(
            Q(name__icontains=search) | Q(code__icontains=search) | Q(name_ar__icontains=search)
        )
    cat = request.GET.get('category')
    if cat:
        services = services.filter(category_id=cat)

    services, current_sort, current_order = apply_sorting(
        request, services,
        allowed_fields=['name', 'code', 'base_price', 'pricing_type'],
        default='name',
    )
    page_obj, query_string = paginate_qs(request, services)

    return render(request, 'erp/services/list.html', {
        'services': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'categories': ServiceCategory.objects.filter(company=company, is_active=True),
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def service_detail(request, pk):
    company = get_user_company(request.user)
    service = get_object_or_404(ServicePricing, pk=pk, company=company)
    price_tiers = service.price_tiers.all().order_by('min_quantity')
    quote_lines = service.quote_lines.select_related('quote__customer').order_by('-quote__quote_date')[:20]
    invoice_lines = service.invoice_lines.select_related('invoice__customer').order_by('-invoice__invoice_date')[:20]
    return render(request, 'erp/services/detail.html', {
        'service': service,
        'price_tiers': price_tiers,
        'quote_lines': quote_lines,
        'invoice_lines': invoice_lines,
    })


@staff_member_required
def service_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = ServicePricingForm(request.POST, company=company)
        if form.is_valid():
            service = form.save(commit=False)
            service.company = company
            service.save()
            messages.success(request, _('Service "%(name)s" created successfully.') % {'name': service.name})
            return redirect('erp:service_detail', pk=service.pk)
    else:
        form = ServicePricingForm(company=company)
    return render(request, 'erp/services/form.html', {
        'form': form, 'title': _('Add Service'), 'submit_text': _('Save Service'),
    })


@staff_member_required
def service_edit(request, pk):
    company = get_user_company(request.user)
    service = get_object_or_404(ServicePricing, pk=pk, company=company)
    if request.method == 'POST':
        form = ServicePricingForm(request.POST, instance=service, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, _('Service updated successfully.'))
            return redirect('erp:service_detail', pk=service.pk)
    else:
        form = ServicePricingForm(instance=service, company=company)
    return render(request, 'erp/services/form.html', {
        'form': form, 'title': _('Edit Service'), 'submit_text': _('Save Changes'),
    })


@staff_member_required
def service_delete(request, pk):
    company = get_user_company(request.user)
    service = get_object_or_404(ServicePricing, pk=pk, company=company)
    if request.method == 'POST':
        service.delete()
        messages.success(request, 'تم حذف الخدمة بنجاح.')
        return redirect('erp:service_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': service, 'object_type': 'خدمة',
        'cancel_url': reverse('erp:service_detail', args=[pk]),
    })
