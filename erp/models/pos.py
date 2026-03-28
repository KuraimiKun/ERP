from django.utils.translation import gettext_lazy as _
"""
Point of Sale (POS) models for the ERP system.

Models:
  - POSTerminal   Cash register / terminal definition
  - POSSession    Shift tracking (open → close)
  - POSOrder      Sale transaction
  - POSOrderLine  Line item on a sale
  - POSPayment    Payment record (supports split payments)
"""

from decimal import Decimal

from django.db import models

from .base import ERPBaseModel, TimeStampedModel


class POSTerminal(ERPBaseModel):
    """Physical or virtual POS terminal / cash register."""

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='pos_terminals',
    )
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20)
    location = models.CharField(max_length=255, blank=True)
    warehouse = models.ForeignKey(
        'erp.Warehouse',
        on_delete=models.PROTECT,
        related_name='pos_terminals',
        help_text=_('Warehouse to deduct stock from on sales'),
    )
    allowed_employees = models.ManyToManyField(
        'erp.Employee',
        blank=True,
        related_name='pos_terminals',
        help_text=_('Leave empty to allow all POS-permitted employees'),
    )
    default_customer = models.ForeignKey(
        'erp.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_pos_terminals',
        help_text=_('Walk-in customer used when no customer is selected'),
    )
    receipt_header = models.TextField(blank=True, help_text=_('Text printed at top of receipt'))
    receipt_footer = models.TextField(blank=True, help_text=_('Text printed at bottom of receipt'))
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name=_('POS Terminal')
        verbose_name_plural = 'POS Terminals'
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class POSSession(ERPBaseModel):
    """Represents one shift/session on a POS terminal (open-to-close)."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='pos_sessions',
    )
    terminal = models.ForeignKey(
        POSTerminal,
        on_delete=models.PROTECT,
        related_name='sessions',
    )
    session_number = models.CharField(max_length=50)
    opened_by = models.ForeignKey(
        'erp.Employee',
        on_delete=models.PROTECT,
        related_name='pos_sessions_opened',
    )
    opening_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text=_('Cash in drawer when opening'),
    )
    opened_at = models.DateTimeField(auto_now_add=True)

    # Closing fields
    closed_by = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pos_sessions_closed',
    )
    closing_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text=_('Actual cash counted at close'),
    )
    expected_cash = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text=_('Calculated: opening + cash sales - cash refunds'),
    )
    cash_difference = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text=_('closing_balance - expected_cash (+ over, - short)'),
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closing_notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )

    # Summary (populated on close)
    total_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_refunds = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name=_('POS Session')
        verbose_name_plural = 'POS Sessions'
        ordering = ['-opened_at']

    def __str__(self):
        return f"{self.terminal.code} - {self.session_number}"

    def calculate_expected_cash(self):
        """Calculate expected cash based on opening balance + cash payments."""
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        cash_in = self.orders.filter(
            status='completed',
        ).aggregate(
            total=Coalesce(
                Sum(
                    'payments__amount',
                    filter=models.Q(payments__payment_method__code__iexact='cash'),
                ),
                Decimal('0'),
            ),
        )['total']

        cash_refunds = self.orders.filter(
            status='refunded',
        ).aggregate(
            total=Coalesce(
                Sum(
                    'payments__amount',
                    filter=models.Q(payments__payment_method__code__iexact='cash'),
                ),
                Decimal('0'),
            ),
        )['total']

        self.expected_cash = self.opening_balance + cash_in - cash_refunds


class POSOrder(ERPBaseModel):
    """Individual POS sale transaction."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        COMPLETED = 'completed', 'Completed'
        REFUNDED = 'refunded', 'Refunded'
        VOIDED = 'voided', 'Voided'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='pos_orders',
    )
    session = models.ForeignKey(
        POSSession,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    order_number = models.CharField(max_length=50)
    order_date = models.DateTimeField(auto_now_add=True)

    customer = models.ForeignKey(
        'erp.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pos_orders',
    )
    employee = models.ForeignKey(
        'erp.Employee',
        on_delete=models.PROTECT,
        related_name='pos_orders',
    )

    # Financials
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)

    # Optional link to generated Invoice
    invoice = models.ForeignKey(
        'erp.Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pos_order',
    )

    class Meta:
        verbose_name=_('POS Order')
        verbose_name_plural = 'POS Orders'
        ordering = ['-order_date']
        unique_together = [('company', 'order_number')]
        indexes = [
            models.Index(fields=['company', 'order_date']),
            models.Index(fields=['session', 'status']),
        ]

    def __str__(self):
        return self.order_number

    def calculate_totals(self):
        """Recalculate totals from lines."""
        lines = self.lines.all()
        self.subtotal = sum(line.line_total for line in lines)
        self.tax_amount = sum(line.tax_amount for line in lines)
        if self.discount_percent > 0:
            self.discount_amount = self.subtotal * (self.discount_percent / Decimal('100'))
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount


class POSOrderLine(TimeStampedModel):
    """Individual line item on a POS order."""

    order = models.ForeignKey(
        POSOrder,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    product = models.ForeignKey(
        'erp.Product',
        on_delete=models.PROTECT,
        related_name='pos_order_lines',
    )
    # Snapshot fields (preserved even if product is edited later)
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=50)

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    cost_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Tax
    tax_rate = models.ForeignKey(
        'erp.TaxRate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pos_order_lines',
    )
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Total
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name=_('POS Order Line')
        verbose_name_plural = 'POS Order Lines'
        ordering = ['id']

    def __str__(self):
        return f"{self.order.order_number} - {self.product_name}"

    def save(self, *args, **kwargs):
        subtotal = self.quantity * self.unit_price
        discount = subtotal * (self.discount_percent / Decimal('100'))
        self.line_total = subtotal - discount

        if self.tax_rate:
            self.tax_rate_percent = self.tax_rate.rate
            self.tax_amount = self.line_total * (self.tax_rate.rate / Decimal('100'))
        elif self.tax_rate_percent > 0:
            self.tax_amount = self.line_total * (self.tax_rate_percent / Decimal('100'))
        else:
            self.tax_amount = Decimal('0')

        super().save(*args, **kwargs)


class POSPayment(TimeStampedModel):
    """Payment for a POS order (supports split payments)."""

    order = models.ForeignKey(
        POSOrder,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    payment_method = models.ForeignKey(
        'erp.PaymentMethod',
        on_delete=models.PROTECT,
        related_name='pos_payments',
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    tendered = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text=_('Amount given by customer (for cash: may exceed amount)'),
    )
    change_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text=_('Change returned to customer (cash only)'),
    )
    reference = models.CharField(
        max_length=100, blank=True,
        help_text=_('Card auth code, cheque number, etc.'),
    )

    class Meta:
        verbose_name=_('POS Payment')
        verbose_name_plural = 'POS Payments'
        ordering = ['id']

    def __str__(self):
        return f"{self.order.order_number} - {self.payment_method.name}: {self.amount}"
