"""
ERP Views – Fixed Assets Management

Asset Register, Categories, Depreciation, Disposal,
Transfers, Revaluation, and Maintenance Logs.
"""

from dateutil.relativedelta import relativedelta

from django.db.models import Q, Sum
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.models.fixed_assets import (
    AssetCategory, FixedAsset, DepreciationSchedule,
    AssetDisposal, AssetTransfer, AssetRevaluation,
    AssetMaintenanceLog,
)
from erp.forms.fixed_assets import (
    AssetCategoryForm, FixedAssetForm, AssetDisposalForm, AssetTransferForm, AssetRevaluationForm,
    AssetMaintenanceLogForm, GenerateDepreciationForm,
)
from django.utils.translation import gettext as _
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required, paginate_qs, apply_sorting,
)


# ═══════════════════════════════════════════════════════════════════
# Asset Categories
# ═══════════════════════════════════════════════════════════════════

@staff_member_required
def asset_category_list(request):
    company = get_user_company(request.user)
    categories = AssetCategory.objects.filter(company=company)

    search = request.GET.get('search')
    if search:
        categories = categories.filter(
            Q(name__icontains=search) | Q(code__icontains=search)
        )
    categories, current_sort, current_order = apply_sorting(
        request, categories,
        allowed_fields=['name', 'code', 'useful_life_years'],
        default='name',
    )
    page_obj, query_string = paginate_qs(request, categories)

    return render(request, 'erp/fixed_assets/categories/list.html', {
        'categories': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def asset_category_create(request):
    company = get_user_company(request.user)
    form = AssetCategoryForm(request.POST or None, company=company)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.company = company
        obj.save()
        messages.success(request, _('Asset category created.'))
        return redirect('erp:asset_category_list')
    return render(request, 'erp/fixed_assets/categories/form.html', {
        'form': form, 'title': _('New Asset Category'),
    })


@staff_member_required
def asset_category_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(AssetCategory, pk=pk, company=company)
    form = AssetCategoryForm(request.POST or None, instance=obj, company=company)
    if form.is_valid():
        form.save()
        messages.success(request, _('Asset category updated.'))
        return redirect('erp:asset_category_list')
    return render(request, 'erp/fixed_assets/categories/form.html', {
        'form': form, 'title': _('Edit %(name)s') % {'name': obj.name},
    })


@staff_member_required
def asset_category_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(AssetCategory, pk=pk, company=company)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, _('Asset category deleted.'))
        return redirect('erp:asset_category_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': obj, 'cancel_url': reverse('erp:asset_category_list'),
    })


# ═══════════════════════════════════════════════════════════════════
# Fixed Asset Register
# ═══════════════════════════════════════════════════════════════════

