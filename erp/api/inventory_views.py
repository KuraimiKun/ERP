"""
ERP API ViewSets – Inventory & Warehouse Management
"""

import logging

from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from ..models import (
    UnitOfMeasure, UnitOfMeasureConversion,
    Warehouse, WarehouseZone, WarehouseBin,
    LotBatch, SerialNumber, StockItem, StockMovement,
    GoodsReceiptNote, StockTransfer, StockAdjustment,
    CycleCount, PickList, ShipmentNote,
    ReorderRule, InventoryValuationConfig,
)
from .views import ERPBaseViewSet
from .inventory_serializers import (
    UnitOfMeasureSerializer, UnitOfMeasureConversionSerializer,
    WarehouseSerializer, WarehouseListSerializer,
    WarehouseZoneSerializer, WarehouseBinSerializer,
    LotBatchSerializer, SerialNumberSerializer,
    StockItemSerializer, StockMovementSerializer,
    GoodsReceiptNoteSerializer, GoodsReceiptNoteListSerializer,
    StockTransferSerializer,
    StockAdjustmentSerializer,
    CycleCountSerializer,
    PickListSerializer,
    ShipmentNoteSerializer,
    ReorderRuleSerializer,
    InventoryValuationConfigSerializer,
)

logger = logging.getLogger('erp.api.inventory')


# ── UoM ─────────────────────────────────────────────────────────

class UnitOfMeasureViewSet(ERPBaseViewSet):
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    search_fields = ['name', 'abbreviation']
    filterset_fields = ['category', 'is_base', 'is_active']
    ordering_fields = ['name', 'category']
    ordering = ['name']


class UnitOfMeasureConversionViewSet(ERPBaseViewSet):
    queryset = UnitOfMeasureConversion.objects.all()
    serializer_class = UnitOfMeasureConversionSerializer


# ── Warehouse / Zone / Bin ──────────────────────────────────────

class WarehouseViewSet(ERPBaseViewSet):
    queryset = Warehouse.objects.select_related('manager').all()
    serializer_class = WarehouseSerializer
    search_fields = ['code', 'name', 'city']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'code', 'city', 'created_at']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return WarehouseListSerializer
        return WarehouseSerializer

    @method_decorator(cache_page(60 * 30))  # 30 minutes – master data
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 30))
    @method_decorator(vary_on_cookie)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class WarehouseZoneViewSet(ERPBaseViewSet):
    queryset = WarehouseZone.objects.select_related('warehouse')
    serializer_class = WarehouseZoneSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['warehouse', 'zone_type', 'is_active']
    ordering_fields = ['name', 'code']
    ordering = ['name']

    def get_queryset(self):
        qs = super().get_queryset()
        company = self.get_company()
        return qs.filter(warehouse__company=company)


class WarehouseBinViewSet(ERPBaseViewSet):
    queryset = WarehouseBin.objects.select_related('zone', 'zone__warehouse')
    serializer_class = WarehouseBinSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['is_active']
    ordering_fields = ['code', 'name']
    ordering = ['code']

    def get_queryset(self):
        qs = super().get_queryset()
        company = self.get_company()
        return qs.filter(zone__warehouse__company=company)


# ── Lot / Serial ───────────────────────────────────────────────

class LotBatchViewSet(ERPBaseViewSet):
    queryset = LotBatch.objects.select_related('product', 'supplier').all()
    serializer_class = LotBatchSerializer
    search_fields = ['lot_number', 'product__name']
    filterset_fields = ['product', 'supplier']
    ordering_fields = ['lot_number', 'manufacture_date', 'expiry_date', 'created_at']
    ordering = ['-created_at']


class SerialNumberViewSet(ERPBaseViewSet):
    queryset = SerialNumber.objects.select_related('product', 'warehouse').all()
    serializer_class = SerialNumberSerializer
    search_fields = ['serial_number', 'product__name']
    filterset_fields = ['status', 'product', 'warehouse']
    ordering_fields = ['serial_number', 'created_at']
    ordering = ['-created_at']


