from django.utils.translation import gettext_lazy as _

"""
Supplier/Vendor management models for the ERP system.
"""

from decimal import Decimal

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from .base import ERPBaseModel, TimeStampedModel
import uuid


def supplier_document_path(instance, filename):
    """Generate upload path for supplier documents."""
    ext = filename.split(".")[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"erp/suppliers/{instance.supplier.id}/{new_filename}"


class Supplier(ERPBaseModel):
    """Supplier/Vendor records."""

    class SupplierType(models.TextChoices):
        AIRLINE = "airline", "Airline"
        HOTEL = "hotel", "Hotel"
        TRANSPORT = "transport", "Transport Company"
        VISA = "visa", "Visa Agency"
        INSURANCE = "insurance", "Insurance Provider"
        TOUR_OPERATOR = "tour_operator", "Tour Operator"
        DMC = "dmc", "DMC Partner"
        OTHER = "other", "Other"

    company = models.ForeignKey("erp.Company", on_delete=models.CASCADE, related_name="suppliers")

    supplier_id = models.CharField(max_length=20)
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
        "erp.Currency", on_delete=models.SET_NULL, null=True, blank=True, related_name="suppliers"
    )
    payment_terms = models.PositiveIntegerField(default=30, help_text=_("Payment terms in days"))
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, help_text=_("Amount owed to supplier")
    )

    # Rating
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)], help_text=_("Rating 1-5")
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Supplier")
        verbose_name_plural = "Suppliers"
        ordering = ["name"]
        unique_together = [("company", "supplier_id")]
        indexes = [
            models.Index(fields=["company", "supplier_type", "is_active"], name="idx_sup_company_type_active"),
            models.Index(fields=["company", "is_active"], name="idx_sup_company_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.supplier_id})"

    def recalculate_balance(self):
        """Recompute current_balance as the sum of balance_due on all
        non-cancelled supplier invoices for this supplier."""
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        total = self.invoices.exclude(status="cancelled").aggregate(total=Coalesce(Sum("balance_due"), Decimal("0")))[
            "total"
        ]
        self.current_balance = total
        self.save(update_fields=["current_balance"])


class SupplierContact(TimeStampedModel):
    """Additional contacts for a supplier."""

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Supplier Contact")
        verbose_name_plural = "Supplier Contacts"
        ordering = ["-is_primary", "name"]

    def __str__(self):
        return f"{self.name} - {self.supplier.name}"


class SupplierDocument(TimeStampedModel):
    """Documents related to suppliers (contracts, licenses, etc.)."""

    class DocumentType(models.TextChoices):
        CONTRACT = "contract", "Contract"
        LICENSE = "license", "Trade License"
        CERTIFICATE = "certificate", "Certificate"
        AGREEMENT = "agreement", "Agreement"
        INSURANCE = "insurance", "Insurance Document"
        OTHER = "other", "Other"

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to=supplier_document_path)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Supplier Document")
        verbose_name_plural = "Supplier Documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.supplier.name}"


class PurchaseOrder(ERPBaseModel):
    """Purchase orders to suppliers."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        SENT = "sent", "Sent to Supplier"
        PARTIAL = "partial", "Partially Received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("erp.Company", on_delete=models.CASCADE, related_name="purchase_orders")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")

    po_number = models.CharField(max_length=50)
    po_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True, help_text=_("Expected delivery/completion date"))

    # Reference
    reference = models.CharField(max_length=100, blank=True)

    # Amounts
    currency = models.ForeignKey("erp.Currency", on_delete=models.PROTECT, related_name="purchase_orders")
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # Approval
    approved_by = models.ForeignKey(
        "erp.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_purchase_orders"
    )
    approval_date = models.DateTimeField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Purchase Order")
        verbose_name_plural = "Purchase Orders"
        ordering = ["-po_date", "-id"]
        unique_together = [("company", "po_number")]
        indexes = [
            models.Index(fields=["company", "status", "po_date"], name="idx_po_company_status_date"),
            models.Index(fields=["supplier", "status"], name="idx_po_supplier_status"),
        ]

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name}"

    def calculate_totals(self):
        """Calculate PO totals from line items."""
        lines = self.lines.all()
        self.subtotal = sum(line.line_total for line in lines)
        self.tax_amount = sum(line.tax_amount for line in lines)
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
        self.balance_due = self.total_amount - self.paid_amount

    def recalculate_payment_status(self):
        """Propagate payment totals from linked SupplierInvoices to this PO.

        Converts each invoice's amounts to the PO currency using the invoice's
        exchange_rate_at_date snapshot so cross-currency invoices are comparable.
        """
        ZERO = Decimal("0")
        po_rate = self.currency.exchange_rate if self.currency_id else Decimal("1")

        total_paid = ZERO
        total_invoiced = ZERO
        for inv in self.supplier_invoices.exclude(status="cancelled").select_related("currency"):
            inv_rate = inv.exchange_rate_at_date or Decimal("1")
            # Ratio converts from invoice currency to PO currency
            ratio = inv_rate / po_rate if po_rate else Decimal("1")
            total_paid += (inv.paid_amount * ratio).quantize(Decimal("0.01"))
            total_invoiced += (inv.total_amount * ratio).quantize(Decimal("0.01"))

        self.paid_amount = total_paid
        self.balance_due = max(self.total_amount - self.paid_amount, ZERO)
        self.save(update_fields=["paid_amount", "balance_due"])

    def cancel(self, user=None):
        """
        Cancel this PO. Reverses any posted GRN journal entries and supplier invoices.
        Safe to call on draft or approved POs. Raises ValueError if already cancelled.
        """
        from django.db import transaction
        import logging

        _logger = logging.getLogger("erp.suppliers")

        if self.status == self.Status.CANCELLED:
            raise ValueError(f"PO {self.po_number} is already cancelled.")

        with transaction.atomic():
            # Cancel any linked SupplierInvoices that are not yet paid
            for si in self.supplier_invoices.exclude(status__in=["paid", "cancelled"]):
                si.status = "cancelled"
                si.save(update_fields=["status"])

            # Reverse and cancel posted journal entries referencing this PO
            from erp.models.finance import JournalEntry, Account

            posted_entries = JournalEntry.objects.filter(
                company=self.company,
                reference=self.po_number,
                status=JournalEntry.Status.POSTED,
            )
            account_ids = list(posted_entries.values_list("lines__account_id", flat=True).distinct())
            locked_accounts = {a.pk: a for a in Account.objects.select_for_update().filter(pk__in=account_ids)}
            for je in posted_entries:
                for line in je.lines.select_related("account").all():
                    acc = locked_accounts.get(line.account_id)
                    if acc:
                        acc.update_balance(line.credit_amount, line.debit_amount)
                        acc.save(update_fields=["current_balance"])
                je.status = JournalEntry.Status.CANCELLED
                je.save(update_fields=["status"])

            self.status = self.Status.CANCELLED
            self.save(update_fields=["status", "updated_at"])

        _logger.info("PurchaseOrder %s cancelled by user %s", self.po_number, user)


class PurchaseOrderLine(TimeStampedModel):
    """Line items for purchase orders."""

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")

    # Optional product link
    product = models.ForeignKey(
        "erp.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_order_lines"
    )

    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Tax
    tax_rate = models.ForeignKey(
        "erp.TaxRate", on_delete=models.SET_NULL, null=True, blank=True, related_name="po_lines"
    )
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Totals
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Receiving
    received_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = _("Purchase Order Line")
        verbose_name_plural = "Purchase Order Lines"
        ordering = ["id"]

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
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        PARTIAL = "partial", "Partially Paid"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("erp.Company", on_delete=models.CASCADE, related_name="supplier_invoices")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="invoices")

    invoice_number = models.CharField(max_length=50)
    supplier_invoice_number = models.CharField(max_length=50, blank=True, help_text="Supplier's own invoice number")
    invoice_date = models.DateField()
    due_date = models.DateField()

    # Link to PO (optional)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_invoices"
    )

    # Amounts
    currency = models.ForeignKey("erp.Currency", on_delete=models.PROTECT, related_name="supplier_invoices")
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    exchange_rate_at_date = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1,
        help_text="Exchange rate to base currency at invoice date",
    )

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Supplier Invoice")
        verbose_name_plural = "Supplier Invoices"
        unique_together = ["company", "invoice_number"]
        ordering = ["-invoice_date", "-id"]
        indexes = [
            models.Index(fields=["company", "status", "invoice_date"], name="idx_si_company_status_date"),
            models.Index(fields=["supplier", "status"], name="idx_si_supplier_status"),
            models.Index(fields=["company", "due_date", "status"], name="idx_si_company_due_status"),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.supplier.name}"

    def clean(self):
        """Validate supplier invoice data."""
        # due_date must not precede invoice_date
        if self.invoice_date and self.due_date and self.due_date < self.invoice_date:
            raise ValidationError({"due_date": _("تاريخ الاستحقاق لا يمكن أن يكون قبل تاريخ الفاتورة")})
        # PO supplier must match invoice supplier
        if self.purchase_order_id and self.supplier_id:
            if self.purchase_order.supplier_id != self.supplier_id:
                raise ValidationError({"purchase_order": _("أمر الشراء المحدد يخص مورداً مختلفاً عن مورد الفاتورة.")})

    def calculate_totals(self):
        """Calculate invoice totals from line items using a single DB aggregate."""
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        ZERO = Decimal("0")
        agg = self.lines.aggregate(
            subtotal=Coalesce(Sum("line_total"), ZERO),
            tax_amount=Coalesce(Sum("tax_amount"), ZERO),
        )
        self.subtotal = agg["subtotal"]
        self.tax_amount = agg["tax_amount"]
        self.total_amount = self.subtotal + self.tax_amount
        self.balance_due = self.total_amount - self.paid_amount

        # Update status based on payment
        if self.total_amount > 0 and self.paid_amount >= self.total_amount:
            self.status = self.Status.PAID
        elif self.paid_amount > 0:
            self.status = self.Status.PARTIAL

    def save(self, *args, **kwargs):
        import logging

        _logger = logging.getLogger("erp.suppliers")
        self.balance_due = self.total_amount - self.paid_amount
        if self.exchange_rate_at_date == 1 and self.currency_id:
            try:
                from erp.models.core import Currency

                cur = Currency.objects.get(pk=self.currency_id)
                if not cur.is_base:
                    self.exchange_rate_at_date = cur.exchange_rate
            except Exception:
                pass
        super().save(*args, **kwargs)

        supplier_pk = self.supplier_id
        po_pk = self.purchase_order_id

        def _recalc():
            try:
                Supplier.objects.get(pk=supplier_pk).recalculate_balance()
            except Exception:
                _logger.exception("Failed to recalculate balance for supplier %s", supplier_pk)
            if po_pk:
                try:
                    PurchaseOrder.objects.get(pk=po_pk).recalculate_payment_status()
                except Exception:
                    _logger.exception("Failed to recalculate payment status for PO %s", po_pk)

        transaction.on_commit(_recalc)


class SupplierInvoiceLine(TimeStampedModel):
    """Line items for supplier invoices."""

    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name="lines")

    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    tax_rate = models.ForeignKey(
        "erp.TaxRate", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_invoice_lines"
    )
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Accounting
    account = models.ForeignKey(
        "erp.Account", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_invoice_lines"
    )

    class Meta:
        verbose_name = _("Supplier Invoice Line")
        verbose_name_plural = "Supplier Invoice Lines"
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        if self.tax_rate:
            self.tax_amount = self.line_total * (self.tax_rate.rate / 100)
        else:
            self.tax_amount = 0
        super().save(*args, **kwargs)


class SupplierPayment(ERPBaseModel):
    """Payments made to suppliers."""

    company = models.ForeignKey("erp.Company", on_delete=models.CASCADE, related_name="supplier_payments")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="payments")

    payment_number = models.CharField(max_length=50)
    payment_date = models.DateField()

    # Method & Reference
    payment_method = models.ForeignKey("erp.PaymentMethod", on_delete=models.PROTECT, related_name="supplier_payments")
    reference_number = models.CharField(max_length=100, blank=True)

    # Amount
    currency = models.ForeignKey("erp.Currency", on_delete=models.PROTECT, related_name="supplier_payments")
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    exchange_rate_at_date = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1,
        help_text="Exchange rate to base currency at payment date",
    )

    # Allocation
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    unallocated_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Supplier Payment")
        verbose_name_plural = "Supplier Payments"
        ordering = ["-payment_date", "-id"]
        unique_together = [("company", "payment_number")]
        indexes = [
            models.Index(fields=["company", "payment_date"], name="idx_sp_company_date"),
            models.Index(fields=["supplier", "payment_date"], name="idx_sp_supplier_date"),
        ]

    def __str__(self):
        return f"{self.payment_number} - {self.supplier.name}"

    def save(self, *args, **kwargs):
        self.unallocated_amount = self.amount - self.allocated_amount
        if self.exchange_rate_at_date == 1 and self.currency_id:
            try:
                from erp.models.core import Currency

                cur = Currency.objects.get(pk=self.currency_id)
                if not cur.is_base:
                    self.exchange_rate_at_date = cur.exchange_rate
            except Exception:
                pass
        super().save(*args, **kwargs)


class SupplierPaymentAllocation(TimeStampedModel):
    """Allocation of payments to supplier invoices."""

    payment = models.ForeignKey(SupplierPayment, on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name="payment_allocations")
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        verbose_name = _("Supplier Payment Allocation")
        verbose_name_plural = "Supplier Payment Allocations"
        unique_together = ["payment", "invoice"]

    def __str__(self):
        return f"{self.payment.payment_number} → {self.invoice.invoice_number}"
