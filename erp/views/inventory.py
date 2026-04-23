"""
ERP Views – Inventory & Warehouse Management

Full CRUD + workflow actions for warehouses, zones, bins, lots/serials,
goods receipt notes, stock transfers, stock adjustments, cycle counts,
pick lists, shipments, reorder rules, stock movements, and valuation config.
"""

from django.db.models import Q, Sum
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.models import (
    Product,
    Warehouse,
    WarehouseZone,
    UnitOfMeasure,
    LotBatch,
    SerialNumber,
    StockItem,
    StockMovement,
    GoodsReceiptNote,
    StockTransfer,
    StockAdjustment,
    CycleCount,
    PickList,
    ShipmentNote,
    ReorderRule,
    InventoryValuationConfig,
)
from erp.forms.inventory import (
    WarehouseForm,
    WarehouseZoneForm,
    WarehouseZoneFormSet,
    WarehouseBinFormSet,
    UnitOfMeasureForm,
    LotBatchForm,
    SerialNumberForm,
    GoodsReceiptNoteForm,
    GoodsReceiptLineFormSet,
    StockTransferForm,
    StockTransferLineFormSet,
    StockAdjustmentForm,
    StockAdjustmentLineFormSet,
    CycleCountForm,
    CycleCountLineFormSet,
    PickListForm,
    PickListLineFormSet,
    ShipmentNoteForm,
    ShipmentLineFormSet,
    ReorderRuleForm,
    InventoryValuationConfigForm,
)
from erp.services.sequence import SequenceService
from ._common import (
    render,
    get_object_or_404,
    redirect,
    messages,
    reverse,
    get_user_company,
    staff_member_required,
    paginate_qs,
    apply_sorting,
)


