"""
Financial/Accounting models for the ERP system.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from .base import ERPBaseModel, TimeStampedModel
import uuid


def invoice_attachment_path(instance, filename):
    """Generate upload path for invoice attachments."""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f'erp/invoices/{instance.invoice.id}/{new_filename}'


def payment_attachment_path(instance, filename):
    """Generate upload path for payment attachments."""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f'erp/payments/{uuid.uuid4()}/{new_filename}'


class Account(ERPBaseModel):
    """Chart of Accounts."""
    class AccountType(models.TextChoices):
        ASSET = 'asset', 'Asset'
        LIABILITY = 'liability', 'Liability'
        EQUITY = 'equity', 'Equity'
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='accounts'
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text='System accounts cannot be deleted')
    
    # Balance tracking
    opening_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='الرصيد الافتتاحي للحساب'
    )
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Account'
        verbose_name_plural = 'Accounts'
        unique_together = ['company', 'code']
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def is_debit_normal(self):
        """Returns True if this account has a debit-normal balance."""
        return self.account_type in ('asset', 'expense')

    def update_balance(self, debit_amount, credit_amount):
        """Update current_balance by the given debit/credit amounts.
        Respects normal balance direction: debit-normal for assets/expenses,
        credit-normal for liabilities/equity/income."""
        if self.is_debit_normal:
            self.current_balance += debit_amount - credit_amount
        else:
            self.current_balance += credit_amount - debit_amount

    def recalculate_balance(self, db_alias=None):
        """Recompute current_balance from opening_balance + all posted journal lines."""
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        qs = self.journal_lines.filter(journal_entry__status='posted')
        if db_alias:
            qs = qs.using(db_alias)
        totals = qs.aggregate(
            total_debit=Coalesce(Sum('debit_amount'), Decimal('0')),
            total_credit=Coalesce(Sum('credit_amount'), Decimal('0')),
        )
        if self.is_debit_normal:
            self.current_balance = self.opening_balance + totals['total_debit'] - totals['total_credit']
        else:
            self.current_balance = self.opening_balance + totals['total_credit'] - totals['total_debit']
        return self.current_balance


class TaxRate(TimeStampedModel):
    """Tax rate definitions."""
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='tax_rates'
    )
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))]
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tax Rate'
        verbose_name_plural = 'Tax Rates'
        ordering = ['rate']

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class PaymentMethod(TimeStampedModel):
    """Payment methods."""
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    requires_reference = models.BooleanField(default=False)
    
    # Link to bank account
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_methods'
    )

    class Meta:
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['name']

    def __str__(self):
        return self.name


class Customer(ERPBaseModel):
    """Customer/Client records for accounting."""
    class CustomerType(models.TextChoices):
        INDIVIDUAL = 'individual', 'Individual'
        COMPANY = 'company', 'Company'
        GOVERNMENT = 'government', 'Government'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='customers'
    )
    
    # Link to system user (optional)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='erp_customer_profile'
    )
    
    customer_id = models.CharField(max_length=20, unique=True)
    customer_type = models.CharField(max_length=20, choices=CustomerType.choices, default=CustomerType.INDIVIDUAL)
    
    # Name
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    
    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Billing Address
    billing_address = models.TextField(blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20, blank=True)
    
    # Shipping Address
    shipping_address = models.TextField(blank=True)
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_country = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    
    # Tax
    tax_id = models.CharField(max_length=50, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_customers'
    )
    
    # Credit
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Settings
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers'
    )
    payment_terms = models.PositiveIntegerField(default=0, help_text='Payment terms in days')
    
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.customer_id})"

    def recalculate_balance(self):
        """Recompute current_balance as the sum of balance_due on all
        non-cancelled invoices. Credit notes reduce the balance."""
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        ZERO = Decimal('0')

        # Standard invoices and debit notes: positive balance
        standard = self.invoices.filter(
            invoice_type__in=['standard', 'debit', 'proforma']
        ).exclude(status='cancelled').aggregate(
            total=Coalesce(Sum('balance_due'), ZERO)
        )['total']

        # Credit notes: negative (reduce what customer owes)
        credit = self.invoices.filter(
            invoice_type='credit'
        ).exclude(status='cancelled').aggregate(
            total=Coalesce(Sum('total_amount'), ZERO)
        )['total']

        self.current_balance = standard - credit
        self.save(update_fields=['current_balance'])


class Invoice(ERPBaseModel):
    """Sales invoices."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        PARTIAL = 'partial', 'Partially Paid'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        CANCELLED = 'cancelled', 'Cancelled'

    class InvoiceType(models.TextChoices):
        STANDARD = 'standard', 'Standard Invoice'
        CREDIT = 'credit', 'Credit Note'
        DEBIT = 'debit', 'Debit Note'
        PROFORMA = 'proforma', 'Proforma Invoice'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    
    # Invoice Details
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_type = models.CharField(max_length=20, choices=InvoiceType.choices, default=InvoiceType.STANDARD)
    invoice_date = models.DateField()
    due_date = models.DateField()
    
    # Reference
    reference = models.CharField(max_length=100, blank=True, help_text='PO number or reference')
    
    # Amounts
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    
    # Notes
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True, help_text='Payment terms and conditions')
    internal_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-invoice_date', '-id']

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"

    def calculate_totals(self):
        """Calculate invoice totals from line items."""
        lines = self.lines.all()
        self.subtotal = sum(line.line_total for line in lines)
        self.tax_amount = sum(line.tax_amount for line in lines)
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
        self.balance_due = self.total_amount - self.paid_amount
        
        # Update status
        if self.paid_amount >= self.total_amount:
            self.status = self.Status.PAID
        elif self.paid_amount > 0:
            self.status = self.Status.PARTIAL

    def save(self, *args, **kwargs):
        self.balance_due = self.total_amount - self.paid_amount
        super().save(*args, **kwargs)
        # Keep customer balance in sync
        try:
            self.customer.recalculate_balance()
        except Exception:
            pass  # Never block invoice save due to balance update error


