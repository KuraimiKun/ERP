"""
ERP Forms – Inventory & Warehouse Management

Forms and formsets for:
  Warehouse, WarehouseZone, WarehouseBin, UnitOfMeasure, UnitOfMeasureConversion,
  LotBatch, SerialNumber, GoodsReceiptNote, GoodsReceiptLine,
  StockTransfer, StockTransferLine, StockAdjustment, StockAdjustmentLine,
  CycleCount, CycleCountLine, PickList, PickListLine,
  ShipmentNote, ShipmentLine, ReorderRule, InventoryValuationConfig
"""
from django import forms

from erp.models import (
    UnitOfMeasure, UnitOfMeasureConversion,
    Warehouse, WarehouseZone, WarehouseBin,
    LotBatch, SerialNumber,
    GoodsReceiptNote, GoodsReceiptLine,
    StockTransfer, StockTransferLine,
    StockAdjustment, StockAdjustmentLine,
    CycleCount, CycleCountLine,
    PickList, PickListLine,
    ShipmentNote, ShipmentLine,
    ReorderRule, InventoryValuationConfig,
)
from .mixins import BootstrapFormMixin, CompanyFilterMixin


# ── UoM ─────────────────────────────────────────────────────────────────────

class UnitOfMeasureForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = ['name', 'name_ar', 'abbreviation', 'category', 'is_base', 'is_active']


class UnitOfMeasureConversionForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = UnitOfMeasureConversion
        fields = ['from_uom', 'to_uom', 'factor']


# ── Warehouse / Zone / Bin ──────────────────────────────────────────────────

class WarehouseForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = [
            'code', 'name', 'name_ar', 'address', 'city', 'country',
            'manager', 'is_active', 'notes',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class WarehouseZoneForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WarehouseZone
        fields = ['code', 'name', 'name_ar', 'zone_type', 'is_active']


WarehouseZoneFormSet = forms.inlineformset_factory(
    Warehouse, WarehouseZone,
    form=WarehouseZoneForm,
    extra=1,
    can_delete=True,
)


class WarehouseBinForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WarehouseBin
        fields = ['code', 'name', 'barcode', 'max_capacity', 'is_active']


WarehouseBinFormSet = forms.inlineformset_factory(
    WarehouseZone, WarehouseBin,
    form=WarehouseBinForm,
    extra=1,
    can_delete=True,
)


# ── Lot / Batch & Serial ───────────────────────────────────────────────────

class LotBatchForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = LotBatch
        fields = [
            'product', 'lot_number', 'manufacture_date', 'expiry_date',
            'supplier', 'notes',
        ]
        widgets = {
            'manufacture_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class SerialNumberForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = SerialNumber
        fields = [
            'product', 'serial_number', 'lot', 'status',
            'warehouse', 'bin', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


# ── Goods Receipt Note ─────────────────────────────────────────────────────

class GoodsReceiptNoteForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = GoodsReceiptNote
        fields = ['grn_number', 'receipt_date', 'purchase_order', 'supplier', 'warehouse', 'notes']
        widgets = {
            'receipt_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['grn_number'].widget.attrs['readonly'] = True


class GoodsReceiptLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = GoodsReceiptLine
        fields = [
            'po_line', 'product', 'quantity_ordered', 'quantity_received',
            'quantity_accepted', 'quantity_rejected', 'unit_cost', 'bin', 'lot', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 1}),
        }


GoodsReceiptLineFormSet = forms.inlineformset_factory(
    GoodsReceiptNote, GoodsReceiptLine,
    form=GoodsReceiptLineForm,
    extra=1,
    can_delete=True,
)


# ── Stock Transfer ──────────────────────────────────────────────────────────

class StockTransferForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = [
            'transfer_number', 'transfer_date',
            'from_warehouse', 'to_warehouse', 'notes',
        ]
        widgets = {
            'transfer_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['transfer_number'].widget.attrs['readonly'] = True


class StockTransferLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StockTransferLine
        fields = ['product', 'quantity', 'from_bin', 'to_bin', 'lot', 'unit_cost', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 1}),
        }


StockTransferLineFormSet = forms.inlineformset_factory(
    StockTransfer, StockTransferLine,
    form=StockTransferLineForm,
    extra=1,
    can_delete=True,
)


# ── Stock Adjustment ────────────────────────────────────────────────────────

class StockAdjustmentForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = [
            'adjustment_number', 'adjustment_date', 'adjustment_type',
            'warehouse', 'reason', 'notes',
        ]
        widgets = {
            'adjustment_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['adjustment_number'].widget.attrs['readonly'] = True


class StockAdjustmentLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StockAdjustmentLine
        fields = ['product', 'bin', 'lot', 'quantity', 'unit_cost', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 1}),
        }


StockAdjustmentLineFormSet = forms.inlineformset_factory(
    StockAdjustment, StockAdjustmentLine,
    form=StockAdjustmentLineForm,
    extra=1,
    can_delete=True,
)


# ── Cycle Count ─────────────────────────────────────────────────────────────

class CycleCountForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = CycleCount
        fields = ['count_number', 'count_date', 'warehouse', 'zone', 'notes']
        widgets = {
            'count_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['count_number'].widget.attrs['readonly'] = True


class CycleCountLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CycleCountLine
        fields = ['product', 'bin', 'lot', 'system_quantity', 'counted_quantity']


CycleCountLineFormSet = forms.inlineformset_factory(
    CycleCount, CycleCountLine,
    form=CycleCountLineForm,
    extra=1,
    can_delete=True,
)


# ── Pick List ───────────────────────────────────────────────────────────────

class PickListForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = PickList
        fields = ['pick_number', 'pick_date', 'warehouse', 'invoice', 'assigned_to', 'notes']
        widgets = {
            'pick_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['pick_number'].widget.attrs['readonly'] = True


class PickListLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PickListLine
        fields = ['product', 'from_bin', 'lot', 'quantity_requested', 'quantity_picked', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 1}),
        }


PickListLineFormSet = forms.inlineformset_factory(
    PickList, PickListLine,
    form=PickListLineForm,
    extra=1,
    can_delete=True,
)


# ── Shipment Note ───────────────────────────────────────────────────────────

class ShipmentNoteForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = ShipmentNote
        fields = [
            'shipment_number', 'shipment_date', 'warehouse', 'pick_list',
            'customer', 'carrier_name', 'tracking_number', 'notes',
        ]
        widgets = {
            'shipment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['shipment_number'].widget.attrs['readonly'] = True


class ShipmentLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ShipmentLine
        fields = ['product', 'lot', 'quantity', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 1}),
        }


ShipmentLineFormSet = forms.inlineformset_factory(
    ShipmentNote, ShipmentLine,
    form=ShipmentLineForm,
    extra=1,
    can_delete=True,
)


# ── Reorder Rule ────────────────────────────────────────────────────────────

class ReorderRuleForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = ReorderRule
        fields = [
            'product', 'warehouse', 'reorder_point', 'safety_stock',
            'min_order_qty', 'max_order_qty', 'lead_time_days',
            'preferred_supplier', 'is_active',
        ]


# ── Valuation Config ───────────────────────────────────────────────────────

class InventoryValuationConfigForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = InventoryValuationConfig
        fields = [
            'valuation_method',
            'inventory_account', 'cogs_account', 'grni_account',
            'adjustment_account', 'write_off_account',
        ]
