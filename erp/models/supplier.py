"""
Supplier/Vendor management models for the ERP system.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from .base import ERPBaseModel, TimeStampedModel
import uuid


def supplier_document_path(instance, filename):
    """Generate upload path for supplier documents."""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f'erp/suppliers/{instance.supplier.id}/{new_filename}'


class Supplier(ERPBaseModel):
    """Supplier/Vendor records."""
    class SupplierType(models.TextChoices):
        AIRLINE = 'airline', 'Airline'
        HOTEL = 'hotel', 'Hotel'
        TRANSPORT = 'transport', 'Transport Company'
        VISA = 'visa', 'Visa Agency'
        INSURANCE = 'insurance', 'Insurance Provider'
        TOUR_OPERATOR = 'tour_operator', 'Tour Operator'
        DMC = 'dmc', 'DMC Partner'
        OTHER = 'other', 'Other'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='suppliers'
    )
    
    supplier_id = models.CharField(max_length=20, unique=True)
    supplier_type = models.CharField(max_length=30, choices=SupplierType.choices)
    
    # Name
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    trading_name = models.CharField(max_length=255, blank=True)
    
    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Primary Contact Person
    contact_person = models.CharField(max_length=255, blank=True)
    contact_position = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Tax & Registration
    tax_number = models.CharField(max_length=50, blank=True)
    registration_number = models.CharField(max_length=50, blank=True)
    
    # Banking
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_name = models.CharField(max_length=255, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_iban = models.CharField(max_length=50, blank=True)
    bank_swift = models.CharField(max_length=20, blank=True)
    
    # Financial
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suppliers'
    )
    payment_terms = models.PositiveIntegerField(default=30, help_text='Payment terms in days')
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Amount owed to supplier')
    
    # Rating
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text='Rating 1-5'
    )
    
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.supplier_id})"


class SupplierContact(TimeStampedModel):
    """Additional contacts for a supplier."""
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='contacts'
    )
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Supplier Contact'
        verbose_name_plural = 'Supplier Contacts'
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return f"{self.name} - {self.supplier.name}"


class SupplierDocument(TimeStampedModel):
    """Documents related to suppliers (contracts, licenses, etc.)."""
    class DocumentType(models.TextChoices):
        CONTRACT = 'contract', 'Contract'
        LICENSE = 'license', 'Trade License'
        CERTIFICATE = 'certificate', 'Certificate'
        AGREEMENT = 'agreement', 'Agreement'
        INSURANCE = 'insurance', 'Insurance Document'
        OTHER = 'other', 'Other'

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to=supplier_document_path)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Supplier Document'
        verbose_name_plural = 'Supplier Documents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.supplier.name}"


class PurchaseOrder(ERPBaseModel):
    """Purchase orders to suppliers."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        SENT = 'sent', 'Sent to Supplier'
        PARTIAL = 'partial', 'Partially Received'
        RECEIVED = 'received', 'Received'
        CANCELLED = 'cancelled', 'Cancelled'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='purchase_orders'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchase_orders'
    )
    
    po_number = models.CharField(max_length=50, unique=True)
    po_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True, help_text='Expected delivery/completion date')
    
    # Reference
    reference = models.CharField(max_length=100, blank=True)
    
    # Amounts
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='purchase_orders'
    )
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    
    # Approval
    approved_by = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_purchase_orders'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
        ordering = ['-po_date', '-id']

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name}"

    def calculate_totals(self):
        """Calculate PO totals from line items."""
        lines = self.lines.all()
        self.subtotal = sum(line.line_total for line in lines)
        self.tax_amount = sum(line.tax_amount for line in lines)
        self.total_amount = self.subtotal + self.tax_amount


class PurchaseOrderLine(TimeStampedModel):
    """Line items for purchase orders."""
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    # Optional product link
    product = models.ForeignKey(
        'erp.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_order_lines'
    )
    
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Tax
    tax_rate = models.ForeignKey(
        'erp.TaxRate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='po_lines'
    )
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Totals
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Receiving
    received_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Purchase Order Line'
        verbose_name_plural = 'Purchase Order Lines'
        ordering = ['id']

    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.description[:50]}"

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        if self.tax_rate:
            self.tax_amount = self.line_total * (self.tax_rate.rate / 100)
        else:
            self.tax_amount = 0
        super().save(*args, **kwargs)


class SupplierInvoice(ERPBaseModel):
    """Invoices from suppliers (bills)."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        PARTIAL = 'partial', 'Partially Paid'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='supplier_invoices'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    
    invoice_number = models.CharField(max_length=50)
    supplier_invoice_number = models.CharField(max_length=50, blank=True, help_text="Supplier's own invoice number")
    invoice_date = models.DateField()
    due_date = models.DateField()
    
    # Link to PO (optional)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_invoices'
    )
    
    # Amounts
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='supplier_invoices'
    )
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Supplier Invoice'
        verbose_name_plural = 'Supplier Invoices'
        unique_together = ['company', 'invoice_number']
        ordering = ['-invoice_date', '-id']

    def __str__(self):
        return f"{self.invoice_number} - {self.supplier.name}"

    def save(self, *args, **kwargs):
        self.balance_due = self.total_amount - self.paid_amount
        super().save(*args, **kwargs)


class SupplierInvoiceLine(TimeStampedModel):
    """Line items for supplier invoices."""
    invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    tax_rate = models.ForeignKey(
        'erp.TaxRate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_invoice_lines'
    )
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Accounting
    account = models.ForeignKey(
        'erp.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_invoice_lines'
    )

    class Meta:
        verbose_name = 'Supplier Invoice Line'
        verbose_name_plural = 'Supplier Invoice Lines'
        ordering = ['id']

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        if self.tax_rate:
            self.tax_amount = self.line_total * (self.tax_rate.rate / 100)
        else:
            self.tax_amount = 0
        super().save(*args, **kwargs)


class SupplierPayment(ERPBaseModel):
    """Payments made to suppliers."""
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='supplier_payments'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    
    payment_number = models.CharField(max_length=50, unique=True)
    payment_date = models.DateField()
    
    # Method & Reference
    payment_method = models.ForeignKey(
        'erp.PaymentMethod',
        on_delete=models.PROTECT,
        related_name='supplier_payments'
    )
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Amount
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='supplier_payments'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Allocation
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Supplier Payment'
        verbose_name_plural = 'Supplier Payments'
        ordering = ['-payment_date', '-id']

    def __str__(self):
        return f"{self.payment_number} - {self.supplier.name}"


class SupplierPaymentAllocation(TimeStampedModel):
    """Allocation of payments to supplier invoices."""
    payment = models.ForeignKey(
        SupplierPayment,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.CASCADE,
        related_name='payment_allocations'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        verbose_name = 'Supplier Payment Allocation'
        verbose_name_plural = 'Supplier Payment Allocations'
        unique_together = ['payment', 'invoice']

    def __str__(self):
        return f"{self.payment.payment_number} → {self.invoice.invoice_number}"