class InvoiceLine(TimeStampedModel):
    """Invoice line items."""
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    # Optional product / service link
    product = models.ForeignKey(
        'erp.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines'
    )
    service_pricing = models.ForeignKey(
        'erp.ServicePricing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines'
    )
    
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Tax
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines'
    )
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Totals
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Accounting
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_lines'
    )

    class Meta:
        verbose_name = 'Invoice Line'
        verbose_name_plural = 'Invoice Lines'
        ordering = ['id']

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description[:50]}"

    def save(self, *args, **kwargs):
        # Ensure Decimal types
        self.quantity = Decimal(str(self.quantity))
        self.unit_price = Decimal(str(self.unit_price))
        self.discount_percent = Decimal(str(self.discount_percent))

        # Calculate line total
        subtotal = self.quantity * self.unit_price
        discount = subtotal * (self.discount_percent / Decimal('100'))
        self.line_total = subtotal - discount
        
        # Calculate tax
        if self.tax_rate:
            self.tax_amount = self.line_total * (Decimal(str(self.tax_rate.rate)) / Decimal('100'))
        else:
            self.tax_amount = Decimal('0')
        
        super().save(*args, **kwargs)


class Payment(ERPBaseModel):
    """Payment records."""
    class PaymentType(models.TextChoices):
        RECEIVED = 'received', 'Payment Received'
        REFUND = 'refund', 'Refund'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='payments'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    
    payment_number = models.CharField(max_length=50, unique=True)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices, default=PaymentType.RECEIVED)
    payment_date = models.DateField()
    
    # Method & Reference
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Amount
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Allocation
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    unallocated_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-payment_date', '-id']

    def __str__(self):
        return f"{self.payment_number} - {self.customer.name} ({self.amount})"

    def save(self, *args, **kwargs):
        self.unallocated_amount = self.amount - self.allocated_amount
        super().save(*args, **kwargs)


class PaymentAllocation(TimeStampedModel):
    """Allocation of payments to invoices."""
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payment_allocations'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'
        unique_together = ['payment', 'invoice']

    def __str__(self):
        return f"{self.payment.payment_number} → {self.invoice.invoice_number}"


