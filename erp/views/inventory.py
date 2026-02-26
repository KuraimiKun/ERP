"""
ERP Views – Inventory & Warehouse Management

Full CRUD + workflow actions for warehouses, zones, bins, lots/serials,
goods receipt notes, stock transfers, stock adjustments, cycle counts,
pick lists, shipments, reorder rules, stock movements, and valuation config.
"""

from django.db.models import Q, Sum, F
from django.utils import timezone

from erp.models import (
    Product, Warehouse, WarehouseZone, WarehouseBin,
    UnitOfMeasure, UnitOfMeasureConversion,
    LotBatch, SerialNumber, StockItem, StockMovement,
    GoodsReceiptNote, GoodsReceiptLine,
    StockTransfer, StockTransferLine,
    StockAdjustment, StockAdjustmentLine,
    CycleCount, CycleCountLine,
    PickList, PickListLine,
    ShipmentNote, ShipmentLine,
    ReorderRule, InventoryValuationConfig,
)
from erp.forms.inventory import (
    WarehouseForm, WarehouseZoneForm, WarehouseZoneFormSet,
    WarehouseBinForm, WarehouseBinFormSet,
    UnitOfMeasureForm, UnitOfMeasureConversionForm,
    LotBatchForm, SerialNumberForm,
    GoodsReceiptNoteForm, GoodsReceiptLineFormSet,
    StockTransferForm, StockTransferLineFormSet,
    StockAdjustmentForm, StockAdjustmentLineFormSet,
    CycleCountForm, CycleCountLineFormSet,
    PickListForm, PickListLineFormSet,
    ShipmentNoteForm, ShipmentLineFormSet,
    ReorderRuleForm, InventoryValuationConfigForm,
)
from erp.services.sequence import SequenceService
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required,
)


# ═══════════════════════════════════════════════════════════════════════════
#  WAREHOUSES
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def warehouse_list(request):
    company = get_user_company(request.user)
    warehouses = Warehouse.objects.filter(company=company).select_related('manager')
    search = request.GET.get('search', '').strip()
    if search:
        warehouses = warehouses.filter(
            Q(name__icontains=search) | Q(code__icontains=search) |
            Q(name_ar__icontains=search) | Q(city__icontains=search)
        )
    return render(request, 'erp/inventory/warehouse_list.html', {
        'warehouses': warehouses.order_by('code'),
    })


@staff_member_required
def warehouse_detail(request, pk):
    company = get_user_company(request.user)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    zones = warehouse.zones.prefetch_related('bins').all()
    stock_summary = (
        StockItem.objects.filter(warehouse=warehouse, warehouse__company=company)
        .values('product__name', 'product__sku', 'product_id')
        .annotate(
            total_on_hand=Sum('on_hand'),
            total_allocated=Sum('allocated'),
        )
        .order_by('product__name')[:50]
    )
    return render(request, 'erp/inventory/warehouse_detail.html', {
        'warehouse': warehouse,
        'zones': zones,
        'stock_summary': stock_summary,
    })


@staff_member_required
def warehouse_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = WarehouseForm(request.POST, company=company)
        zone_formset = WarehouseZoneFormSet(request.POST)
        if form.is_valid() and zone_formset.is_valid():
            wh = form.save(commit=False)
            wh.company = company
            wh.save()
            zone_formset.instance = wh
            zone_formset.save()
            messages.success(request, f'تم إنشاء المستودع "{wh.name}" بنجاح.')
            return redirect('erp:warehouse_detail', pk=wh.pk)
    else:
        form = WarehouseForm(company=company)
        zone_formset = WarehouseZoneFormSet()
    return render(request, 'erp/inventory/warehouse_form.html', {
        'form': form, 'zone_formset': zone_formset,
        'title': 'إنشاء مستودع', 'submit_text': 'حفظ',
    })


@staff_member_required
def warehouse_edit(request, pk):
    company = get_user_company(request.user)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    if request.method == 'POST':
        form = WarehouseForm(request.POST, instance=warehouse, company=company)
        zone_formset = WarehouseZoneFormSet(request.POST, instance=warehouse)
        if form.is_valid() and zone_formset.is_valid():
            form.save()
            zone_formset.save()
            messages.success(request, 'تم تحديث المستودع بنجاح.')
            return redirect('erp:warehouse_detail', pk=warehouse.pk)
    else:
        form = WarehouseForm(instance=warehouse, company=company)
        zone_formset = WarehouseZoneFormSet(instance=warehouse)
    return render(request, 'erp/inventory/warehouse_form.html', {
        'form': form, 'zone_formset': zone_formset,
        'title': 'تعديل مستودع', 'submit_text': 'حفظ التغييرات', 'warehouse': warehouse,
    })