@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def asset_list(request):
    company = get_user_company(request.user)
    assets = FixedAsset.objects.filter(company=company).select_related(
        'category', 'department', 'custodian', 'currency',
    )

    status = request.GET.get('status')
    if status:
        assets = assets.filter(status=status)

    category = request.GET.get('category')
    if category:
        assets = assets.filter(category_id=category)

    search = request.GET.get('search')
    if search:
        assets = assets.filter(
            Q(asset_number__icontains=search) |
            Q(name__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(barcode__icontains=search)
        )

    categories = AssetCategory.objects.filter(company=company, is_active=True)

    # Summary stats
    totals = assets.aggregate(
        total_cost=Sum('acquisition_cost'),
        total_book_value=Sum('current_book_value'),
        total_depreciation=Sum('accumulated_depreciation'),
    )
    assets, current_sort, current_order = apply_sorting(
        request, assets,
        allowed_fields=['asset_number', 'name', 'acquisition_date', 'acquisition_cost', 'current_book_value', 'status'],
        default='-acquisition_date',
    )
    page_obj, query_string = paginate_qs(request, assets)

    return render(request, 'erp/fixed_assets/assets/list.html', {
        'assets': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statuses': FixedAsset.Status.choices,
        'categories': categories,
        'totals': totals,
        'current_sort': current_sort,
        'current_order': current_order,
        'company': company,
    })


@staff_member_required
def asset_detail(request, pk):
    company = get_user_company(request.user)
    asset = get_object_or_404(
        FixedAsset.objects.select_related(
            'category', 'department', 'custodian', 'supplier',
            'currency', 'asset_account', 'depreciation_expense_account',
            'accumulated_depreciation_account',
        ),
        pk=pk, company=company,
    )
    schedules = asset.depreciation_schedule.all()
    transfers = asset.transfers.all().select_related(
        'from_department', 'to_department', 'from_custodian', 'to_custodian',
    )
    revaluations = asset.revaluations.all()
    maintenance = asset.maintenance_logs.all()

    disposal = getattr(asset, 'disposal', None)

    # Depreciation progress
    dep_posted = schedules.filter(status='posted').count()
    dep_total = schedules.count()
    dep_percent = (
        asset.accumulated_depreciation / asset.depreciable_amount * 100
        if asset.depreciable_amount > 0 else 0
    )

    return render(request, 'erp/fixed_assets/assets/detail.html', {
        'asset': asset,
        'schedules': schedules,
        'transfers': transfers,
        'revaluations': revaluations,
        'maintenance': maintenance,
        'disposal': disposal,
        'dep_posted': dep_posted,
        'dep_total': dep_total,
        'dep_percent': min(dep_percent, 100),
    })


@staff_member_required
def asset_create(request):
    company = get_user_company(request.user)
    form = FixedAssetForm(request.POST or None, company=company)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.company = company
        obj.current_book_value = obj.acquisition_cost
        obj.save()
        messages.success(request, _('Asset %(number)s created.') % {'number': obj.asset_number})
        return redirect('erp:asset_detail', pk=obj.pk)
    return render(request, 'erp/fixed_assets/assets/form.html', {
        'form': form, 'title': _('Register New Asset'),
    })


@staff_member_required
def asset_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(FixedAsset, pk=pk, company=company)
    form = FixedAssetForm(request.POST or None, instance=obj, company=company)
    if form.is_valid():
        form.save()
        messages.success(request, _('Asset %(number)s updated.') % {'number': obj.asset_number})
        return redirect('erp:asset_detail', pk=obj.pk)
    return render(request, 'erp/fixed_assets/assets/form.html', {
        'form': form, 'title': _('Edit %(name)s') % {'name': obj.name},
    })


@staff_member_required
def asset_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(FixedAsset, pk=pk, company=company)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, _('Asset deleted.'))
        return redirect('erp:asset_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': obj, 'cancel_url': reverse('erp:asset_detail', args=[obj.pk]),
    })


@staff_member_required
def asset_activate(request, pk):
    """Activate a draft asset (creates acquisition journal entry)."""
    company = get_user_company(request.user)
    asset = get_object_or_404(FixedAsset, pk=pk, company=company, status='draft')
    if request.method == 'POST':
        je = asset.activate(request.user)
        if je:
            messages.success(request, _('Asset activated. Journal entry %(number)s created.') % {'number': je.entry_number})
        else:
            messages.success(request, _('Asset activated (no GL accounts configured for journal entry).'))
        return redirect('erp:asset_detail', pk=asset.pk)
    return redirect('erp:asset_detail', pk=asset.pk)


# ═══════════════════════════════════════════════════════════════════
# Depreciation Schedules
# ═══════════════════════════════════════════════════════════════════