class Expense(ERPBaseModel):
    """Business expense records."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PAID = 'paid', 'Paid'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    
    expense_number = models.CharField(max_length=50, unique=True)
    expense_date = models.DateField()
    
    # Category
    category = models.ForeignKey(
        'erp.ExpenseCategory',
        on_delete=models.PROTECT,
        related_name='expenses'
    )
    
    # Supplier (optional)
    supplier = models.ForeignKey(
        'erp.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    
    # Employee who submitted (optional)
    employee = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    
    description = models.TextField()
    
    # Amount
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='expenses'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Payment
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    payment_reference = models.CharField(max_length=100, blank=True)
    
    # Accounting
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    
    # Approval
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Attachments handled separately
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'
        ordering = ['-expense_date', '-id']

    def __str__(self):
        return f"{self.expense_number} - {self.description[:50]}"

    def save(self, *args, **kwargs):
        self.total_amount = self.amount + self.tax_amount
        super().save(*args, **kwargs)


class ExpenseCategory(TimeStampedModel):
    """Expense categories."""
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='expense_categories'
    )
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20, blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense_categories'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class ExpenseAttachment(TimeStampedModel):
    """Attachments for expenses (receipts, invoices, etc.)."""
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='erp/expenses/')
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'Expense Attachment'
        verbose_name_plural = 'Expense Attachments'

    def __str__(self):
        return f"Attachment for {self.expense.expense_number}"


class JournalEntry(ERPBaseModel):
    """القيود اليومية - Journal Entries for double-entry bookkeeping."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'مسودة'
        POSTED = 'posted', 'مرحّل'
        CANCELLED = 'cancelled', 'ملغي'

    class EntryType(models.TextChoices):
        MANUAL = 'manual', 'يدوي'
        INVOICE = 'invoice', 'فاتورة'
        PAYMENT = 'payment', 'دفعة'
        EXPENSE = 'expense', 'مصروف'
        PAYROLL = 'payroll', 'رواتب'
        ADJUSTMENT = 'adjustment', 'تسوية'
        OPENING = 'opening', 'رصيد افتتاحي'
        CLOSING = 'closing', 'إقفال'
        INVENTORY = 'inventory', 'مخزون'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='journal_entries'
    )
    
    entry_number = models.CharField(max_length=50)
    entry_date = models.DateField()
    entry_type = models.CharField(max_length=20, choices=EntryType.choices, default=EntryType.MANUAL)
    
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text='رقم مرجعي خارجي')
    
    fiscal_year = models.ForeignKey(
        'erp.FiscalYear',
        on_delete=models.PROTECT,
        related_name='journal_entries',
        null=True,
        blank=True
    )
    
    # Totals (auto-calculated)
    total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    
    # Posting info
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posted_journal_entries'
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_journal_entries'
    )

    class Meta:
        verbose_name = 'قيد يومية'
        verbose_name_plural = 'القيود اليومية'
        unique_together = ['company', 'entry_number']
        ordering = ['-entry_date', '-entry_number']

    def __str__(self):
        return f"{self.entry_number} - {self.entry_date}"

    @property
    def is_balanced(self):
        """Check if debit equals credit."""
        return self.total_debit == self.total_credit

    def calculate_totals(self):
        """Calculate total debit and credit from lines."""
        from django.db.models import Sum
        totals = self.lines.aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        self.total_debit = totals['total_debit'] or Decimal('0')
        self.total_credit = totals['total_credit'] or Decimal('0')

    def post(self, user):
        """Post the journal entry and update account balances."""
        from django.utils import timezone
        from django.db import transaction
        if self.status != self.Status.DRAFT:
            raise ValueError('يمكن ترحيل المسودات فقط')
        if not self.is_balanced:
            raise ValueError('القيد غير متوازن - المدين لا يساوي الدائن')
        
        with transaction.atomic():
            # Update account balances (respects normal balance direction)
            for line in self.lines.select_related('account').all():
                line.account.update_balance(line.debit_amount, line.credit_amount)
                line.account.save(update_fields=['current_balance'])
            
            self.status = self.Status.POSTED
            self.posted_by = user
            self.posted_at = timezone.now()
            self.save()


class JournalEntryLine(TimeStampedModel):
    """سطور القيد اليومي - Individual debit/credit entries."""
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='journal_lines'
    )
    
    description = models.CharField(max_length=255, blank=True)
    
    debit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0'))]
    )
    credit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    # Optional reference to related objects
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'سطر قيد'
        verbose_name_plural = 'سطور القيد'
        ordering = ['id']

    def __str__(self):
        if self.debit_amount > 0:
            return f"{self.account.code} - مدين: {self.debit_amount}"
        return f"{self.account.code} - دائن: {self.credit_amount}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update journal entry totals
        self.journal_entry.calculate_totals()
        self.journal_entry.save(update_fields=['total_debit', 'total_credit'])