@staff_member_required
def warehouse_delete(request, pk):
    company = get_user_company(request.user)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    if request.method == 'POST':
        warehouse.delete()
        messages.success(request, 'تم حذف المستودع بنجاح.')
        return redirect('erp:warehouse_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': warehouse, 'object_type': 'مستودع',
        'cancel_url': reverse('erp:warehouse_detail', args=[pk]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  WAREHOUSE ZONES & BINS (managed via warehouse detail + standalone)
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def zone_detail(request, pk):
    company = get_user_company(request.user)
    zone = get_object_or_404(WarehouseZone, pk=pk, warehouse__company=company)
    bins = zone.bins.all().order_by('code')
    return render(request, 'erp/inventory/zone_detail.html', {
        'zone': zone, 'bins': bins,
    })


@staff_member_required
def zone_create(request, warehouse_pk):
    company = get_user_company(request.user)
    warehouse = get_object_or_404(Warehouse, pk=warehouse_pk, company=company)
    if request.method == 'POST':
        form = WarehouseZoneForm(request.POST)
        bin_formset = WarehouseBinFormSet(request.POST)
        if form.is_valid() and bin_formset.is_valid():
            zone = form.save(commit=False)
            zone.warehouse = warehouse
            zone.save()
            bin_formset.instance = zone
            bin_formset.save()
            messages.success(request, f'تم إنشاء المنطقة "{zone.name}" بنجاح.')
            return redirect('erp:warehouse_detail', pk=warehouse.pk)
    else:
        form = WarehouseZoneForm()
        bin_formset = WarehouseBinFormSet()
    return render(request, 'erp/inventory/zone_form.html', {
        'form': form, 'bin_formset': bin_formset, 'warehouse': warehouse,
        'title': 'إنشاء منطقة', 'submit_text': 'حفظ',
    })


@staff_member_required
def zone_edit(request, pk):
    company = get_user_company(request.user)
    zone = get_object_or_404(WarehouseZone, pk=pk, warehouse__company=company)
    if request.method == 'POST':
        form = WarehouseZoneForm(request.POST, instance=zone)
        bin_formset = WarehouseBinFormSet(request.POST, instance=zone)
        if form.is_valid() and bin_formset.is_valid():
            form.save()
            bin_formset.save()
            messages.success(request, 'تم تحديث المنطقة بنجاح.')
            return redirect('erp:zone_detail', pk=zone.pk)
    else:
        form = WarehouseZoneForm(instance=zone)
        bin_formset = WarehouseBinFormSet(instance=zone)
    return render(request, 'erp/inventory/zone_form.html', {
        'form': form, 'bin_formset': bin_formset, 'warehouse': zone.warehouse,
        'title': 'تعديل منطقة', 'submit_text': 'حفظ التغييرات', 'zone': zone,
    })


@staff_member_required
def zone_delete(request, pk):
    company = get_user_company(request.user)
    zone = get_object_or_404(WarehouseZone, pk=pk, warehouse__company=company)
    wh_pk = zone.warehouse_id
    if request.method == 'POST':
        zone.delete()
        messages.success(request, 'تم حذف المنطقة بنجاح.')
        return redirect('erp:warehouse_detail', pk=wh_pk)
    return render(request, 'erp/confirm_delete.html', {
        'object': zone, 'object_type': 'منطقة مستودع',
        'cancel_url': reverse('erp:zone_detail', args=[pk]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  UNIT OF MEASURE
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def uom_list(request):
    company = get_user_company(request.user)
    uoms = UnitOfMeasure.objects.filter(company=company)
    return render(request, 'erp/inventory/uom_list.html', {'uoms': uoms.order_by('category', 'name')})


@staff_member_required
def uom_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = UnitOfMeasureForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, f'تم إنشاء وحدة القياس "{obj.name}" بنجاح.')
            return redirect('erp:uom_list')
    else:
        form = UnitOfMeasureForm(company=company)
    return render(request, 'erp/inventory/uom_form.html', {
        'form': form, 'title': 'إنشاء وحدة قياس', 'submit_text': 'حفظ',
    })


@staff_member_required
def uom_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(UnitOfMeasure, pk=pk, company=company)
    if request.method == 'POST':
        form = UnitOfMeasureForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث وحدة القياس بنجاح.')
            return redirect('erp:uom_list')
    else:
        form = UnitOfMeasureForm(instance=obj, company=company)
    return render(request, 'erp/inventory/uom_form.html', {
        'form': form, 'title': 'تعديل وحدة قياس', 'submit_text': 'حفظ التغييرات',
    })


@staff_member_required
def uom_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(UnitOfMeasure, pk=pk, company=company)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'تم حذف وحدة القياس بنجاح.')
        return redirect('erp:uom_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': obj, 'object_type': 'وحدة قياس',
        'cancel_url': reverse('erp:uom_list'),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  LOT / BATCH
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def lot_list(request):
    company = get_user_company(request.user)
    lots = LotBatch.objects.filter(company=company).select_related('product', 'supplier')
    search = request.GET.get('search', '').strip()
    if search:
        lots = lots.filter(
            Q(lot_number__icontains=search) | Q(product__name__icontains=search)
        )
    return render(request, 'erp/inventory/lot_list.html', {'lots': lots.order_by('-created_at')[:200]})


@staff_member_required
def lot_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = LotBatchForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, f'تم إنشاء الدفعة "{obj.lot_number}" بنجاح.')
            return redirect('erp:lot_list')
    else:
        form = LotBatchForm(company=company)
    return render(request, 'erp/inventory/lot_form.html', {
        'form': form, 'title': 'إنشاء دفعة', 'submit_text': 'حفظ',
    })


@staff_member_required
def lot_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(LotBatch, pk=pk, company=company)
    if request.method == 'POST':
        form = LotBatchForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الدفعة بنجاح.')
            return redirect('erp:lot_list')
    else:
        form = LotBatchForm(instance=obj, company=company)
    return render(request, 'erp/inventory/lot_form.html', {
        'form': form, 'title': 'تعديل دفعة', 'submit_text': 'حفظ التغييرات',
    })


@staff_member_required
def lot_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(LotBatch, pk=pk, company=company)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'تم حذف الدفعة بنجاح.')
        return redirect('erp:lot_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': obj, 'object_type': 'دفعة/لوط',
        'cancel_url': reverse('erp:lot_list'),
    })


# ── Serial Numbers ──────────────────────────────────────────────────────────

@staff_member_required
def serial_list(request):
    company = get_user_company(request.user)
    serials = SerialNumber.objects.filter(company=company).select_related(
        'product', 'lot', 'warehouse'
    )
    search = request.GET.get('search', '').strip()
    if search:
        serials = serials.filter(
            Q(serial_number__icontains=search) | Q(product__name__icontains=search)
        )
    status_filter = request.GET.get('status')
    if status_filter:
        serials = serials.filter(status=status_filter)
    return render(request, 'erp/inventory/serial_list.html', {
        'serials': serials.order_by('-created_at')[:200],
        'status_choices': SerialNumber.Status.choices,
    })


@staff_member_required
def serial_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = SerialNumberForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, f'تم إنشاء الرقم التسلسلي "{obj.serial_number}" بنجاح.')
            return redirect('erp:serial_list')
    else:
        form = SerialNumberForm(company=company)
    return render(request, 'erp/inventory/serial_form.html', {
        'form': form, 'title': 'إنشاء رقم تسلسلي', 'submit_text': 'حفظ',
    })