# ── Stock Item / Movement ──────────────────────────────────────

class StockItemViewSet(ERPBaseViewSet):
    queryset = StockItem.objects.select_related('product', 'warehouse', 'bin', 'lot').all()
    serializer_class = StockItemSerializer
    search_fields = ['product__name', 'product__sku']
    filterset_fields = ['warehouse', 'product']
    ordering_fields = ['quantity', 'product__name', 'warehouse__name']
    ordering = ['product__name']
    http_method_names = ['get', 'head', 'options']  # Read-only

    def get_queryset(self):
        qs = super().get_queryset()
        company = self.get_company()
        return qs.filter(warehouse__company=company)

    @method_decorator(cache_page(60 * 5))  # 5 minutes – stock changes
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class StockMovementViewSet(ERPBaseViewSet):
    queryset = StockMovement.objects.select_related(
        'product', 'warehouse', 'performed_by'
    ).all()
    serializer_class = StockMovementSerializer
    search_fields = ['reference_number', 'product__name', 'description']
    filterset_fields = ['movement_type', 'warehouse', 'product']
    ordering_fields = ['movement_date', 'created_at']
    ordering = ['-movement_date']
    http_method_names = ['get', 'head', 'options']  # Read-only


# ── GRN ────────────────────────────────────────────────────────

