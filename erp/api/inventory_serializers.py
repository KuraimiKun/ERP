"""
ERP API Serializers – Inventory & Warehouse Management
"""

from rest_framework import serializers
from ..models import (
    UnitOfMeasure, UnitOfMeasureConversion,
    Warehouse, WarehouseZone, WarehouseBin,
    LotBatch, SerialNumber, StockItem, StockMovement,
    GoodsReceiptNote, GoodsReceiptLine,
    StockTransfer, StockTransferLine,
    StockAdjustment, StockAdjustmentLine,
    CycleCount, CycleCountLine,
    PickList, PickListLine,
    ShipmentNote, ShipmentLine,
    ReorderRule, InventoryValuationConfig,
)


# ── UoM ─────────────────────────────────────────────────────────

class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = [
            'id', 'company', 'name', 'name_ar', 'abbreviation',
            'category', 'is_base', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class UnitOfMeasureConversionSerializer(serializers.ModelSerializer):
    from_uom_name = serializers.CharField(source='from_uom.name', read_only=True)
    to_uom_name = serializers.CharField(source='to_uom.name', read_only=True)

    class Meta:
        model = UnitOfMeasureConversion
        fields = [
            'id', 'company', 'from_uom', 'from_uom_name',
            'to_uom', 'to_uom_name', 'factor',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# ── Warehouse / Zone / Bin ──────────────────────────────────────

class WarehouseBinSerializer(serializers.ModelSerializer):
    class Meta:
        model = WarehouseBin
        fields = [
            'id', 'zone', 'code', 'name', 'barcode',
            'max_capacity', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class WarehouseZoneSerializer(serializers.ModelSerializer):
    bins = WarehouseBinSerializer(many=True, read_only=True)
    bins_count = serializers.IntegerField(source='bins.count', read_only=True)

    class Meta:
        model = WarehouseZone
        fields = [
            'id', 'warehouse', 'code', 'name', 'name_ar', 'zone_type',
            'is_active', 'bins', 'bins_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class WarehouseSerializer(serializers.ModelSerializer):
    zones = WarehouseZoneSerializer(many=True, read_only=True)
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            'id', 'company', 'code', 'name', 'name_ar',
            'address', 'city', 'country', 'manager', 'manager_name',
            'is_active', 'notes', 'zones', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_manager_name(self, obj):
        return str(obj.manager) if obj.manager else None


class WarehouseListSerializer(serializers.ModelSerializer):
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            'id', 'code', 'name', 'city', 'manager_name', 'is_active',
        ]

    def get_manager_name(self, obj):
        return str(obj.manager) if obj.manager else None


# ── Lot / Serial ───────────────────────────────────────────────

class LotBatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = LotBatch
        fields = [
            'id', 'company', 'product', 'product_name', 'lot_number',
            'manufacture_date', 'expiry_date', 'is_expired',
            'supplier', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class SerialNumberSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SerialNumber
        fields = [
            'id', 'company', 'product', 'product_name', 'serial_number',
            'lot', 'status', 'warehouse', 'bin', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# ── Stock Item & Movement ──────────────────────────────────────

class StockItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    available = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)

    class Meta:
        model = StockItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'warehouse', 'warehouse_name', 'bin', 'lot',
            'on_hand', 'allocated', 'in_transit',
            'unit_cost', 'available', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            'id', 'company', 'product', 'product_name',
            'warehouse', 'warehouse_name', 'bin', 'lot',
            'movement_type', 'quantity', 'unit_cost', 'total_cost',
            'reference_type', 'reference_id', 'reference_number',
            'description', 'performed_by', 'performed_by_name',
            'movement_date', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_performed_by_name(self, obj):
        return str(obj.performed_by) if obj.performed_by else None


# ── GRN ────────────────────────────────────────────────────────

class GoodsReceiptLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = GoodsReceiptLine
        fields = [
            'id', 'grn', 'po_line', 'product', 'product_name',
            'quantity_ordered', 'quantity_received', 'quantity_accepted',
            'quantity_rejected', 'unit_cost', 'bin', 'lot', 'notes',
        ]


class GoodsReceiptNoteSerializer(serializers.ModelSerializer):
    lines = GoodsReceiptLineSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = GoodsReceiptNote
        fields = [
            'id', 'company', 'grn_number', 'receipt_date',
            'purchase_order', 'supplier', 'supplier_name',
            'warehouse', 'warehouse_name', 'status',
            'notes', 'lines',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'grn_number']


class GoodsReceiptNoteListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = GoodsReceiptNote
        fields = [
            'id', 'grn_number', 'receipt_date', 'supplier_name',
            'warehouse_name', 'status', 'created_at',
        ]


# ── Stock Transfer ─────────────────────────────────────────────

class StockTransferLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = StockTransferLine
        fields = [
            'id', 'transfer', 'product', 'product_name',
            'quantity', 'from_bin', 'to_bin', 'lot', 'unit_cost', 'notes',
        ]


class StockTransferSerializer(serializers.ModelSerializer):
    lines = StockTransferLineSerializer(many=True, read_only=True)
    from_warehouse_name = serializers.CharField(source='from_warehouse.name', read_only=True)
    to_warehouse_name = serializers.CharField(source='to_warehouse.name', read_only=True)

    class Meta:
        model = StockTransfer
        fields = [
            'id', 'company', 'transfer_number', 'transfer_date',
            'from_warehouse', 'from_warehouse_name',
            'to_warehouse', 'to_warehouse_name',
            'status', 'shipped_date', 'received_date',
            'notes', 'lines', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'transfer_number']


# ── Stock Adjustment ───────────────────────────────────────────

class StockAdjustmentLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = StockAdjustmentLine
        fields = [
            'id', 'adjustment', 'product', 'product_name',
            'bin', 'lot', 'quantity', 'unit_cost', 'notes',
        ]


class StockAdjustmentSerializer(serializers.ModelSerializer):
    lines = StockAdjustmentLineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'company', 'adjustment_number', 'adjustment_date',
            'adjustment_type', 'warehouse', 'warehouse_name', 'status',
            'reason', 'approved_by', 'approved_at', 'notes', 'lines',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'adjustment_number']


# ── Cycle Count ────────────────────────────────────────────────

class CycleCountLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    variance = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)

    class Meta:
        model = CycleCountLine
        fields = [
            'id', 'cycle_count', 'product', 'product_name',
            'bin', 'lot', 'system_quantity', 'counted_quantity', 'variance',
        ]


class CycleCountSerializer(serializers.ModelSerializer):
    lines = CycleCountLineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = CycleCount
        fields = [
            'id', 'company', 'count_number', 'count_date',
            'warehouse', 'warehouse_name', 'zone', 'status',
            'variance_posted', 'notes', 'lines',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'count_number']


# ── Pick List ──────────────────────────────────────────────────

class PickListLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PickListLine
        fields = [
            'id', 'pick_list', 'product', 'product_name',
            'from_bin', 'lot', 'quantity_requested', 'quantity_picked', 'notes',
        ]


class PickListSerializer(serializers.ModelSerializer):
    lines = PickListLineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = PickList
        fields = [
            'id', 'company', 'pick_number', 'pick_date',
            'warehouse', 'warehouse_name', 'invoice',
            'assigned_to', 'status', 'notes', 'lines',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'pick_number']


# ── Shipment ───────────────────────────────────────────────────

class ShipmentLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ShipmentLine
        fields = [
            'id', 'shipment', 'product', 'product_name',
            'lot', 'quantity', 'notes',
        ]


class ShipmentNoteSerializer(serializers.ModelSerializer):
    lines = ShipmentLineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = ShipmentNote
        fields = [
            'id', 'company', 'shipment_number', 'shipment_date',
            'warehouse', 'warehouse_name', 'pick_list',
            'customer', 'customer_name', 'carrier_name',
            'tracking_number', 'status', 'notes', 'lines',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'shipment_number']

    def get_customer_name(self, obj):
        return str(obj.customer) if obj.customer else None


# ── Reorder Rule ───────────────────────────────────────────────

class ReorderRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = ReorderRule
        fields = [
            'id', 'company', 'product', 'product_name',
            'warehouse', 'warehouse_name',
            'reorder_point', 'safety_stock',
            'min_order_qty', 'max_order_qty', 'lead_time_days',
            'preferred_supplier', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# ── Valuation Config ──────────────────────────────────────────

class InventoryValuationConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryValuationConfig
        fields = [
            'id', 'company', 'valuation_method',
            'inventory_account', 'cogs_account', 'grni_account',
            'adjustment_account', 'write_off_account',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