@staff_member_required
def serial_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(SerialNumber, pk=pk, company=company)
    if request.method == 'POST':
        form = SerialNumberForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الرقم التسلسلي بنجاح.')
            return redirect('erp:serial_list')
    else:
        form = SerialNumberForm(instance=obj, company=company)
    return render(request, 'erp/inventory/serial_form.html', {
        'form': form, 'title': 'تعديل رقم تسلسلي', 'submit_text': 'حفظ التغييرات',
    })


# ═══════════════════════════════════════════════════════════════════════════
#  GOODS RECEIPT NOTE (GRN)
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def grn_list(request):
    company = get_user_company(request.user)
    grns = GoodsReceiptNote.objects.filter(company=company).select_related(
        'supplier', 'warehouse', 'purchase_order'
    )
    search = request.GET.get('search', '').strip()
    if search:
        grns = grns.filter(
            Q(grn_number__icontains=search) | Q(supplier__name__icontains=search)
        )
    status_filter = request.GET.get('status')
    if status_filter:
        grns = grns.filter(status=status_filter)
    return render(request, 'erp/inventory/grn_list.html', {
        'grns': grns.order_by('-receipt_date', '-created_at')[:200],
    })


@staff_member_required
def grn_detail(request, pk):
    company = get_user_company(request.user)
    grn = get_object_or_404(GoodsReceiptNote, pk=pk, company=company)
    lines = grn.lines.select_related('product', 'po_line', 'bin', 'lot').all()
    return render(request, 'erp/inventory/grn_detail.html', {
        'grn': grn, 'lines': lines,
    })


@staff_member_required
def grn_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias
    db = get_current_db_alias()
    if request.method == 'POST':
        form = GoodsReceiptNoteForm(request.POST, company=company)
        formset = GoodsReceiptLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            grn = form.save(commit=False)
            grn.company = company
            grn.grn_number = SequenceService.get_next_number(
                company, 'goods_receipt', db_alias=db
            )
            grn.received_by = request.user
            grn.save()
            formset.instance = grn
            formset.save()
            messages.success(request, f'تم إنشاء إذن استلام البضائع {grn.grn_number} بنجاح.')
            return redirect('erp:grn_detail', pk=grn.pk)
    else:
        form = GoodsReceiptNoteForm(company=company)
        formset = GoodsReceiptLineFormSet()
    return render(request, 'erp/inventory/grn_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'إنشاء إذن استلام بضائع', 'submit_text': 'حفظ',
    })


@staff_member_required
def grn_edit(request, pk):
    company = get_user_company(request.user)
    grn = get_object_or_404(GoodsReceiptNote, pk=pk, company=company)
    if grn.status != 'draft':
        messages.error(request, 'لا يمكن تعديل إذن استلام مؤكد.')
        return redirect('erp:grn_detail', pk=grn.pk)
    if request.method == 'POST':
        form = GoodsReceiptNoteForm(request.POST, instance=grn, company=company)
        formset = GoodsReceiptLineFormSet(request.POST, instance=grn)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'تم تحديث إذن استلام البضائع بنجاح.')
            return redirect('erp:grn_detail', pk=grn.pk)
    else:
        form = GoodsReceiptNoteForm(instance=grn, company=company)
        formset = GoodsReceiptLineFormSet(instance=grn)
    return render(request, 'erp/inventory/grn_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'تعديل إذن استلام بضائع', 'submit_text': 'حفظ التغييرات', 'grn': grn,
    })