class GoodsReceiptNoteViewSet(ERPBaseViewSet):
    queryset = GoodsReceiptNote.objects.select_related(
        'supplier', 'warehouse', 'purchase_order'
    ).all()
    serializer_class = GoodsReceiptNoteSerializer
    search_fields = ['grn_number', 'supplier__name']
    filterset_fields = ['status', 'warehouse', 'supplier']
    ordering_fields = ['grn_number', 'received_date', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return GoodsReceiptNoteListSerializer
        return GoodsReceiptNoteSerializer

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        grn = self.get_object()
        if grn.status != 'draft':
            return Response({'error': 'Only draft GRNs can be confirmed.'}, status=400)
        try:
            from erp.services.inventory import confirm_goods_receipt
            confirm_goods_receipt(grn.pk, request.user)
            grn.refresh_from_db()
            return Response(GoodsReceiptNoteSerializer(grn).data)
        except Exception as e:
            logger.exception("Inventory action failed: %s", e)
            return Response({'error': 'Operation failed.'}, status=400)


# ── Stock Transfer ─────────────────────────────────────────────

class StockTransferViewSet(ERPBaseViewSet):
    queryset = StockTransfer.objects.select_related(
        'from_warehouse', 'to_warehouse'
    ).all()
    serializer_class = StockTransferSerializer
    search_fields = ['transfer_number']
    filterset_fields = ['status', 'from_warehouse', 'to_warehouse']
    ordering_fields = ['transfer_number', 'created_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        transfer = self.get_object()
        try:
            from erp.services.inventory import ship_stock_transfer
            ship_stock_transfer(transfer.pk, request.user)
            transfer.refresh_from_db()
            return Response(StockTransferSerializer(transfer).data)
        except Exception as e:
            logger.exception("Inventory action failed: %s", e)
            return Response({'error': 'Operation failed.'}, status=400)

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        transfer = self.get_object()
        try:
            from erp.services.inventory import receive_stock_transfer
            receive_stock_transfer(transfer.pk, request.user)
            transfer.refresh_from_db()
            return Response(StockTransferSerializer(transfer).data)
        except Exception as e:
            logger.exception("Inventory action failed: %s", e)
            return Response({'error': 'Operation failed.'}, status=400)


# ── Stock Adjustment ───────────────────────────────────────────

class StockAdjustmentViewSet(ERPBaseViewSet):
    queryset = StockAdjustment.objects.select_related('warehouse').all()
    serializer_class = StockAdjustmentSerializer
    search_fields = ['adjustment_number', 'reason']
    filterset_fields = ['status', 'adjustment_type', 'warehouse']
    ordering_fields = ['adjustment_number', 'created_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        adj = self.get_object()
        try:
            from erp.services.inventory import approve_stock_adjustment
            approve_stock_adjustment(adj.pk, request.user)
            adj.refresh_from_db()
            return Response(StockAdjustmentSerializer(adj).data)
        except Exception as e:
            logger.exception("Inventory action failed: %s", e)
            return Response({'error': 'Operation failed.'}, status=400)


# ── Cycle Count ────────────────────────────────────────────────

class CycleCountViewSet(ERPBaseViewSet):
    queryset = CycleCount.objects.select_related('warehouse', 'zone').all()
    serializer_class = CycleCountSerializer
    search_fields = ['count_number']
    filterset_fields = ['status', 'warehouse']
    ordering_fields = ['count_number', 'created_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        cc = self.get_object()
        try:
            from erp.services.inventory import complete_cycle_count
            complete_cycle_count(cc.pk, request.user)
            cc.refresh_from_db()
            return Response(CycleCountSerializer(cc).data)
        except Exception as e:
            logger.exception("Inventory action failed: %s", e)
            return Response({'error': 'Operation failed.'}, status=400)


# ── Pick List ──────────────────────────────────────────────────

class PickListViewSet(ERPBaseViewSet):
    queryset = PickList.objects.select_related('warehouse', 'assigned_to').all()
    serializer_class = PickListSerializer
    search_fields = ['pick_number']
    filterset_fields = ['status', 'warehouse', 'assigned_to']
    ordering_fields = ['pick_number', 'created_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        pick = self.get_object()
        try:
            from erp.services.inventory import complete_pick_list
            complete_pick_list(pick.pk, request.user)
            pick.refresh_from_db()
            return Response(PickListSerializer(pick).data)
        except Exception as e:
            logger.exception("Inventory action failed: %s", e)
            return Response({'error': 'Operation failed.'}, status=400)


# ── Shipment ───────────────────────────────────────────────────

class ShipmentNoteViewSet(ERPBaseViewSet):
    queryset = ShipmentNote.objects.select_related(
        'warehouse', 'customer', 'pick_list'
    ).all()
    serializer_class = ShipmentNoteSerializer
    search_fields = ['shipment_number', 'tracking_number', 'customer__name']
    filterset_fields = ['status', 'warehouse', 'customer']
    ordering_fields = ['shipment_number', 'shipped_date', 'created_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        shipment = self.get_object()
        try:
            from erp.services.inventory import ship_shipment
            ship_shipment(shipment.pk, request.user)
            shipment.refresh_from_db()
            return Response(ShipmentNoteSerializer(shipment).data)
        except Exception as e:
            logger.exception("Inventory action failed: %s", e)
            return Response({'error': 'Operation failed.'}, status=400)


# ── Reorder Rule ───────────────────────────────────────────────

class ReorderRuleViewSet(ERPBaseViewSet):
    queryset = ReorderRule.objects.select_related(
        'product', 'warehouse', 'preferred_supplier'
    ).all()
    serializer_class = ReorderRuleSerializer
    search_fields = ['product__name', 'product__sku']
    filterset_fields = ['warehouse', 'is_active', 'preferred_supplier']
    ordering_fields = ['product__name', 'reorder_point', 'created_at']
    ordering = ['product__name']

    @action(detail=False, methods=['get'])
    def suggestions(self, request):
        """Return products that need reordering."""
        from erp.services.inventory import get_reorder_suggestions
        company = self.get_company()
        suggestions = get_reorder_suggestions(company)
        return Response(suggestions)


# ── Valuation Config ──────────────────────────────────────────

class InventoryValuationConfigViewSet(ERPBaseViewSet):
    queryset = InventoryValuationConfig.objects.all()
    serializer_class = InventoryValuationConfigSerializer
