from django.utils.translation import gettext_lazy as _

"""
Inventory & Warehouse Management models for the ERP system.

Covers:
  - Warehouses / Zones / Bins (location hierarchy)
  - Unit of Measure & conversions
  - Stock Items (per-product per-location quantities)
  - Immutable Stock Movement Ledger
  - Lot / Batch tracking & Serial Numbers
  - Goods Receipt Notes (GRN) tied to Purchase Orders
  - Stock Transfers between warehouses
  - Stock Adjustments (gain / loss / write-off)
  - Cycle Counts with variance posting
  - Pick Lists & Shipment Notes (outbound flow)
  - Reorder Rules (min/max, safety stock, lead-time purchasing)
  - Inventory Valuation Configuration (FIFO / Weighted Average)
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from .base import ERPBaseModel, TimeStampedModel


# =========================================================================
# Unit of Measure
# =========================================================================


class UnitOfMeasure(TimeStampedModel):
    """Unit of Measure definition (e.g. unit, kg, m, litre)."""

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="units_of_measure",
    )
    name = models.CharField(max_length=50)
    name_ar = models.CharField(max_length=50, blank=True)
    abbreviation = models.CharField(max_length=10)
    category = models.CharField(
        max_length=30,
        choices=[
            ("unit", "Unit / Piece"),
            ("weight", "Weight"),
            ("length", "Length"),
            ("volume", "Volume"),
            ("area", "Area"),
            ("time", "Time"),
            ("other", "Other"),
        ],
        default="unit",
    )
    is_base = models.BooleanField(
        default=False,
        help_text=_("Base UoM for its category (conversion factor = 1)"),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Unit of Measure")
        verbose_name_plural = "Units of Measure"
        unique_together = ["company", "abbreviation"]
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.abbreviation} – {self.name}"


class UnitOfMeasureConversion(TimeStampedModel):
    """Conversion factor between two UoMs in the same category."""

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="uom_conversions",
    )
    from_uom = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.CASCADE,
        related_name="conversions_from",
    )
    to_uom = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.CASCADE,
        related_name="conversions_to",
    )
    factor = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=1,
        help_text=_("Multiply from_uom quantity by this factor to get to_uom quantity"),
    )

    class Meta:
        verbose_name = _("UoM Conversion")
        verbose_name_plural = "UoM Conversions"
        unique_together = ["company", "from_uom", "to_uom"]

    def __str__(self):
        return f"1 {self.from_uom.abbreviation} = {self.factor} {self.to_uom.abbreviation}"


# =========================================================================
# Warehouse / Zone / Bin (Location Hierarchy)
# =========================================================================


class Warehouse(ERPBaseModel):
    """Physical warehouse or storage facility."""

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="warehouses",
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    manager = models.ForeignKey(
        "erp.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_warehouses",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Warehouse")
        verbose_name_plural = "Warehouses"
        unique_together = ["company", "code"]
        ordering = ["code"]
        indexes = [
            models.Index(fields=["company", "is_active"], name="idx_wh_company_active"),
        ]

    def __str__(self):
        return f"{self.code} – {self.name}"


class WarehouseZone(TimeStampedModel):
    """Logical zone inside a warehouse (e.g. Receiving, Bulk, Pick Face, Quarantine)."""

    class ZoneType(models.TextChoices):
        RECEIVING = "receiving", "Receiving"
        STORAGE = "storage", "Storage"
        PICKING = "picking", "Picking / Pick Face"
        PACKING = "packing", "Packing"
        SHIPPING = "shipping", "Shipping / Dispatch"
        QUARANTINE = "quarantine", "Quarantine"
        RETURNS = "returns", "Returns"
        OTHER = "other", "Other"

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="zones",
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    zone_type = models.CharField(
        max_length=20,
        choices=ZoneType.choices,
        default=ZoneType.STORAGE,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Warehouse Zone")
        verbose_name_plural = "Warehouse Zones"
        unique_together = ["warehouse", "code"]
        ordering = ["code"]

    def __str__(self):
        return f"{self.warehouse.code}/{self.code} – {self.name}"


class WarehouseBin(TimeStampedModel):
    """Physical or logical bin (slot/shelf) inside a zone."""

    zone = models.ForeignKey(
        WarehouseZone,
        on_delete=models.CASCADE,
        related_name="bins",
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=50, blank=True)
    max_capacity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Max storage capacity (0 = unlimited)"),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Warehouse Bin")
        verbose_name_plural = "Warehouse Bins"
        unique_together = ["zone", "code"]
        ordering = ["code"]

    def __str__(self):
        return f"{self.zone.warehouse.code}/{self.zone.code}/{self.code}"


# =========================================================================
# Lot / Batch & Serial Numbers
# =========================================================================


class LotBatch(ERPBaseModel):
    """Lot or batch of a product for traceability and expiry tracking."""

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="lot_batches",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.CASCADE,
        related_name="lots",
    )
    lot_number = models.CharField(max_length=50)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey(
        "erp.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplied_lots",
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Lot / Batch")
        verbose_name_plural = "Lots / Batches"
        unique_together = ["company", "product", "lot_number"]
        ordering = ["expiry_date", "lot_number"]

    def __str__(self):
        return f"{self.product.sku} – LOT {self.lot_number}"

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False


class SerialNumber(TimeStampedModel):
    """Individual serial number for a product (one-to-one with a physical unit)."""

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ALLOCATED = "allocated", "Allocated"
        SOLD = "sold", "Sold / Shipped"
        QUARANTINE = "quarantine", "Quarantine"
        RETURNED = "returned", "Returned"
        SCRAPPED = "scrapped", "Scrapped"

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="serial_numbers",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.CASCADE,
        related_name="serial_numbers",
    )
    serial_number = models.CharField(max_length=100)
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serial_numbers",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serial_numbers",
    )
    bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serial_numbers",
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Serial Number")
        verbose_name_plural = "Serial Numbers"
        unique_together = ["company", "product", "serial_number"]
        ordering = ["serial_number"]
        indexes = [
            models.Index(fields=["company", "status"], name="idx_sn_company_status"),
            models.Index(fields=["product", "status"], name="idx_sn_product_status"),
        ]

    def __str__(self):
        return f"{self.product.sku} – SN {self.serial_number}"


# =========================================================================
# Stock Item (per-product per-warehouse quantity snapshot)
# =========================================================================


class StockItem(TimeStampedModel):
    """
    Quantity snapshot for a product at a specific warehouse (optionally per bin).

    All quantities are maintained by the stock-movement service; never
    update these columns directly – always record a StockMovement first.
    """

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="stock_items",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.CASCADE,
        related_name="stock_items",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="stock_items",
    )
    bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_items",
    )
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_items",
    )

    # Quantities
    on_hand = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    allocated = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        help_text=_("Reserved for outbound orders"),
    )
    in_transit = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        help_text=_("In-transit from another warehouse"),
    )

    # Cost tracking (for weighted-average valuation)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        verbose_name = _("Stock Item")
        verbose_name_plural = "Stock Items"
        unique_together = ["company", "product", "warehouse", "bin", "lot"]
        ordering = ["product__sku", "warehouse__code"]
        indexes = [
            models.Index(fields=["company", "warehouse"], name="idx_si_company_wh"),
            models.Index(fields=["company", "product"], name="idx_si_company_prod"),
        ]

    def __str__(self):
        return f"{self.product.sku} @ {self.warehouse.code} = {self.on_hand}"

    @property
    def available(self):
        """Quantity free to promise (on-hand minus allocated)."""
        return self.on_hand - self.allocated


# =========================================================================
# Stock Movement Ledger (append-only)
# =========================================================================


class StockMovement(TimeStampedModel):
    """
    Immutable double-entry stock ledger.  Every inventory change creates
    exactly one StockMovement row. Quantities are always positive; direction
    is defined by movement_type.
    """

    class MovementType(models.TextChoices):
        # Inbound
        OPENING = "opening", "Opening Balance"
        PURCHASE_RECEIPT = "purchase_receipt", "Purchase Receipt"
        RETURN_IN = "return_in", "Customer Return Inbound"
        TRANSFER_IN = "transfer_in", "Transfer In"
        ADJUSTMENT_GAIN = "adjustment_gain", "Adjustment – Gain"
        PRODUCTION_IN = "production_in", "Production Output"

        # Outbound
        SALES_ISSUE = "sales_issue", "Sales Issue"
        RETURN_OUT = "return_out", "Supplier Return Outbound"
        TRANSFER_OUT = "transfer_out", "Transfer Out"
        ADJUSTMENT_LOSS = "adjustment_loss", "Adjustment – Loss"
        WRITE_OFF = "write_off", "Write-off / Scrap"

        # Neutral
        CYCLE_COUNT = "cycle_count", "Cycle Count Adjustment"

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )
    movement_date = models.DateTimeField(default=timezone.now)
    movement_type = models.CharField(max_length=30, choices=MovementType.choices)

    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=16, decimal_places=4, default=0)

    # Generic reference to the originating document
    reference_type = models.CharField(
        max_length=40,
        blank=True,
        help_text=_("e.g. goods_receipt, stock_transfer, stock_adjustment, cycle_count, invoice"),
    )
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reference_number = models.CharField(max_length=50, blank=True)

    description = models.CharField(max_length=500, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    class Meta:
        verbose_name = _("Stock Movement")
        verbose_name_plural = "Stock Movements"
        ordering = ["-movement_date", "-id"]
        indexes = [
            models.Index(fields=["company", "product", "movement_date"]),
            models.Index(fields=["company", "warehouse", "movement_date"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} – {self.product.sku} × {self.quantity}"

    @property
    def is_inbound(self):
        return self.movement_type in (
            self.MovementType.OPENING,
            self.MovementType.PURCHASE_RECEIPT,
            self.MovementType.RETURN_IN,
            self.MovementType.TRANSFER_IN,
            self.MovementType.ADJUSTMENT_GAIN,
            self.MovementType.PRODUCTION_IN,
        )


# =========================================================================
# Goods Receipt Note (GRN)
# =========================================================================


class GoodsReceiptNote(ERPBaseModel):
    """
    Records the physical receipt of goods against a Purchase Order.
    One PO can have multiple partial GRNs.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="goods_receipts",
    )
    grn_number = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateField()
    purchase_order = models.ForeignKey(
        "erp.PurchaseOrder",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    supplier = models.ForeignKey(
        "erp.Supplier",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Goods Receipt Note")
        verbose_name_plural = "Goods Receipt Notes"
        ordering = ["-receipt_date", "-id"]
        indexes = [
            models.Index(fields=["company", "status"], name="idx_grn_company_status"),
            models.Index(fields=["company", "receipt_date"], name="idx_grn_company_date"),
            models.Index(fields=["supplier", "status"], name="idx_grn_supplier_status"),
        ]

    def __str__(self):
        return f"{self.grn_number} ← PO {self.purchase_order.po_number}"


class GoodsReceiptLine(TimeStampedModel):
    """Line item for a single product received on a GRN."""

    grn = models.ForeignKey(
        GoodsReceiptNote,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    po_line = models.ForeignKey(
        "erp.PurchaseOrderLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_lines",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.PROTECT,
        related_name="grn_lines",
    )
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    quantity_accepted = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        help_text=_("Accepted after QC inspection"),
    )
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_lines",
    )
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_lines",
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Goods Receipt Line")
        verbose_name_plural = "Goods Receipt Lines"
        ordering = ["id"]

    def __str__(self):
        return f"{self.grn.grn_number} – {self.product.sku} × {self.quantity_received}"


# =========================================================================
# Stock Transfer
# =========================================================================


class StockTransfer(ERPBaseModel):
    """Transfer of stock between two warehouses (or zones/bins)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_TRANSIT = "in_transit", "In Transit"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="stock_transfers",
    )
    transfer_number = models.CharField(max_length=50, unique=True)
    transfer_date = models.DateField()

    from_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    shipped_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Stock Transfer")
        verbose_name_plural = "Stock Transfers"
        ordering = ["-transfer_date", "-id"]
        indexes = [
            models.Index(fields=["company", "status"], name="idx_xfer_company_status"),
            models.Index(fields=["company", "transfer_date"], name="idx_xfer_company_date"),
        ]

    def __str__(self):
        return f"{self.transfer_number}: {self.from_warehouse.code} → {self.to_warehouse.code}"


class StockTransferLine(TimeStampedModel):
    """Line on a stock transfer."""

    transfer = models.ForeignKey(
        StockTransfer,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.PROTECT,
        related_name="transfer_lines",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    from_bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfer_lines_from",
    )
    to_bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfer_lines_to",
    )
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfer_lines",
    )
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Stock Transfer Line")
        verbose_name_plural = "Stock Transfer Lines"
        ordering = ["id"]

    def __str__(self):
        return f"{self.transfer.transfer_number} – {self.product.sku} × {self.quantity}"


# =========================================================================
# Stock Adjustment
# =========================================================================


class StockAdjustment(ERPBaseModel):
    """Record a planned or unplanned inventory adjustment."""

    class AdjustmentType(models.TextChoices):
        GAIN = "gain", "Gain (found)"
        LOSS = "loss", "Loss (missing)"
        WRITE_OFF = "write_off", "Write-Off / Scrap"
        REVALUATION = "revaluation", "Cost Revaluation"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="stock_adjustments",
    )
    adjustment_number = models.CharField(max_length=50, unique=True)
    adjustment_date = models.DateField()
    adjustment_type = models.CharField(
        max_length=20,
        choices=AdjustmentType.choices,
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="stock_adjustments",
    )
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_adjustments",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Stock Adjustment")
        verbose_name_plural = "Stock Adjustments"
        ordering = ["-adjustment_date", "-id"]
        indexes = [
            models.Index(fields=["company", "status", "adjustment_type"], name="idx_adj_co_status_type"),
            models.Index(fields=["company", "adjustment_date"], name="idx_adj_company_date"),
        ]

    def __str__(self):
        return f"{self.adjustment_number} ({self.get_adjustment_type_display()})"


class StockAdjustmentLine(TimeStampedModel):
    """Single line of a stock adjustment."""

    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.PROTECT,
        related_name="adjustment_lines",
    )
    bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustment_lines",
    )
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustment_lines",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Stock Adjustment Line")
        verbose_name_plural = "Stock Adjustment Lines"
        ordering = ["id"]

    def __str__(self):
        return f"{self.adjustment.adjustment_number} – {self.product.sku} × {self.quantity}"


# =========================================================================
# Cycle Count
# =========================================================================


class CycleCount(ERPBaseModel):
    """Cycle count header – a planned or ad-hoc inventory count."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="cycle_counts",
    )
    count_number = models.CharField(max_length=50, unique=True)
    count_date = models.DateField()
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="cycle_counts",
    )
    zone = models.ForeignKey(
        WarehouseZone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cycle_counts",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    variance_posted = models.BooleanField(
        default=False,
        help_text=_("True once the variance has been posted as a stock adjustment"),
    )
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cycle_counts",
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Cycle Count")
        verbose_name_plural = "Cycle Counts"
        ordering = ["-count_date", "-id"]
        indexes = [
            models.Index(fields=["company", "status"], name="idx_cc_company_status"),
            models.Index(fields=["company", "count_date"], name="idx_cc_company_date"),
        ]

    def __str__(self):
        return f"{self.count_number} – {self.warehouse.code}"

    def finalize(self, user):
        """
        Finalize a completed cycle count: create a StockAdjustment for all variance
        lines and trigger the accounting journal entry.

        Only runs once (variance_posted guard). Sets status='completed'.
        """
        from django.db import transaction
        from tenants.routers import get_current_db_alias

        if self.variance_posted:
            return None
        if self.status == self.Status.CANCELLED:
            raise ValueError("Cannot finalize a cancelled cycle count.")

        db = get_current_db_alias()
        lines_with_variance = [
            line
            for line in self.lines.select_related("product", "bin", "lot").using(db)
            if line.counted_quantity is not None and line.variance != 0
        ]
        if not lines_with_variance:
            with transaction.atomic(using=db):
                self.status = self.Status.COMPLETED
                self.variance_posted = True
                self.save(using=db, update_fields=["status", "variance_posted", "updated_at"])
            return None

        with transaction.atomic(using=db):
            # Create parent StockAdjustment
            from erp.services.sequence import SequenceService

            adj_number = SequenceService.get_next_number(self.company, "stock_adjustment")
            adj = StockAdjustment.objects.using(db).create(
                company=self.company,
                adjustment_number=adj_number,
                adjustment_date=self.count_date,
                warehouse=self.warehouse,
                adjustment_type=StockAdjustment.AdjustmentType.GAIN,
                reason=f"Cycle Count {self.count_number}",
                status=StockAdjustment.Status.APPROVED,
                approved_by=user,
                created_by=user,
            )
            for line in lines_with_variance:
                variance = line.variance  # + = gain, - = loss
                StockAdjustmentLine.objects.using(db).create(
                    adjustment=adj,
                    product=line.product,
                    bin=line.bin,
                    lot=line.lot,
                    quantity=abs(variance),
                    unit_cost=line.product.cost_price or 0,
                    notes="Cycle count variance",
                )
                # Update StockItem directly
                from erp.services.inventory import record_stock_movement, StockMovement

                movement_type = (
                    StockMovement.MovementType.ADJUSTMENT_IN
                    if variance > 0
                    else StockMovement.MovementType.ADJUSTMENT_OUT
                )
                record_stock_movement(
                    company=self.company,
                    product=line.product,
                    warehouse=self.warehouse,
                    movement_type=movement_type,
                    quantity=abs(variance),
                    unit_cost=line.product.cost_price or 0,
                    bin=line.bin,
                    lot=line.lot,
                    reference_type="cycle_count",
                    reference_id=self.pk,
                    reference_number=self.count_number,
                    description=f"Cycle count {self.count_number} variance",
                    user=user,
                    db_alias=db,
                )

            self.status = self.Status.COMPLETED
            self.variance_posted = True
            self.save(using=db, update_fields=["status", "variance_posted", "updated_at"])

        # Create accounting JE outside the transaction
        try:
            from erp.services.inventory_accounting import create_adjustment_journal_entry

            create_adjustment_journal_entry(adj, user)
        except Exception:
            import logging

            logging.getLogger("erp.inventory").exception(
                "CycleCount finalize: JE creation failed for count %s", self.count_number
            )

        return adj