@staff_member_required
def grn_confirm(request, pk):
    """Confirm a GRN → creates stock movements and updates PO status."""
    company = get_user_company(request.user)
    grn = get_object_or_404(GoodsReceiptNote, pk=pk, company=company)
    if request.method == 'POST':
        if grn.status != 'draft':
            messages.error(request, 'هذا الإذن مؤكد بالفعل.')
            return redirect('erp:grn_detail', pk=grn.pk)
        try:
            from erp.services.inventory import confirm_goods_receipt
            confirm_goods_receipt(grn.pk, request.user)
            messages.success(request, f'تم تأكيد إذن الاستلام {grn.grn_number} بنجاح.')
        except Exception as e:
            messages.error(request, f'فشل تأكيد الإذن: {e}')
    return redirect('erp:grn_detail', pk=grn.pk)


@staff_member_required
def grn_delete(request, pk):
    company = get_user_company(request.user)
    grn = get_object_or_404(GoodsReceiptNote, pk=pk, company=company)
    if grn.status != 'draft':
        messages.error(request, 'لا يمكن حذف إذن مؤكد.')
        return redirect('erp:grn_detail', pk=grn.pk)
    if request.method == 'POST':
        grn.delete()
        messages.success(request, 'تم حذف إذن الاستلام بنجاح.')
        return redirect('erp:grn_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': grn, 'object_type': 'إذن استلام بضائع',
        'cancel_url': reverse('erp:grn_detail', args=[pk]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  STOCK TRANSFER
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def transfer_list(request):
    company = get_user_company(request.user)
    transfers = StockTransfer.objects.filter(company=company).select_related(
        'from_warehouse', 'to_warehouse'
    )
    search = request.GET.get('search', '').strip()
    if search:
        transfers = transfers.filter(
            Q(transfer_number__icontains=search) |
            Q(from_warehouse__name__icontains=search) |
            Q(to_warehouse__name__icontains=search)
        )
    status_filter = request.GET.get('status')
    if status_filter:
        transfers = transfers.filter(status=status_filter)
    return render(request, 'erp/inventory/transfer_list.html', {
        'transfers': transfers.order_by('-transfer_date', '-created_at')[:200],
    })


@staff_member_required
def transfer_detail(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    lines = transfer.lines.select_related('product', 'lot').all()
    return render(request, 'erp/inventory/transfer_detail.html', {
        'transfer': transfer, 'lines': lines,
    })


@staff_member_required
def transfer_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias
    db = get_current_db_alias()
    if request.method == 'POST':
        form = StockTransferForm(request.POST, company=company)
        formset = StockTransferLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.transfer_number = SequenceService.get_next_number(
                company, 'stock_transfer', db_alias=db
            )
            obj.created_by = request.user
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(request, f'تم إنشاء تحويل المخزون {obj.transfer_number} بنجاح.')
            return redirect('erp:transfer_detail', pk=obj.pk)
    else:
        form = StockTransferForm(company=company)
        formset = StockTransferLineFormSet()
    return render(request, 'erp/inventory/transfer_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'إنشاء تحويل مخزون', 'submit_text': 'حفظ',
    })


@staff_member_required
def transfer_edit(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    if transfer.status != 'draft':
        messages.error(request, 'لا يمكن تعديل تحويل غير مسودة.')
        return redirect('erp:transfer_detail', pk=transfer.pk)
    if request.method == 'POST':
        form = StockTransferForm(request.POST, instance=transfer, company=company)
        formset = StockTransferLineFormSet(request.POST, instance=transfer)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'تم تحديث تحويل المخزون بنجاح.')
            return redirect('erp:transfer_detail', pk=transfer.pk)
    else:
        form = StockTransferForm(instance=transfer, company=company)
        formset = StockTransferLineFormSet(instance=transfer)
    return render(request, 'erp/inventory/transfer_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'تعديل تحويل مخزون', 'submit_text': 'حفظ التغييرات', 'transfer': transfer,
    })


@staff_member_required
def transfer_ship(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    if request.method == 'POST':
        try:
            from erp.services.inventory import ship_stock_transfer
            ship_stock_transfer(transfer.pk, request.user)
            messages.success(request, f'تم شحن التحويل {transfer.transfer_number} بنجاح.')
        except Exception as e:
            messages.error(request, f'فشل شحن التحويل: {e}')
    return redirect('erp:transfer_detail', pk=transfer.pk)


@staff_member_required
def transfer_receive(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    if request.method == 'POST':
        try:
            from erp.services.inventory import receive_stock_transfer
            receive_stock_transfer(transfer.pk, request.user)
            messages.success(request, f'تم استلام التحويل {transfer.transfer_number} بنجاح.')
        except Exception as e:
            messages.error(request, f'فشل استلام التحويل: {e}')
    return redirect('erp:transfer_detail', pk=transfer.pk)


@staff_member_required
def transfer_delete(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    if transfer.status != 'draft':
        messages.error(request, 'لا يمكن حذف تحويل غير مسودة.')
        return redirect('erp:transfer_detail', pk=transfer.pk)
    if request.method == 'POST':
        transfer.delete()
        messages.success(request, 'تم حذف التحويل بنجاح.')
        return redirect('erp:transfer_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': transfer, 'object_type': 'تحويل مخزون',
        'cancel_url': reverse('erp:transfer_detail', args=[pk]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  STOCK ADJUSTMENT
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def adjustment_list(request):
    company = get_user_company(request.user)
    adjustments = StockAdjustment.objects.filter(company=company).select_related('warehouse')
    status_filter = request.GET.get('status')
    if status_filter:
        adjustments = adjustments.filter(status=status_filter)
    return render(request, 'erp/inventory/adjustment_list.html', {
        'adjustments': adjustments.order_by('-adjustment_date', '-created_at')[:200],
    })


@staff_member_required
def adjustment_detail(request, pk):
    company = get_user_company(request.user)
    adj = get_object_or_404(StockAdjustment, pk=pk, company=company)
    lines = adj.lines.select_related('product', 'bin', 'lot').all()
    return render(request, 'erp/inventory/adjustment_detail.html', {
        'adjustment': adj, 'lines': lines,
    })


@staff_member_required
def adjustment_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias
    db = get_current_db_alias()
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST, company=company)
        formset = StockAdjustmentLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.adjustment_number = SequenceService.get_next_number(
                company, 'stock_adjustment', db_alias=db
            )
            obj.created_by = request.user
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(request, f'تم إنشاء تسوية المخزون {obj.adjustment_number} بنجاح.')
            return redirect('erp:adjustment_detail', pk=obj.pk)
    else:
        form = StockAdjustmentForm(company=company)
        formset = StockAdjustmentLineFormSet()
    return render(request, 'erp/inventory/adjustment_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'إنشاء تسوية مخزون', 'submit_text': 'حفظ',
    })


@staff_member_required
def adjustment_edit(request, pk):
    company = get_user_company(request.user)
    adj = get_object_or_404(StockAdjustment, pk=pk, company=company)
    if adj.status != 'draft':
        messages.error(request, 'لا يمكن تعديل تسوية غير مسودة.')
        return redirect('erp:adjustment_detail', pk=adj.pk)
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST, instance=adj, company=company)
        formset = StockAdjustmentLineFormSet(request.POST, instance=adj)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'تم تحديث تسوية المخزون بنجاح.')
            return redirect('erp:adjustment_detail', pk=adj.pk)
    else:
        form = StockAdjustmentForm(instance=adj, company=company)
        formset = StockAdjustmentLineFormSet(instance=adj)
    return render(request, 'erp/inventory/adjustment_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'تعديل تسوية مخزون', 'submit_text': 'حفظ التغييرات', 'adjustment': adj,
    })


@staff_member_required
def adjustment_approve(request, pk):
    company = get_user_company(request.user)
    adj = get_object_or_404(StockAdjustment, pk=pk, company=company)
    if request.method == 'POST':
        try:
            from erp.services.inventory import approve_stock_adjustment
            approve_stock_adjustment(adj.pk, request.user)
            messages.success(request, f'تم اعتماد التسوية {adj.adjustment_number} بنجاح.')
        except Exception as e:
            messages.error(request, f'فشل اعتماد التسوية: {e}')
    return redirect('erp:adjustment_detail', pk=adj.pk)


@staff_member_required
def adjustment_delete(request, pk):
    company = get_user_company(request.user)
    adj = get_object_or_404(StockAdjustment, pk=pk, company=company)
    if adj.status not in ('draft', 'pending'):
        messages.error(request, 'لا يمكن حذف تسوية معتمدة.')
        return redirect('erp:adjustment_detail', pk=adj.pk)
    if request.method == 'POST':
        adj.delete()
        messages.success(request, 'تم حذف التسوية بنجاح.')
        return redirect('erp:adjustment_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': adj, 'object_type': 'تسوية مخزون',
        'cancel_url': reverse('erp:adjustment_detail', args=[pk]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  CYCLE COUNT
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def cycle_count_list(request):
    company = get_user_company(request.user)
    counts = CycleCount.objects.filter(company=company).select_related('warehouse', 'zone')
    status_filter = request.GET.get('status')
    if status_filter:
        counts = counts.filter(status=status_filter)
    return render(request, 'erp/inventory/cycle_count_list.html', {
        'counts': counts.order_by('-count_date', '-created_at')[:200],
    })


@staff_member_required
def cycle_count_detail(request, pk):
    company = get_user_company(request.user)
    cc = get_object_or_404(CycleCount, pk=pk, company=company)
    lines = cc.lines.select_related('product', 'bin', 'lot').all()
    return render(request, 'erp/inventory/cycle_count_detail.html', {
        'count': cc, 'lines': lines,
    })


@staff_member_required
def cycle_count_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias
    db = get_current_db_alias()
    if request.method == 'POST':
        form = CycleCountForm(request.POST, company=company)
        formset = CycleCountLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.count_number = SequenceService.get_next_number(
                company, 'cycle_count', db_alias=db
            )
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(request, f'تم إنشاء الجرد {obj.count_number} بنجاح.')
            return redirect('erp:cycle_count_detail', pk=obj.pk)
    else:
        form = CycleCountForm(company=company)
        formset = CycleCountLineFormSet()
    return render(request, 'erp/inventory/cycle_count_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'إنشاء جرد دوري', 'submit_text': 'حفظ',
    })


@staff_member_required
def cycle_count_edit(request, pk):
    company = get_user_company(request.user)
    cc = get_object_or_404(CycleCount, pk=pk, company=company)
    if cc.status not in ('planned', 'in_progress'):
        messages.error(request, 'لا يمكن تعديل جرد مكتمل.')
        return redirect('erp:cycle_count_detail', pk=cc.pk)
    if request.method == 'POST':
        form = CycleCountForm(request.POST, instance=cc, company=company)
        formset = CycleCountLineFormSet(request.POST, instance=cc)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'تم تحديث الجرد بنجاح.')
            return redirect('erp:cycle_count_detail', pk=cc.pk)
    else:
        form = CycleCountForm(instance=cc, company=company)
        formset = CycleCountLineFormSet(instance=cc)
    return render(request, 'erp/inventory/cycle_count_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'تعديل جرد دوري', 'submit_text': 'حفظ التغييرات', 'count': cc,
    })