@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def depreciation_list(request):
    """List all depreciation schedules across all assets."""
    company = get_user_company(request.user)
    schedules = DepreciationSchedule.objects.filter(
        asset__company=company,
    ).select_related('asset', 'asset__currency', 'journal_entry')

    status = request.GET.get('status')
    if status:
        schedules = schedules.filter(status=status)

    asset_id = request.GET.get('asset')
    if asset_id:
        schedules = schedules.filter(asset_id=asset_id)
    schedules, current_sort, current_order = apply_sorting(
        request, schedules,
        allowed_fields=['period_date', 'depreciation_amount', 'status'],
        default='-period_date',
    )
    page_obj, query_string = paginate_qs(request, schedules)

    return render(request, 'erp/fixed_assets/depreciation/list.html', {
        'schedules': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statuses': DepreciationSchedule.Status.choices,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def depreciation_generate(request, pk):
    """Generate depreciation schedule rows for an asset."""
    company = get_user_company(request.user)
    asset = get_object_or_404(FixedAsset, pk=pk, company=company)

    form = GenerateDepreciationForm(request.POST or None)
    if form.is_valid():
        start = form.cleaned_data['start_date']
        periods = form.cleaned_data['periods']

        running_accum = asset.accumulated_depreciation
        created = 0
        for i in range(periods):
            period_date = start + relativedelta(months=i, day=31)  # end of month
            amount = asset.calculate_monthly_depreciation()

            # Don't depreciate below salvage value
            max_remaining = asset.acquisition_cost - asset.salvage_value - running_accum
            if max_remaining <= 0:
                break
            amount = min(amount, max_remaining)
            if amount <= 0:
                break

            running_accum += amount
            book_value_after = asset.acquisition_cost - running_accum

            _obj, was_created = DepreciationSchedule.objects.get_or_create(
                asset=asset,
                period_date=period_date,
                defaults={
                    'depreciation_amount': amount,
                    'accumulated_total': running_accum,
                    'book_value_after': book_value_after,
                },
            )
            if was_created:
                created += 1

        messages.success(request, _('%(count)s depreciation period(s) generated.') % {'count': created})
        return redirect('erp:asset_detail', pk=asset.pk)

    return render(request, 'erp/fixed_assets/depreciation/generate.html', {
        'form': form, 'asset': asset,
    })


@staff_member_required
def depreciation_post(request, pk):
    """Post a single scheduled depreciation entry."""
    company = get_user_company(request.user)
    schedule = get_object_or_404(
        DepreciationSchedule, pk=pk, asset__company=company, status='scheduled',
    )
    if request.method == 'POST':
        try:
            je = schedule.post(request.user)
            messages.success(
                request,
                _('Depreciation posted. Journal entry %(number)s created.') % {'number': je.entry_number},
            )
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('erp:asset_detail', pk=schedule.asset.pk)
    return redirect('erp:asset_detail', pk=schedule.asset.pk)


@staff_member_required
def depreciation_post_batch(request):
    """Post all scheduled depreciation up to a given date."""
    company = get_user_company(request.user)
    if request.method == 'POST':
        cutoff = request.POST.get('cutoff_date')
        if cutoff:
            scheduled = DepreciationSchedule.objects.filter(
                asset__company=company,
                status='scheduled',
                period_date__lte=cutoff,
            ).select_related('asset').order_by('period_date')

            posted = 0
            errors = 0
            for s in scheduled:
                try:
                    s.post(request.user)
                    posted += 1
                except (ValueError, Exception):
                    errors += 1

            messages.success(request, _('%(posted)s depreciation entries posted, %(errors)s errors.') % {'posted': posted, 'errors': errors})
    return redirect('erp:depreciation_list')


# ═══════════════════════════════════════════════════════════════════
# Asset Disposal
# ═══════════════════════════════════════════════════════════════════

@staff_member_required
def disposal_list(request):
    company = get_user_company(request.user)
    disposals = AssetDisposal.objects.filter(
        asset__company=company,
    ).select_related('asset', 'asset__currency', 'journal_entry')
    disposals, current_sort, current_order = apply_sorting(
        request, disposals,
        allowed_fields=['disposal_date', 'disposal_amount'],
        default='-disposal_date',
    )
    page_obj, query_string = paginate_qs(request, disposals)

    return render(request, 'erp/fixed_assets/disposals/list.html', {
        'disposals': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def disposal_create(request, pk):
    """Create a disposal for a specific asset."""
    company = get_user_company(request.user)
    asset = get_object_or_404(FixedAsset, pk=pk, company=company)

    if hasattr(asset, 'disposal'):
        messages.warning(request, _('This asset already has a disposal record.'))
        return redirect('erp:asset_detail', pk=asset.pk)

    form = AssetDisposalForm(request.POST or None)
    if form.is_valid():
        disposal = form.save(commit=False)
        disposal.asset = asset
        disposal.save()

        # Auto-process: calculate gain/loss and create disposal journal entry
        try:
            je = disposal.process(request.user)
            if je:
                messages.success(
                    request,
                    _('Disposal record created for %(number)s. Journal entry %(je)s posted.')
                    % {'number': asset.asset_number, 'je': je.entry_number},
                )
            else:
                messages.success(request, _('Disposal record created for %(number)s.') % {'number': asset.asset_number})
        except Exception:
            messages.success(request, _('Disposal record created for %(number)s.') % {'number': asset.asset_number})
            messages.warning(request, _('Journal entry could not be created automatically. Use "Process" to retry.'))

        return redirect('erp:disposal_detail', pk=disposal.pk)

    return render(request, 'erp/fixed_assets/disposals/form.html', {
        'form': form, 'asset': asset, 'title': _('Dispose Asset: %(name)s') % {'name': asset.name},
    })


@staff_member_required
def disposal_detail(request, pk):
    company = get_user_company(request.user)
    disposal = get_object_or_404(
        AssetDisposal.objects.select_related('asset', 'journal_entry'),
        pk=pk, asset__company=company,
    )
    return render(request, 'erp/fixed_assets/disposals/detail.html', {
        'disposal': disposal,
    })


@staff_member_required
def disposal_process(request, pk):
    """Process a disposal (calculate gain/loss, create journal entry)."""
    company = get_user_company(request.user)
    disposal = get_object_or_404(
        AssetDisposal, pk=pk, asset__company=company,
    )
    if disposal.journal_entry:
        messages.warning(request, _('This disposal has already been processed.'))
        return redirect('erp:disposal_detail', pk=disposal.pk)

    if request.method == 'POST':
        je = disposal.process(request.user)
        if je:
            messages.success(request, _('Disposal processed. Journal entry %(number)s created.') % {'number': je.entry_number})
        else:
            messages.success(request, _('Disposal processed.'))
        return redirect('erp:disposal_detail', pk=disposal.pk)
    return redirect('erp:disposal_detail', pk=disposal.pk)


# ═══════════════════════════════════════════════════════════════════
# Asset Transfers
# ═══════════════════════════════════════════════════════════════════

@staff_member_required
def transfer_fa_list(request):
    company = get_user_company(request.user)
    transfers = AssetTransfer.objects.filter(
        asset__company=company,
    ).select_related(
        'asset', 'from_department', 'to_department',
        'from_custodian', 'to_custodian',
    )
    transfers, current_sort, current_order = apply_sorting(
        request, transfers,
        allowed_fields=['transfer_date', 'created_at'],
        default='-transfer_date',
    )
    page_obj, query_string = paginate_qs(request, transfers)

    return render(request, 'erp/fixed_assets/transfers/list.html', {
        'transfers': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def transfer_fa_create(request, pk):
    """Create a transfer for a specific asset."""
    company = get_user_company(request.user)
    asset = get_object_or_404(FixedAsset, pk=pk, company=company)
    form = AssetTransferForm(request.POST or None, company=company)
    if form.is_valid():
        transfer = form.save(commit=False)
        transfer.asset = asset
        # Pre-fill "from" fields
        transfer.from_department = asset.department
        transfer.from_location = asset.location
        transfer.from_custodian = asset.custodian
        transfer.save()
        transfer.apply()
        messages.success(request, _('Asset %(number)s transferred successfully.') % {'number': asset.asset_number})
        return redirect('erp:asset_detail', pk=asset.pk)
    return render(request, 'erp/fixed_assets/transfers/form.html', {
        'form': form, 'asset': asset, 'title': _('Transfer Asset: %(name)s') % {'name': asset.name},
    })


# ═══════════════════════════════════════════════════════════════════
# Asset Revaluation
# ═══════════════════════════════════════════════════════════════════

@staff_member_required
def revaluation_list(request):
    company = get_user_company(request.user)
    revaluations = AssetRevaluation.objects.filter(
        asset__company=company,
    ).select_related('asset', 'asset__currency', 'journal_entry')
    revaluations, current_sort, current_order = apply_sorting(
        request, revaluations,
        allowed_fields=['revaluation_date', 'new_value'],
        default='-revaluation_date',
    )
    page_obj, query_string = paginate_qs(request, revaluations)

    return render(request, 'erp/fixed_assets/revaluations/list.html', {
        'revaluations': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def revaluation_create(request, pk):
    """Create a revaluation for a specific asset."""
    company = get_user_company(request.user)
    asset = get_object_or_404(FixedAsset, pk=pk, company=company)
    form = AssetRevaluationForm(request.POST or None)
    if form.is_valid():
        reval = form.save(commit=False)
        reval.asset = asset
        reval.old_value = asset.current_book_value
        reval.save()
        messages.success(request, _('Revaluation record created for %(number)s.') % {'number': asset.asset_number})
        return redirect('erp:revaluation_detail', pk=reval.pk)
    return render(request, 'erp/fixed_assets/revaluations/form.html', {
        'form': form, 'asset': asset, 'title': _('Revalue Asset: %(name)s') % {'name': asset.name},
    })


@staff_member_required
def revaluation_detail(request, pk):
    company = get_user_company(request.user)
    reval = get_object_or_404(
        AssetRevaluation.objects.select_related('asset', 'journal_entry'),
        pk=pk, asset__company=company,
    )
    return render(request, 'erp/fixed_assets/revaluations/detail.html', {
        'revaluation': reval,
    })


@staff_member_required
def revaluation_process(request, pk):
    """Process a revaluation (create journal entry, update book value)."""
    company = get_user_company(request.user)
    reval = get_object_or_404(
        AssetRevaluation, pk=pk, asset__company=company,
    )
    if reval.journal_entry:
        messages.warning(request, _('This revaluation has already been processed.'))
        return redirect('erp:revaluation_detail', pk=reval.pk)

    if request.method == 'POST':
        je = reval.process(request.user)
        if je:
            messages.success(request, _('Revaluation processed. Journal entry %(number)s created.') % {'number': je.entry_number})
        else:
            messages.success(request, _('No change in value.'))
        return redirect('erp:revaluation_detail', pk=reval.pk)
    return redirect('erp:revaluation_detail', pk=reval.pk)


# ═══════════════════════════════════════════════════════════════════
# Asset Maintenance Logs
# ═══════════════════════════════════════════════════════════════════

@staff_member_required
def maintenance_list(request):
    company = get_user_company(request.user)
    logs = AssetMaintenanceLog.objects.filter(
        asset__company=company,
    ).select_related('asset', 'asset__currency', 'performed_by')

    status = request.GET.get('status')
    if status:
        logs = logs.filter(status=status)

    mtype = request.GET.get('type')
    if mtype:
        logs = logs.filter(maintenance_type=mtype)
    logs, current_sort, current_order = apply_sorting(
        request, logs,
        allowed_fields=['maintenance_date', 'cost', 'status', 'maintenance_type'],
        default='-maintenance_date',
    )
    page_obj, query_string = paginate_qs(request, logs)

    return render(request, 'erp/fixed_assets/maintenance/list.html', {
        'logs': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statuses': AssetMaintenanceLog.Status.choices,
        'types': AssetMaintenanceLog.MaintenanceType.choices,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def maintenance_create(request, pk):
    """Create maintenance log for a specific asset."""
    company = get_user_company(request.user)
    asset = get_object_or_404(FixedAsset, pk=pk, company=company)
    form = AssetMaintenanceLogForm(request.POST or None, company=company)
    if form.is_valid():
        log = form.save(commit=False)
        log.asset = asset
        log.save()
        messages.success(request, _('Maintenance log created.'))
        return redirect('erp:asset_detail', pk=asset.pk)
    return render(request, 'erp/fixed_assets/maintenance/form.html', {
        'form': form, 'asset': asset, 'title': _('Log Maintenance: %(name)s') % {'name': asset.name},
    })


@staff_member_required
def maintenance_edit(request, pk):
    company = get_user_company(request.user)
    log = get_object_or_404(AssetMaintenanceLog, pk=pk, asset__company=company)
    form = AssetMaintenanceLogForm(request.POST or None, instance=log, company=company)
    if form.is_valid():
        form.save()
        messages.success(request, _('Maintenance log updated.'))
        return redirect('erp:asset_detail', pk=log.asset.pk)
    return render(request, 'erp/fixed_assets/maintenance/form.html', {
        'form': form, 'asset': log.asset, 'title': _('Edit Maintenance: %(name)s') % {'name': log.asset.name},
    })


@staff_member_required
def maintenance_delete(request, pk):
    company = get_user_company(request.user)
    log = get_object_or_404(AssetMaintenanceLog, pk=pk, asset__company=company)
    asset_pk = log.asset.pk
    if request.method == 'POST':
        log.delete()
        messages.success(request, _('Maintenance log deleted.'))
        return redirect('erp:asset_detail', pk=asset_pk)
    return render(request, 'erp/confirm_delete.html', {
        'object': log, 'cancel_url': reverse('erp:asset_detail', args=[asset_pk]),
    })