class CycleCountLine(TimeStampedModel):
    """One product line on a cycle count."""

    cycle_count = models.ForeignKey(
        CycleCount,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.PROTECT,
        related_name="cycle_count_lines",
    )
    bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cycle_count_lines",
    )
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cycle_count_lines",
    )
    system_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        help_text=_("Quantity in the system at the time of count"),
    )
    counted_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=_("Actual physical count"),
    )

    class Meta:
        verbose_name = _("Cycle Count Line")
        verbose_name_plural = "Cycle Count Lines"
        ordering = ["id"]

    def __str__(self):
        return f"{self.cycle_count.count_number} – {self.product.sku}"

    @property
    def variance(self):
        """Variance = counted - system (+ is gain, – is loss)."""
        if self.counted_quantity is not None:
            return self.counted_quantity - self.system_quantity
        return Decimal("0")


# =========================================================================
# Pick List / Shipment Note (Outbound Flow)
# =========================================================================


class PickList(ERPBaseModel):
    """Pick list generated for one or more sales orders / invoices."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "Picking In Progress"
        PICKED = "picked", "Fully Picked"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="pick_lists",
    )
    pick_number = models.CharField(max_length=50, unique=True)
    pick_date = models.DateField()
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="pick_lists",
    )
    # Optional link to invoice
    invoice = models.ForeignKey(
        "erp.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pick_lists",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_picks",
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Pick List")
        verbose_name_plural = "Pick Lists"
        ordering = ["-pick_date", "-id"]
        indexes = [
            models.Index(fields=["company", "status"], name="idx_pick_company_status"),
            models.Index(fields=["assigned_to", "status"], name="idx_pick_assignee_status"),
        ]

    def __str__(self):
        return self.pick_number


class PickListLine(TimeStampedModel):
    """Line on a pick list."""

    pick_list = models.ForeignKey(
        PickList,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.PROTECT,
        related_name="pick_lines",
    )
    from_bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pick_lines",
    )
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pick_lines",
    )
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=4)
    quantity_picked = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Pick List Line")
        verbose_name_plural = "Pick List Lines"
        ordering = ["id"]

    def __str__(self):
        return f"{self.pick_list.pick_number} – {self.product.sku} × {self.quantity_requested}"


class ShipmentNote(ERPBaseModel):
    """Shipping / dispatch note after picking."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="shipments",
    )
    shipment_number = models.CharField(max_length=50, unique=True)
    shipment_date = models.DateField()
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="shipments",
    )
    pick_list = models.ForeignKey(
        PickList,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
    )
    customer = models.ForeignKey(
        "erp.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
    )
    # Carrier info
    carrier_name = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Shipment Note")
        verbose_name_plural = "Shipment Notes"
        ordering = ["-shipment_date", "-id"]
        indexes = [
            models.Index(fields=["company", "status"], name="idx_ship_company_status"),
            models.Index(fields=["company", "shipment_date"], name="idx_ship_company_date"),
            models.Index(fields=["customer", "status"], name="idx_ship_customer_status"),
        ]

    def __str__(self):
        return self.shipment_number