@staff_member_required
def cycle_count_complete(request, pk):
    company = get_user_company(request.user)
    cc = get_object_or_404(CycleCount, pk=pk, company=company)
    if request.method == 'POST':
        try:
            from erp.services.inventory import complete_cycle_count
            complete_cycle_count(cc.pk, request.user)
            messages.success(request, f'تم إكمال الجرد {cc.count_number} بنجاح.')
        except Exception as e:
            messages.error(request, f'فشل إكمال الجرد: {e}')
    return redirect('erp:cycle_count_detail', pk=cc.pk)


@staff_member_required
def cycle_count_delete(request, pk):
    company = get_user_company(request.user)
    cc = get_object_or_404(CycleCount, pk=pk, company=company)
    if cc.status == 'completed':
        messages.error(request, 'لا يمكن حذف جرد مكتمل.')
        return redirect('erp:cycle_count_detail', pk=cc.pk)
    if request.method == 'POST':
        cc.delete()
        messages.success(request, 'تم حذف الجرد بنجاح.')
        return redirect('erp:cycle_count_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': cc, 'object_type': 'جرد دوري',
        'cancel_url': reverse('erp:cycle_count_detail', args=[pk]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  PICK LIST
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def pick_list_list(request):
    company = get_user_company(request.user)
    picks = PickList.objects.filter(company=company).select_related('warehouse', 'assigned_to')
    status_filter = request.GET.get('status')
    if status_filter:
        picks = picks.filter(status=status_filter)
    return render(request, 'erp/inventory/pick_list_list.html', {
        'picks': picks.order_by('-pick_date', '-created_at')[:200],
    })


@staff_member_required
def pick_list_detail(request, pk):
    company = get_user_company(request.user)
    pick = get_object_or_404(PickList, pk=pk, company=company)
    lines = pick.lines.select_related('product', 'from_bin', 'lot').all()
    return render(request, 'erp/inventory/pick_list_detail.html', {
        'pick': pick, 'lines': lines,
    })


@staff_member_required
def pick_list_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias
    db = get_current_db_alias()
    if request.method == 'POST':
        form = PickListForm(request.POST, company=company)
        formset = PickListLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.pick_number = SequenceService.get_next_number(
                company, 'pick_list', db_alias=db
            )
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(request, f'تم إنشاء قائمة الانتقاء {obj.pick_number} بنجاح.')
            return redirect('erp:pick_list_detail', pk=obj.pk)
    else:
        form = PickListForm(company=company)
        formset = PickListLineFormSet()
    return render(request, 'erp/inventory/pick_list_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'إنشاء قائمة انتقاء', 'submit_text': 'حفظ',
    })


@staff_member_required
def pick_list_edit(request, pk):
    company = get_user_company(request.user)
    pick = get_object_or_404(PickList, pk=pk, company=company)
    if pick.status not in ('draft', 'in_progress'):
        messages.error(request, 'لا يمكن تعديل قائمة انتقاء مكتملة.')
        return redirect('erp:pick_list_detail', pk=pick.pk)
    if request.method == 'POST':
        form = PickListForm(request.POST, instance=pick, company=company)
        formset = PickListLineFormSet(request.POST, instance=pick)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'تم تحديث قائمة الانتقاء بنجاح.')
            return redirect('erp:pick_list_detail', pk=pick.pk)
    else:
        form = PickListForm(instance=pick, company=company)
        formset = PickListLineFormSet(instance=pick)
    return render(request, 'erp/inventory/pick_list_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'تعديل قائمة انتقاء', 'submit_text': 'حفظ التغييرات', 'pick': pick,
    })