# ═══════════════════════════════════════════════════════════════════════════
#  WAREHOUSES
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def warehouse_list(request):
    company = get_user_company(request.user)
    warehouses = Warehouse.objects.filter(company=company).select_related("manager")
    search = request.GET.get("search", "").strip()
    if search:
        warehouses = warehouses.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(name_ar__icontains=search)
            | Q(city__icontains=search)
        )
    warehouses, current_sort, current_order = apply_sorting(
        request,
        warehouses,
        allowed_fields=["code", "name", "city"],
        default="code",
    )
    page_obj, query_string = paginate_qs(request, warehouses)

    return render(
        request,
        "erp/inventory/warehouse_list.html",
        {
            "warehouses": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def warehouse_detail(request, pk):
    company = get_user_company(request.user)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    zones = warehouse.zones.prefetch_related("bins").all()
    stock_summary = (
        StockItem.objects.filter(warehouse=warehouse, warehouse__company=company)
        .values("product__name", "product__sku", "product_id")
        .annotate(
            total_on_hand=Sum("on_hand"),
            total_allocated=Sum("allocated"),
        )
        .order_by("product__name")[:50]
    )
    return render(
        request,
        "erp/inventory/warehouse_detail.html",
        {
            "warehouse": warehouse,
            "zones": zones,
            "stock_summary": stock_summary,
        },
    )


@staff_member_required
def warehouse_create(request):
    company = get_user_company(request.user)
    if request.method == "POST":
        form = WarehouseForm(request.POST, company=company)
        zone_formset = WarehouseZoneFormSet(request.POST)
        if form.is_valid() and zone_formset.is_valid():
            wh = form.save(commit=False)
            wh.company = company
            wh.save()
            zone_formset.instance = wh
            zone_formset.save()
            messages.success(request, _('Warehouse "%(name)s" created successfully.') % {"name": wh.name})
            return redirect("erp:warehouse_detail", pk=wh.pk)
    else:
        form = WarehouseForm(company=company)
        zone_formset = WarehouseZoneFormSet()
    return render(
        request,
        "erp/inventory/warehouse_form.html",
        {
            "form": form,
            "zone_formset": zone_formset,
            "title": _("Create Warehouse"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def warehouse_edit(request, pk):
    company = get_user_company(request.user)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    if request.method == "POST":
        form = WarehouseForm(request.POST, instance=warehouse, company=company)
        zone_formset = WarehouseZoneFormSet(request.POST, instance=warehouse)
        if form.is_valid() and zone_formset.is_valid():
            form.save()
            zone_formset.save()
            messages.success(request, _("Warehouse updated successfully."))
            return redirect("erp:warehouse_detail", pk=warehouse.pk)
    else:
        form = WarehouseForm(instance=warehouse, company=company)
        zone_formset = WarehouseZoneFormSet(instance=warehouse)
    return render(
        request,
        "erp/inventory/warehouse_form.html",
        {
            "form": form,
            "zone_formset": zone_formset,
            "title": _("Edit Warehouse"),
            "submit_text": _("Save Changes"),
            "warehouse": warehouse,
        },
    )


@staff_member_required
def warehouse_delete(request, pk):
    company = get_user_company(request.user)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    if request.method == "POST":
        warehouse.delete()
        messages.success(request, _("Warehouse deleted successfully."))
        return redirect("erp:warehouse_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": warehouse,
            "object_type": _("Warehouse"),
            "cancel_url": reverse("erp:warehouse_detail", args=[pk]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  WAREHOUSE ZONES & BINS (managed via warehouse detail + standalone)
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def zone_detail(request, pk):
    company = get_user_company(request.user)
    zone = get_object_or_404(WarehouseZone, pk=pk, warehouse__company=company)
    bins = zone.bins.all().order_by("code")
    return render(
        request,
        "erp/inventory/zone_detail.html",
        {
            "zone": zone,
            "bins": bins,
        },
    )


@staff_member_required
def zone_create(request, warehouse_pk):
    company = get_user_company(request.user)
    warehouse = get_object_or_404(Warehouse, pk=warehouse_pk, company=company)
    if request.method == "POST":
        form = WarehouseZoneForm(request.POST)
        bin_formset = WarehouseBinFormSet(request.POST)
        if form.is_valid() and bin_formset.is_valid():
            zone = form.save(commit=False)
            zone.warehouse = warehouse
            zone.save()
            bin_formset.instance = zone
            bin_formset.save()
            messages.success(request, _('Zone "%(name)s" created successfully.') % {"name": zone.name})
            return redirect("erp:warehouse_detail", pk=warehouse.pk)
    else:
        form = WarehouseZoneForm()
        bin_formset = WarehouseBinFormSet()
    return render(
        request,
        "erp/inventory/zone_form.html",
        {
            "form": form,
            "bin_formset": bin_formset,
            "warehouse": warehouse,
            "title": _("Create Zone"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def zone_edit(request, pk):
    company = get_user_company(request.user)
    zone = get_object_or_404(WarehouseZone, pk=pk, warehouse__company=company)
    if request.method == "POST":
        form = WarehouseZoneForm(request.POST, instance=zone)
        bin_formset = WarehouseBinFormSet(request.POST, instance=zone)
        if form.is_valid() and bin_formset.is_valid():
            form.save()
            bin_formset.save()
            messages.success(request, _("Zone updated successfully."))
            return redirect("erp:zone_detail", pk=zone.pk)
    else:
        form = WarehouseZoneForm(instance=zone)
        bin_formset = WarehouseBinFormSet(instance=zone)
    return render(
        request,
        "erp/inventory/zone_form.html",
        {
            "form": form,
            "bin_formset": bin_formset,
            "warehouse": zone.warehouse,
            "title": _("Edit Zone"),
            "submit_text": _("Save Changes"),
            "zone": zone,
        },
    )


@staff_member_required
def zone_delete(request, pk):
    company = get_user_company(request.user)
    zone = get_object_or_404(WarehouseZone, pk=pk, warehouse__company=company)
    wh_pk = zone.warehouse_id
    if request.method == "POST":
        zone.delete()
        messages.success(request, _("Zone deleted successfully."))
        return redirect("erp:warehouse_detail", pk=wh_pk)
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": zone,
            "object_type": _("Warehouse Zone"),
            "cancel_url": reverse("erp:zone_detail", args=[pk]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  UNIT OF MEASURE
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def uom_list(request):
    company = get_user_company(request.user)
    uoms = UnitOfMeasure.objects.filter(company=company)
    uoms, current_sort, current_order = apply_sorting(
        request,
        uoms,
        allowed_fields=["name", "category", "abbreviation"],
        default="name",
    )
    page_obj, query_string = paginate_qs(request, uoms)

    return render(
        request,
        "erp/inventory/uom_list.html",
        {
            "uoms": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def uom_create(request):
    company = get_user_company(request.user)
    if request.method == "POST":
        form = UnitOfMeasureForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, _('Unit of measure "%(name)s" created successfully.') % {"name": obj.name})
            return redirect("erp:uom_list")
    else:
        form = UnitOfMeasureForm(company=company)
    return render(
        request,
        "erp/inventory/uom_form.html",
        {
            "form": form,
            "title": _("Create Unit of Measure"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def uom_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(UnitOfMeasure, pk=pk, company=company)
    if request.method == "POST":
        form = UnitOfMeasureForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Unit of measure updated successfully."))
            return redirect("erp:uom_list")
    else:
        form = UnitOfMeasureForm(instance=obj, company=company)
    return render(
        request,
        "erp/inventory/uom_form.html",
        {
            "form": form,
            "title": _("Edit Unit of Measure"),
            "submit_text": _("Save Changes"),
        },
    )


@staff_member_required
def uom_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(UnitOfMeasure, pk=pk, company=company)
    if request.method == "POST":
        obj.delete()
        messages.success(request, _("Unit of measure deleted successfully."))
        return redirect("erp:uom_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": obj,
            "object_type": _("Unit of Measure"),
            "cancel_url": reverse("erp:uom_list"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  LOT / BATCH
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def lot_list(request):
    company = get_user_company(request.user)
    lots = LotBatch.objects.filter(company=company).select_related("product", "supplier")
    search = request.GET.get("search", "").strip()
    if search:
        lots = lots.filter(Q(lot_number__icontains=search) | Q(product__name__icontains=search))
    lots, current_sort, current_order = apply_sorting(
        request,
        lots,
        allowed_fields=["lot_number", "expiry_date", "created_at"],
        default="-created_at",
    )
    page_obj, query_string = paginate_qs(request, lots)

    return render(
        request,
        "erp/inventory/lot_list.html",
        {
            "lots": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def lot_create(request):
    company = get_user_company(request.user)
    if request.method == "POST":
        form = LotBatchForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, _('Lot/Batch "%(number)s" created successfully.') % {"number": obj.lot_number})
            return redirect("erp:lot_list")
    else:
        form = LotBatchForm(company=company)
    return render(
        request,
        "erp/inventory/lot_form.html",
        {
            "form": form,
            "title": _("Create Lot/Batch"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def lot_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(LotBatch, pk=pk, company=company)
    if request.method == "POST":
        form = LotBatchForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Lot/Batch updated successfully."))
            return redirect("erp:lot_list")
    else:
        form = LotBatchForm(instance=obj, company=company)
    return render(
        request,
        "erp/inventory/lot_form.html",
        {
            "form": form,
            "title": _("Edit Lot/Batch"),
            "submit_text": _("Save Changes"),
        },
    )


@staff_member_required
def lot_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(LotBatch, pk=pk, company=company)
    if request.method == "POST":
        obj.delete()
        messages.success(request, _("Lot/Batch deleted successfully."))
        return redirect("erp:lot_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": obj,
            "object_type": _("Lot/Batch"),
            "cancel_url": reverse("erp:lot_list"),
        },
    )


# ── Serial Numbers ──────────────────────────────────────────────────────────


@staff_member_required
def serial_list(request):
    company = get_user_company(request.user)
    serials = SerialNumber.objects.filter(company=company).select_related("product", "lot", "warehouse")
    search = request.GET.get("search", "").strip()
    if search:
        serials = serials.filter(Q(serial_number__icontains=search) | Q(product__name__icontains=search))
    status_filter = request.GET.get("status")
    if status_filter:
        serials = serials.filter(status=status_filter)
    serials, current_sort, current_order = apply_sorting(
        request,
        serials,
        allowed_fields=["serial_number", "status", "created_at"],
        default="-created_at",
    )
    page_obj, query_string = paginate_qs(request, serials)

    return render(
        request,
        "erp/inventory/serial_list.html",
        {
            "serials": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "status_choices": SerialNumber.Status.choices,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def serial_create(request):
    company = get_user_company(request.user)
    if request.method == "POST":
        form = SerialNumberForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(
                request, _('Serial number "%(number)s" created successfully.') % {"number": obj.serial_number}
            )
            return redirect("erp:serial_list")
    else:
        form = SerialNumberForm(company=company)
    return render(
        request,
        "erp/inventory/serial_form.html",
        {
            "form": form,
            "title": _("Create Serial Number"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def serial_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(SerialNumber, pk=pk, company=company)
    if request.method == "POST":
        form = SerialNumberForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Serial number updated successfully."))
            return redirect("erp:serial_list")
    else:
        form = SerialNumberForm(instance=obj, company=company)
    return render(
        request,
        "erp/inventory/serial_form.html",
        {
            "form": form,
            "title": _("Edit Serial Number"),
            "submit_text": _("Save Changes"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  GOODS RECEIPT NOTE (GRN)
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def grn_list(request):
    company = get_user_company(request.user)
    grns = GoodsReceiptNote.objects.filter(company=company).select_related("supplier", "warehouse", "purchase_order")
    search = request.GET.get("search", "").strip()
    if search:
        grns = grns.filter(Q(grn_number__icontains=search) | Q(supplier__name__icontains=search))
    status_filter = request.GET.get("status")
    if status_filter:
        grns = grns.filter(status=status_filter)
    grns, current_sort, current_order = apply_sorting(
        request,
        grns,
        allowed_fields=["grn_number", "receipt_date", "status"],
        default="-receipt_date",
    )
    page_obj, query_string = paginate_qs(request, grns)

    return render(
        request,
        "erp/inventory/grn_list.html",
        {
            "grns": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def grn_detail(request, pk):
    company = get_user_company(request.user)
    grn = get_object_or_404(GoodsReceiptNote, pk=pk, company=company)
    lines = grn.lines.select_related("product", "po_line", "bin", "lot").all()
    return render(
        request,
        "erp/inventory/grn_detail.html",
        {
            "grn": grn,
            "lines": lines,
        },
    )


@staff_member_required
def grn_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias

    db = get_current_db_alias()
    if request.method == "POST":
        form = GoodsReceiptNoteForm(request.POST, company=company)
        formset = GoodsReceiptLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            grn = form.save(commit=False)
            grn.company = company
            grn.grn_number = SequenceService.get_next_number(company, "goods_receipt", db_alias=db)
            grn.received_by = request.user
            grn.save()
            formset.instance = grn
            formset.save()
            messages.success(
                request, _("Goods receipt note %(number)s created successfully.") % {"number": grn.grn_number}
            )
            return redirect("erp:grn_detail", pk=grn.pk)
    else:
        form = GoodsReceiptNoteForm(company=company)
        formset = GoodsReceiptLineFormSet()
    return render(
        request,
        "erp/inventory/grn_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Create Goods Receipt Note"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def grn_edit(request, pk):
    company = get_user_company(request.user)
    grn = get_object_or_404(GoodsReceiptNote, pk=pk, company=company)
    if grn.status != "draft":
        messages.error(request, _("Cannot edit a confirmed goods receipt note."))
        return redirect("erp:grn_detail", pk=grn.pk)
    if request.method == "POST":
        form = GoodsReceiptNoteForm(request.POST, instance=grn, company=company)
        formset = GoodsReceiptLineFormSet(request.POST, instance=grn)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Goods receipt note updated successfully."))
            return redirect("erp:grn_detail", pk=grn.pk)
    else:
        form = GoodsReceiptNoteForm(instance=grn, company=company)
        formset = GoodsReceiptLineFormSet(instance=grn)
    return render(
        request,
        "erp/inventory/grn_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Edit Goods Receipt Note"),
            "submit_text": _("Save Changes"),
            "grn": grn,
        },
    )


@staff_member_required
def grn_confirm(request, pk):
    """Confirm a GRN → creates stock movements and updates PO status."""
    company = get_user_company(request.user)
    grn = get_object_or_404(GoodsReceiptNote, pk=pk, company=company)
    if request.method == "POST":
        if grn.status != "draft":
            messages.error(request, _("This receipt note is already confirmed."))
            return redirect("erp:grn_detail", pk=grn.pk)
        try:
            from erp.services.inventory import confirm_goods_receipt

            confirm_goods_receipt(grn.pk, request.user)
            messages.success(
                request, _("Goods receipt note %(number)s confirmed successfully.") % {"number": grn.grn_number}
            )
        except Exception as e:
            messages.error(request, _("Failed to confirm receipt note: %(error)s") % {"error": e})
    return redirect("erp:grn_detail", pk=grn.pk)


@staff_member_required
def grn_delete(request, pk):
    company = get_user_company(request.user)
    grn = get_object_or_404(GoodsReceiptNote, pk=pk, company=company)
    if grn.status != "draft":
        messages.error(request, _("Cannot delete a confirmed receipt note."))
        return redirect("erp:grn_detail", pk=grn.pk)
    if request.method == "POST":
        grn.delete()
        messages.success(request, _("Goods receipt note deleted successfully."))
        return redirect("erp:grn_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": grn,
            "object_type": _("Goods Receipt Note"),
            "cancel_url": reverse("erp:grn_detail", args=[pk]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  STOCK TRANSFER
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def transfer_list(request):
    company = get_user_company(request.user)
    transfers = StockTransfer.objects.filter(company=company).select_related("from_warehouse", "to_warehouse")
    search = request.GET.get("search", "").strip()
    if search:
        transfers = transfers.filter(
            Q(transfer_number__icontains=search)
            | Q(from_warehouse__name__icontains=search)
            | Q(to_warehouse__name__icontains=search)
        )
    status_filter = request.GET.get("status")
    if status_filter:
        transfers = transfers.filter(status=status_filter)
    transfers, current_sort, current_order = apply_sorting(
        request,
        transfers,
        allowed_fields=["transfer_number", "transfer_date", "status"],
        default="-transfer_date",
    )
    page_obj, query_string = paginate_qs(request, transfers)

    return render(
        request,
        "erp/inventory/transfer_list.html",
        {
            "transfers": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def transfer_detail(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    lines = transfer.lines.select_related("product", "lot").all()
    return render(
        request,
        "erp/inventory/transfer_detail.html",
        {
            "transfer": transfer,
            "lines": lines,
        },
    )


@staff_member_required
def transfer_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias

    db = get_current_db_alias()
    if request.method == "POST":
        form = StockTransferForm(request.POST, company=company)
        formset = StockTransferLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.transfer_number = SequenceService.get_next_number(company, "stock_transfer", db_alias=db)
            obj.created_by = request.user
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(
                request, _("Stock transfer %(number)s created successfully.") % {"number": obj.transfer_number}
            )
            return redirect("erp:transfer_detail", pk=obj.pk)
    else:
        form = StockTransferForm(company=company)
        formset = StockTransferLineFormSet()
    return render(
        request,
        "erp/inventory/transfer_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Create Stock Transfer"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def transfer_edit(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    if transfer.status != "draft":
        messages.error(request, _("Cannot edit a non-draft transfer."))
        return redirect("erp:transfer_detail", pk=transfer.pk)
    if request.method == "POST":
        form = StockTransferForm(request.POST, instance=transfer, company=company)
        formset = StockTransferLineFormSet(request.POST, instance=transfer)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Stock transfer updated successfully."))
            return redirect("erp:transfer_detail", pk=transfer.pk)
    else:
        form = StockTransferForm(instance=transfer, company=company)
        formset = StockTransferLineFormSet(instance=transfer)
    return render(
        request,
        "erp/inventory/transfer_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Edit Stock Transfer"),
            "submit_text": _("Save Changes"),
            "transfer": transfer,
        },
    )


@staff_member_required
def transfer_ship(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    if request.method == "POST":
        try:
            from erp.services.inventory import ship_stock_transfer

            ship_stock_transfer(transfer.pk, request.user)
            messages.success(
                request, _("Transfer %(number)s shipped successfully.") % {"number": transfer.transfer_number}
            )
        except Exception as e:
            messages.error(request, _("Failed to ship transfer: %(error)s") % {"error": e})
    return redirect("erp:transfer_detail", pk=transfer.pk)


@staff_member_required
def transfer_receive(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    if request.method == "POST":
        try:
            from erp.services.inventory import receive_stock_transfer

            receive_stock_transfer(transfer.pk, request.user)
            messages.success(
                request, _("Transfer %(number)s received successfully.") % {"number": transfer.transfer_number}
            )
        except Exception as e:
            messages.error(request, _("Failed to receive transfer: %(error)s") % {"error": e})
    return redirect("erp:transfer_detail", pk=transfer.pk)


@staff_member_required
def transfer_delete(request, pk):
    company = get_user_company(request.user)
    transfer = get_object_or_404(StockTransfer, pk=pk, company=company)
    if transfer.status != "draft":
        messages.error(request, _("Cannot delete a non-draft transfer."))
        return redirect("erp:transfer_detail", pk=transfer.pk)
    if request.method == "POST":
        transfer.delete()
        messages.success(request, _("Stock transfer deleted successfully."))
        return redirect("erp:transfer_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": transfer,
            "object_type": _("Stock Transfer"),
            "cancel_url": reverse("erp:transfer_detail", args=[pk]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  STOCK ADJUSTMENT
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def adjustment_list(request):
    company = get_user_company(request.user)
    adjustments = StockAdjustment.objects.filter(company=company).select_related("warehouse")
    status_filter = request.GET.get("status")
    if status_filter:
        adjustments = adjustments.filter(status=status_filter)
    adjustments, current_sort, current_order = apply_sorting(
        request,
        adjustments,
        allowed_fields=["adjustment_number", "adjustment_date", "adjustment_type", "status"],
        default="-adjustment_date",
    )
    page_obj, query_string = paginate_qs(request, adjustments)

    return render(
        request,
        "erp/inventory/adjustment_list.html",
        {
            "adjustments": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def adjustment_detail(request, pk):
    company = get_user_company(request.user)
    adj = get_object_or_404(StockAdjustment, pk=pk, company=company)
    lines = adj.lines.select_related("product", "bin", "lot").all()
    return render(
        request,
        "erp/inventory/adjustment_detail.html",
        {
            "adjustment": adj,
            "lines": lines,
        },
    )


@staff_member_required
def adjustment_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias

    db = get_current_db_alias()
    if request.method == "POST":
        form = StockAdjustmentForm(request.POST, company=company)
        formset = StockAdjustmentLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.adjustment_number = SequenceService.get_next_number(company, "stock_adjustment", db_alias=db)
            obj.created_by = request.user
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(
                request, _("Stock adjustment %(number)s created successfully.") % {"number": obj.adjustment_number}
            )
            return redirect("erp:adjustment_detail", pk=obj.pk)
    else:
        form = StockAdjustmentForm(company=company)
        formset = StockAdjustmentLineFormSet()
    return render(
        request,
        "erp/inventory/adjustment_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Create Stock Adjustment"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def adjustment_edit(request, pk):
    company = get_user_company(request.user)
    adj = get_object_or_404(StockAdjustment, pk=pk, company=company)
    if adj.status != "draft":
        messages.error(request, _("Cannot edit a non-draft adjustment."))
        return redirect("erp:adjustment_detail", pk=adj.pk)
    if request.method == "POST":
        form = StockAdjustmentForm(request.POST, instance=adj, company=company)
        formset = StockAdjustmentLineFormSet(request.POST, instance=adj)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Stock adjustment updated successfully."))
            return redirect("erp:adjustment_detail", pk=adj.pk)
    else:
        form = StockAdjustmentForm(instance=adj, company=company)
        formset = StockAdjustmentLineFormSet(instance=adj)
    return render(
        request,
        "erp/inventory/adjustment_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Edit Stock Adjustment"),
            "submit_text": _("Save Changes"),
            "adjustment": adj,
        },
    )


@staff_member_required
def adjustment_approve(request, pk):
    company = get_user_company(request.user)
    adj = get_object_or_404(StockAdjustment, pk=pk, company=company)
    if request.method == "POST":
        try:
            from erp.services.inventory import approve_stock_adjustment

            approve_stock_adjustment(adj.pk, request.user)
            messages.success(
                request, _("Adjustment %(number)s approved successfully.") % {"number": adj.adjustment_number}
            )
        except Exception as e:
            messages.error(request, _("Failed to approve adjustment: %(error)s") % {"error": e})
    return redirect("erp:adjustment_detail", pk=adj.pk)


@staff_member_required
def adjustment_delete(request, pk):
    company = get_user_company(request.user)
    adj = get_object_or_404(StockAdjustment, pk=pk, company=company)
    if adj.status not in ("draft", "pending"):
        messages.error(request, _("Cannot delete an approved adjustment."))
        return redirect("erp:adjustment_detail", pk=adj.pk)
    if request.method == "POST":
        adj.delete()
        messages.success(request, _("Stock adjustment deleted successfully."))
        return redirect("erp:adjustment_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": adj,
            "object_type": _("Stock Adjustment"),
            "cancel_url": reverse("erp:adjustment_detail", args=[pk]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  CYCLE COUNT
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def cycle_count_list(request):
    company = get_user_company(request.user)
    counts = CycleCount.objects.filter(company=company).select_related("warehouse", "zone")
    status_filter = request.GET.get("status")
    if status_filter:
        counts = counts.filter(status=status_filter)
    counts, current_sort, current_order = apply_sorting(
        request,
        counts,
        allowed_fields=["count_number", "count_date", "status"],
        default="-count_date",
    )
    page_obj, query_string = paginate_qs(request, counts)

    return render(
        request,
        "erp/inventory/cycle_count_list.html",
        {
            "counts": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def cycle_count_detail(request, pk):
    company = get_user_company(request.user)
    cc = get_object_or_404(CycleCount, pk=pk, company=company)
    lines = cc.lines.select_related("product", "bin", "lot").all()
    return render(
        request,
        "erp/inventory/cycle_count_detail.html",
        {
            "count": cc,
            "lines": lines,
        },
    )


@staff_member_required
def cycle_count_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias

    db = get_current_db_alias()
    if request.method == "POST":
        form = CycleCountForm(request.POST, company=company)
        formset = CycleCountLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.count_number = SequenceService.get_next_number(company, "cycle_count", db_alias=db)
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(request, _("Cycle count %(number)s created successfully.") % {"number": obj.count_number})
            return redirect("erp:cycle_count_detail", pk=obj.pk)
    else:
        form = CycleCountForm(company=company)
        formset = CycleCountLineFormSet()
    return render(
        request,
        "erp/inventory/cycle_count_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Create Cycle Count"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def cycle_count_edit(request, pk):
    company = get_user_company(request.user)
    cc = get_object_or_404(CycleCount, pk=pk, company=company)
    if cc.status not in ("planned", "in_progress"):
        messages.error(request, _("Cannot edit a completed cycle count."))
        return redirect("erp:cycle_count_detail", pk=cc.pk)
    if request.method == "POST":
        form = CycleCountForm(request.POST, instance=cc, company=company)
        formset = CycleCountLineFormSet(request.POST, instance=cc)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Cycle count updated successfully."))
            return redirect("erp:cycle_count_detail", pk=cc.pk)
    else:
        form = CycleCountForm(instance=cc, company=company)
        formset = CycleCountLineFormSet(instance=cc)
    return render(
        request,
        "erp/inventory/cycle_count_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Edit Cycle Count"),
            "submit_text": _("Save Changes"),
            "count": cc,
        },
    )


@staff_member_required
def cycle_count_complete(request, pk):
    company = get_user_company(request.user)
    cc = get_object_or_404(CycleCount, pk=pk, company=company)
    if request.method == "POST":
        try:
            from erp.services.inventory import complete_cycle_count

            complete_cycle_count(cc.pk, request.user)
            messages.success(request, _("Cycle count %(number)s completed successfully.") % {"number": cc.count_number})
        except Exception as e:
            messages.error(request, _("Failed to complete cycle count: %(error)s") % {"error": e})
    return redirect("erp:cycle_count_detail", pk=cc.pk)


@staff_member_required
def cycle_count_delete(request, pk):
    company = get_user_company(request.user)
    cc = get_object_or_404(CycleCount, pk=pk, company=company)
    if cc.status == "completed":
        messages.error(request, _("Cannot delete a completed cycle count."))
        return redirect("erp:cycle_count_detail", pk=cc.pk)
    if request.method == "POST":
        cc.delete()
        messages.success(request, _("Cycle count deleted successfully."))
        return redirect("erp:cycle_count_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": cc,
            "object_type": _("Cycle Count"),
            "cancel_url": reverse("erp:cycle_count_detail", args=[pk]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  PICK LIST
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def pick_list_list(request):
    company = get_user_company(request.user)
    picks = PickList.objects.filter(company=company).select_related("warehouse", "assigned_to")
    status_filter = request.GET.get("status")
    if status_filter:
        picks = picks.filter(status=status_filter)
    picks, current_sort, current_order = apply_sorting(
        request,
        picks,
        allowed_fields=["pick_number", "pick_date", "status"],
        default="-pick_date",
    )
    page_obj, query_string = paginate_qs(request, picks)

    return render(
        request,
        "erp/inventory/pick_list_list.html",
        {
            "picks": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def pick_list_detail(request, pk):
    company = get_user_company(request.user)
    pick = get_object_or_404(PickList, pk=pk, company=company)
    lines = pick.lines.select_related("product", "from_bin", "lot").all()
    return render(
        request,
        "erp/inventory/pick_list_detail.html",
        {
            "pick": pick,
            "lines": lines,
        },
    )


@staff_member_required
def pick_list_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias

    db = get_current_db_alias()
    if request.method == "POST":
        form = PickListForm(request.POST, company=company)
        formset = PickListLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.pick_number = SequenceService.get_next_number(company, "pick_list", db_alias=db)
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(request, _("Pick list %(number)s created successfully.") % {"number": obj.pick_number})
            return redirect("erp:pick_list_detail", pk=obj.pk)
    else:
        form = PickListForm(company=company)
        formset = PickListLineFormSet()
    return render(
        request,
        "erp/inventory/pick_list_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Create Pick List"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def pick_list_edit(request, pk):
    company = get_user_company(request.user)
    pick = get_object_or_404(PickList, pk=pk, company=company)
    if pick.status not in ("draft", "in_progress"):
        messages.error(request, _("Cannot edit a completed pick list."))
        return redirect("erp:pick_list_detail", pk=pick.pk)
    if request.method == "POST":
        form = PickListForm(request.POST, instance=pick, company=company)
        formset = PickListLineFormSet(request.POST, instance=pick)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Pick list updated successfully."))
            return redirect("erp:pick_list_detail", pk=pick.pk)
    else:
        form = PickListForm(instance=pick, company=company)
        formset = PickListLineFormSet(instance=pick)
    return render(
        request,
        "erp/inventory/pick_list_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Edit Pick List"),
            "submit_text": _("Save Changes"),
            "pick": pick,
        },
    )


@staff_member_required
def pick_list_complete(request, pk):
    company = get_user_company(request.user)
    pick = get_object_or_404(PickList, pk=pk, company=company)
    if request.method == "POST":
        try:
            from erp.services.inventory import complete_pick_list

            complete_pick_list(pick.pk, request.user)
            messages.success(request, _("Pick list %(number)s completed successfully.") % {"number": pick.pick_number})
        except Exception as e:
            messages.error(request, _("Failed to complete pick list: %(error)s") % {"error": e})
    return redirect("erp:pick_list_detail", pk=pick.pk)


@staff_member_required
def pick_list_delete(request, pk):
    company = get_user_company(request.user)
    pick = get_object_or_404(PickList, pk=pk, company=company)
    if pick.status == "picked":
        messages.error(request, _("Cannot delete a completed pick list."))
        return redirect("erp:pick_list_detail", pk=pick.pk)
    if request.method == "POST":
        pick.delete()
        messages.success(request, _("Pick list deleted successfully."))
        return redirect("erp:pick_list_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": pick,
            "object_type": _("Pick List"),
            "cancel_url": reverse("erp:pick_list_detail", args=[pk]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  SHIPMENT NOTE
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def shipment_list(request):
    company = get_user_company(request.user)
    shipments = ShipmentNote.objects.filter(company=company).select_related("warehouse", "customer", "pick_list")
    search = request.GET.get("search", "").strip()
    if search:
        shipments = shipments.filter(
            Q(shipment_number__icontains=search)
            | Q(tracking_number__icontains=search)
            | Q(customer__name__icontains=search)
        )
    status_filter = request.GET.get("status")
    if status_filter:
        shipments = shipments.filter(status=status_filter)

    shipments, current_sort, current_order = apply_sorting(
        request,
        shipments,
        allowed_fields=["shipment_number", "shipment_date", "status"],
        default="-shipment_date",
    )
    page_obj, query_string = paginate_qs(request, shipments)

    return render(
        request,
        "erp/inventory/shipment_list.html",
        {
            "shipments": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def shipment_detail(request, pk):
    company = get_user_company(request.user)
    shipment = get_object_or_404(ShipmentNote, pk=pk, company=company)
    lines = shipment.lines.select_related("product", "lot").all()
    return render(
        request,
        "erp/inventory/shipment_detail.html",
        {
            "shipment": shipment,
            "lines": lines,
        },
    )


@staff_member_required
def shipment_create(request):
    company = get_user_company(request.user)
    from tenants.routers import get_current_db_alias

    db = get_current_db_alias()
    if request.method == "POST":
        form = ShipmentNoteForm(request.POST, company=company)
        formset = ShipmentLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.shipment_number = SequenceService.get_next_number(company, "shipment", db_alias=db)
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(
                request, _("Shipment note %(number)s created successfully.") % {"number": obj.shipment_number}
            )
            return redirect("erp:shipment_detail", pk=obj.pk)
    else:
        form = ShipmentNoteForm(company=company)
        formset = ShipmentLineFormSet()
    return render(
        request,
        "erp/inventory/shipment_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Create Shipment Note"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def shipment_edit(request, pk):
    company = get_user_company(request.user)
    shipment = get_object_or_404(ShipmentNote, pk=pk, company=company)
    if shipment.status != "draft":
        messages.error(request, _("Cannot edit a non-draft shipment note."))
        return redirect("erp:shipment_detail", pk=shipment.pk)
    if request.method == "POST":
        form = ShipmentNoteForm(request.POST, instance=shipment, company=company)
        formset = ShipmentLineFormSet(request.POST, instance=shipment)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Shipment note updated successfully."))
            return redirect("erp:shipment_detail", pk=shipment.pk)
    else:
        form = ShipmentNoteForm(instance=shipment, company=company)
        formset = ShipmentLineFormSet(instance=shipment)
    return render(
        request,
        "erp/inventory/shipment_form.html",
        {
            "form": form,
            "formset": formset,
            "products": Product.objects.filter(company=company, is_active=True).order_by("name"),
            "title": _("Edit Shipment Note"),
            "submit_text": _("Save Changes"),
            "shipment": shipment,
        },
    )


@staff_member_required
def shipment_ship(request, pk):
    company = get_user_company(request.user)
    shipment = get_object_or_404(ShipmentNote, pk=pk, company=company)
    if request.method == "POST":
        try:
            from erp.services.inventory import ship_shipment

            ship_shipment(shipment.pk, request.user)
            messages.success(
                request, _("Shipment %(number)s shipped successfully.") % {"number": shipment.shipment_number}
            )
        except Exception as e:
            messages.error(request, _("Failed to ship: %(error)s") % {"error": e})
    return redirect("erp:shipment_detail", pk=shipment.pk)


@staff_member_required
def shipment_delete(request, pk):
    company = get_user_company(request.user)
    shipment = get_object_or_404(ShipmentNote, pk=pk, company=company)
    if shipment.status != "draft":
        messages.error(request, _("Cannot delete a non-draft shipment note."))
        return redirect("erp:shipment_detail", pk=shipment.pk)
    if request.method == "POST":
        shipment.delete()
        messages.success(request, _("Shipment note deleted successfully."))
        return redirect("erp:shipment_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": shipment,
            "object_type": _("Shipment Note"),
            "cancel_url": reverse("erp:shipment_detail", args=[pk]),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  REORDER RULES
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def reorder_rule_list(request):
    company = get_user_company(request.user)
    rules = ReorderRule.objects.filter(company=company).select_related("product", "warehouse", "preferred_supplier")

    rules, current_sort, current_order = apply_sorting(
        request,
        rules,
        allowed_fields=["product__name", "reorder_point", "lead_time_days", "is_active"],
        default="product__name",
    )
    page_obj, query_string = paginate_qs(request, rules)

    return render(
        request,
        "erp/inventory/reorder_rule_list.html",
        {
            "rules": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def reorder_rule_create(request):
    company = get_user_company(request.user)
    if request.method == "POST":
        form = ReorderRuleForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, _("Reorder rule created successfully."))
            return redirect("erp:reorder_rule_list")
    else:
        form = ReorderRuleForm(company=company)
    return render(
        request,
        "erp/inventory/reorder_rule_form.html",
        {
            "form": form,
            "title": _("Create Reorder Rule"),
            "submit_text": _("Save"),
        },
    )


@staff_member_required
def reorder_rule_edit(request, pk):
    company = get_user_company(request.user)
    rule = get_object_or_404(ReorderRule, pk=pk, company=company)
    if request.method == "POST":
        form = ReorderRuleForm(request.POST, instance=rule, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Reorder rule updated successfully."))
            return redirect("erp:reorder_rule_list")
    else:
        form = ReorderRuleForm(instance=rule, company=company)
    return render(
        request,
        "erp/inventory/reorder_rule_form.html",
        {
            "form": form,
            "title": _("Edit Reorder Rule"),
            "submit_text": _("Save Changes"),
        },
    )


@staff_member_required
def reorder_rule_delete(request, pk):
    company = get_user_company(request.user)
    rule = get_object_or_404(ReorderRule, pk=pk, company=company)
    if request.method == "POST":
        rule.delete()
        messages.success(request, _("Reorder rule deleted successfully."))
        return redirect("erp:reorder_rule_list")
    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": rule,
            "object_type": _("Reorder Rule"),
            "cancel_url": reverse("erp:reorder_rule_list"),
        },
    )


@staff_member_required
def reorder_suggestions(request):
    """Show products that need reordering based on reorder rules."""
    company = get_user_company(request.user)
    from erp.services.inventory import get_reorder_suggestions

    suggestions = get_reorder_suggestions(company)
    return render(
        request,
        "erp/inventory/reorder_suggestions.html",
        {
            "suggestions": suggestions,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  STOCK MOVEMENTS (read-only ledger)
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def stock_movement_list(request):
    company = get_user_company(request.user)
    movements = StockMovement.objects.filter(company=company).select_related(
        "product", "warehouse", "bin", "lot", "performed_by"
    )
    search = request.GET.get("search", "").strip()
    if search:
        movements = movements.filter(
            Q(reference_number__icontains=search)
            | Q(product__name__icontains=search)
            | Q(description__icontains=search)
        )
    movement_type = request.GET.get("type")
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    warehouse_id = request.GET.get("warehouse")
    if warehouse_id:
        movements = movements.filter(warehouse_id=warehouse_id)
    product_id = request.GET.get("product")
    if product_id:
        movements = movements.filter(product_id=product_id)

    movements, current_sort, current_order = apply_sorting(
        request,
        movements,
        allowed_fields=["movement_date", "movement_type", "quantity", "unit_cost"],
        default="-movement_date",
    )
    page_obj, query_string = paginate_qs(request, movements)

    return render(
        request,
        "erp/inventory/movement_list.html",
        {
            "movements": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "movement_types": StockMovement.MovementType.choices,
            "warehouses": Warehouse.objects.filter(company=company, is_active=True),
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  STOCK LEVELS DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def stock_levels(request):
    """Dashboard showing stock levels across all warehouses."""
    company = get_user_company(request.user)
    warehouse_id = request.GET.get("warehouse")

    items_qs = StockItem.objects.filter(warehouse__company=company).select_related("product", "warehouse", "bin", "lot")

    if warehouse_id:
        items_qs = items_qs.filter(warehouse_id=warehouse_id)

    search = request.GET.get("search", "").strip()
    if search:
        items_qs = items_qs.filter(Q(product__name__icontains=search) | Q(product__sku__icontains=search))

    # Show only items with stock
    items_qs = items_qs.filter(on_hand__gt=0)

    return render(
        request,
        "erp/inventory/stock_levels.html",
        {
            "items": items_qs.order_by("product__name", "warehouse__name")[:500],
            "warehouses": Warehouse.objects.filter(company=company, is_active=True),
            "selected_warehouse": warehouse_id,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
#  VALUATION CONFIG
# ═══════════════════════════════════════════════════════════════════════════


@staff_member_required
def valuation_config(request):
    company = get_user_company(request.user)
    config, _ = InventoryValuationConfig.objects.get_or_create(company=company)
    if request.method == "POST":
        form = InventoryValuationConfigForm(request.POST, instance=config, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Inventory valuation settings saved successfully."))
            return redirect("erp:valuation_config")
    else:
        form = InventoryValuationConfigForm(instance=config, company=company)
    return render(
        request,
        "erp/inventory/valuation_config.html",
        {
            "form": form,
        },
    )