class ShipmentLine(TimeStampedModel):
    """Line on a shipment."""

    shipment = models.ForeignKey(
        ShipmentNote,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.PROTECT,
        related_name="shipment_lines",
    )
    lot = models.ForeignKey(
        LotBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipment_lines",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Shipment Line")
        verbose_name_plural = "Shipment Lines"
        ordering = ["id"]

    def __str__(self):
        return f"{self.shipment.shipment_number} – {self.product.sku} × {self.quantity}"


# =========================================================================
# Reorder Rules
# =========================================================================


class ReorderRule(TimeStampedModel):
    """
    Per-product per-warehouse reorder parameters.
    Used by the replenishment service to generate purchase suggestions.
    """

    company = models.ForeignKey(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="reorder_rules",
    )
    product = models.ForeignKey(
        "erp.Product",
        on_delete=models.CASCADE,
        related_name="reorder_rules",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="reorder_rules",
    )
    reorder_point = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Trigger reorder when available qty falls below this"),
    )
    safety_stock = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Minimum buffer stock to always keep on hand"),
    )
    min_order_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1,
        help_text=_("Minimum quantity per purchase order line"),
    )
    max_order_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Maximum quantity per order (0 = unlimited)"),
    )
    lead_time_days = models.PositiveIntegerField(
        default=0,
        help_text=_("Expected supplier lead time"),
    )
    preferred_supplier = models.ForeignKey(
        "erp.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reorder_rules",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Reorder Rule")
        verbose_name_plural = "Reorder Rules"
        unique_together = ["company", "product", "warehouse"]
        ordering = ["product__sku"]

    def __str__(self):
        return f"{self.product.sku} @ {self.warehouse.code} – ROP {self.reorder_point}"


# =========================================================================
# Inventory Valuation Configuration
# =========================================================================


class InventoryValuationConfig(TimeStampedModel):
    """Company-wide inventory valuation method and GL account mapping."""

    class ValuationMethod(models.TextChoices):
        FIFO = "fifo", "FIFO (First In, First Out)"
        WEIGHTED_AVG = "weighted_avg", "Weighted Average Cost"

    company = models.OneToOneField(
        "erp.Company",
        on_delete=models.CASCADE,
        related_name="inventory_valuation_config",
    )
    valuation_method = models.CharField(
        max_length=20,
        choices=ValuationMethod.choices,
        default=ValuationMethod.WEIGHTED_AVG,
    )

    # GL account mappings
    inventory_account = models.ForeignKey(
        "erp.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("DR on receipt, CR on issue (default 1500)"),
    )
    cogs_account = models.ForeignKey(
        "erp.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("DR on sales issue (default 5100)"),
    )
    grni_account = models.ForeignKey(
        "erp.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Goods Received Not Invoiced (default 1400)"),
    )
    adjustment_account = models.ForeignKey(
        "erp.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Inventory adjustment gains/losses (default 6200)"),
    )
    write_off_account = models.ForeignKey(
        "erp.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=_("Write-off / scrap expense (default 6300)"),
    )

    class Meta:
        verbose_name = _("Inventory Valuation Config")
        verbose_name_plural = "Inventory Valuation Configs"

    def __str__(self):
        return f"{self.company.name} – {self.get_valuation_method_display()}"