@staff_member_required
def pick_list_complete(request, pk):
    company = get_user_company(request.user)
    pick = get_object_or_404(PickList, pk=pk, company=company)
    if request.method == 'POST':
        try:
            from erp.services.inventory import complete_pick_list
            complete_pick_list(pick.pk, request.user)
            messages.success(request, f'تم إكمال قائمة الانتقاء {pick.pick_number} بنجاح.')
        except Exception as e:
            messages.error(request, f'فشل إكمال قائمة الانتقاء: {e}')
    return redirect('erp:pick_list_detail', pk=pick.pk)


@staff_member_required
def pick_list_delete(request, pk):
    company = get_user_company(request.user)
    pick = get_object_or_404(PickList, pk=pk, company=company)
    if pick.status == 'picked':
        messages.error(request, 'لا يمكن حذف قائمة انتقاء مكتملة.')
        return redirect('erp:pick_list_detail', pk=pick.pk)
    if request.method == 'POST':
        pick.delete()
        messages.success(request, 'تم حذف قائمة الانتقاء بنجاح.')
        return redirect('erp:pick_list_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': pick, 'object_type': 'قائمة انتقاء',
        'cancel_url': reverse('erp:pick_list_detail', args=[pk]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  SHIPMENT NOTE
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def shipment_list(request):
    company = get_user_company(request.user)
    shipments = ShipmentNote.objects.filter(company=company).select_related(
        'warehouse', 'customer', 'pick_list'
    )
    search = request.GET.get('search', '').strip()
    if search:
        shipments = shipments.filter(
            Q(shipment_number__icontains=search) |
            Q(tracking_number__icontains=search) |
            Q(customer__name__icontains=search)
        )
    status_filter = request.GET.get('status')
    if status_filter:
        shipments = shipments.filter(status=status_filter)
    return render(request, 'erp/inventory/shipment_list.html', {
        'shipments': shipments.order_by('-shipment_date', '-created_at')[:200],
    })


@staff_member_required
def shipment_detail(request, pk):
    company = get_user_company(request.user)
    shipment = get_object_or_404(ShipmentNote, pk=pk, company=company)
    lines = shipment.lines.select_related('product', 'lot').all()
    return render(request, 'erp/inventory/shipment_detail.html', {
        'shipment': shipment, 'lines': lines,
    })


@staff_member_required
def shipment_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias
    db = get_current_db_alias()
    if request.method == 'POST':
        form = ShipmentNoteForm(request.POST, company=company)
        formset = ShipmentLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.shipment_number = SequenceService.get_next_number(
                company, 'shipment', db_alias=db
            )
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(request, f'تم إنشاء إذن الشحن {obj.shipment_number} بنجاح.')
            return redirect('erp:shipment_detail', pk=obj.pk)
    else:
        form = ShipmentNoteForm(company=company)
        formset = ShipmentLineFormSet()
    return render(request, 'erp/inventory/shipment_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'إنشاء إذن شحن', 'submit_text': 'حفظ',
    })


@staff_member_required
def shipment_edit(request, pk):
    company = get_user_company(request.user)
    shipment = get_object_or_404(ShipmentNote, pk=pk, company=company)
    if shipment.status != 'draft':
        messages.error(request, 'لا يمكن تعديل إذن شحن غير مسودة.')
        return redirect('erp:shipment_detail', pk=shipment.pk)
    if request.method == 'POST':
        form = ShipmentNoteForm(request.POST, instance=shipment, company=company)
        formset = ShipmentLineFormSet(request.POST, instance=shipment)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'تم تحديث إذن الشحن بنجاح.')
            return redirect('erp:shipment_detail', pk=shipment.pk)
    else:
        form = ShipmentNoteForm(instance=shipment, company=company)
        formset = ShipmentLineFormSet(instance=shipment)
    return render(request, 'erp/inventory/shipment_form.html', {
        'form': form, 'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'title': 'تعديل إذن شحن', 'submit_text': 'حفظ التغييرات', 'shipment': shipment,
    })


@staff_member_required
def shipment_ship(request, pk):
    company = get_user_company(request.user)
    shipment = get_object_or_404(ShipmentNote, pk=pk, company=company)
    if request.method == 'POST':
        try:
            from erp.services.inventory import ship_shipment
            ship_shipment(shipment.pk, request.user)
            messages.success(request, f'تم شحن الإذن {shipment.shipment_number} بنجاح.')
        except Exception as e:
            messages.error(request, f'فشل الشحن: {e}')
    return redirect('erp:shipment_detail', pk=shipment.pk)


@staff_member_required
def shipment_delete(request, pk):
    company = get_user_company(request.user)
    shipment = get_object_or_404(ShipmentNote, pk=pk, company=company)
    if shipment.status != 'draft':
        messages.error(request, 'لا يمكن حذف إذن شحن غير مسودة.')
        return redirect('erp:shipment_detail', pk=shipment.pk)
    if request.method == 'POST':
        shipment.delete()
        messages.success(request, 'تم حذف إذن الشحن بنجاح.')
        return redirect('erp:shipment_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': shipment, 'object_type': 'إذن شحن',
        'cancel_url': reverse('erp:shipment_detail', args=[pk]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  REORDER RULES
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def reorder_rule_list(request):
    company = get_user_company(request.user)
    rules = ReorderRule.objects.filter(company=company).select_related(
        'product', 'warehouse', 'preferred_supplier'
    )
    return render(request, 'erp/inventory/reorder_rule_list.html', {
        'rules': rules.order_by('product__name'),
    })


@staff_member_required
def reorder_rule_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = ReorderRuleForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, 'تم إنشاء قاعدة إعادة الطلب بنجاح.')
            return redirect('erp:reorder_rule_list')
    else:
        form = ReorderRuleForm(company=company)
    return render(request, 'erp/inventory/reorder_rule_form.html', {
        'form': form, 'title': 'إنشاء قاعدة إعادة طلب', 'submit_text': 'حفظ',
    })


@staff_member_required
def reorder_rule_edit(request, pk):
    company = get_user_company(request.user)
    rule = get_object_or_404(ReorderRule, pk=pk, company=company)
    if request.method == 'POST':
        form = ReorderRuleForm(request.POST, instance=rule, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث قاعدة إعادة الطلب بنجاح.')
            return redirect('erp:reorder_rule_list')
    else:
        form = ReorderRuleForm(instance=rule, company=company)
    return render(request, 'erp/inventory/reorder_rule_form.html', {
        'form': form, 'title': 'تعديل قاعدة إعادة طلب', 'submit_text': 'حفظ التغييرات',
    })


@staff_member_required
def reorder_rule_delete(request, pk):
    company = get_user_company(request.user)
    rule = get_object_or_404(ReorderRule, pk=pk, company=company)
    if request.method == 'POST':
        rule.delete()
        messages.success(request, 'تم حذف قاعدة إعادة الطلب بنجاح.')
        return redirect('erp:reorder_rule_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': rule, 'object_type': 'قاعدة إعادة طلب',
        'cancel_url': reverse('erp:reorder_rule_list'),
    })


@staff_member_required
def reorder_suggestions(request):
    """Show products that need reordering based on reorder rules."""
    company = get_user_company(request.user)
    from erp.services.inventory import get_reorder_suggestions
    suggestions = get_reorder_suggestions(company)
    return render(request, 'erp/inventory/reorder_suggestions.html', {
        'suggestions': suggestions,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  STOCK MOVEMENTS (read-only ledger)
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def stock_movement_list(request):
    company = get_user_company(request.user)
    movements = StockMovement.objects.filter(company=company).select_related(
        'product', 'warehouse', 'bin', 'lot', 'performed_by'
    )
    search = request.GET.get('search', '').strip()
    if search:
        movements = movements.filter(
            Q(reference_number__icontains=search) |
            Q(product__name__icontains=search) |
            Q(description__icontains=search)
        )
    movement_type = request.GET.get('type')
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        movements = movements.filter(warehouse_id=warehouse_id)
    product_id = request.GET.get('product')
    if product_id:
        movements = movements.filter(product_id=product_id)

    return render(request, 'erp/inventory/movement_list.html', {
        'movements': movements.order_by('-movement_date', '-created_at')[:200],
        'movement_types': StockMovement.MovementType.choices,
        'warehouses': Warehouse.objects.filter(company=company, is_active=True),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  STOCK LEVELS DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def stock_levels(request):
    """Dashboard showing stock levels across all warehouses."""
    company = get_user_company(request.user)
    warehouse_id = request.GET.get('warehouse')

    items_qs = StockItem.objects.filter(
        warehouse__company=company
    ).select_related('product', 'warehouse', 'bin', 'lot')

    if warehouse_id:
        items_qs = items_qs.filter(warehouse_id=warehouse_id)

    search = request.GET.get('search', '').strip()
    if search:
        items_qs = items_qs.filter(
            Q(product__name__icontains=search) |
            Q(product__sku__icontains=search)
        )

    # Show only items with stock
    items_qs = items_qs.filter(on_hand__gt=0)

    return render(request, 'erp/inventory/stock_levels.html', {
        'items': items_qs.order_by('product__name', 'warehouse__name')[:500],
        'warehouses': Warehouse.objects.filter(company=company, is_active=True),
        'selected_warehouse': warehouse_id,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  VALUATION CONFIG
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def valuation_config(request):
    company = get_user_company(request.user)
    config, _ = InventoryValuationConfig.objects.get_or_create(company=company)
    if request.method == 'POST':
        form = InventoryValuationConfigForm(request.POST, instance=config, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم حفظ إعدادات تقييم المخزون بنجاح.')
            return redirect('erp:valuation_config')
    else:
        form = InventoryValuationConfigForm(instance=config, company=company)
    return render(request, 'erp/inventory/valuation_config.html', {
        'form': form,
    })
