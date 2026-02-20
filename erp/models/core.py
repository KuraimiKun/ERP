"""
Core/Company models for the ERP system.
"""

from django.db import models
from django.conf import settings
from .base import ERPBaseModel, TimeStampedModel


class Currency(TimeStampedModel):
    """Currency definitions for multi-currency support."""
    code = models.CharField(max_length=3, unique=True, help_text='ISO 4217 code (e.g., SAR, USD)')
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    symbol = models.CharField(max_length=10)
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1,
        help_text='Exchange rate relative to base currency'
    )
    is_base = models.BooleanField(default=False, help_text='Is this the base currency?')
    is_active = models.BooleanField(default=True)
    decimal_places = models.PositiveSmallIntegerField(default=2)

    class Meta:
        verbose_name = 'Currency'
        verbose_name_plural = 'Currencies'
        ordering = ['-is_base', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        # Ensure only one base currency
        if self.is_base:
            Currency.objects.filter(is_base=True).exclude(pk=self.pk).update(is_base=False)
        super().save(*args, **kwargs)


class Company(ERPBaseModel):
    """Company/Organization settings."""
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    
    # Registration
    tax_number = models.CharField(max_length=50, blank=True, help_text='VAT/Tax registration number')
    commercial_register = models.CharField(max_length=50, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    
    # Contact
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    fax = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Address
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Branding
    logo = models.ImageField(upload_to='company/logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='company/favicons/', null=True, blank=True)
    
    # Settings
    base_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='companies'
    )
    fiscal_year_start = models.PositiveSmallIntegerField(default=1, help_text='Month (1-12)')
    
    # Bank Details
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    iban = models.CharField(max_length=50, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class Department(ERPBaseModel):
    """Company departments."""
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='departments'
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
    manager = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments'
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['name']

    def __str__(self):
        return self.name


class Branch(ERPBaseModel):
    """Company branches/locations."""
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='branches'
    )
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20, blank=True)
    
    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Address
    address = models.TextField()
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    
    # Settings
    is_headquarters = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    manager = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_branches'
    )

    class Meta:
        verbose_name = 'Branch'
        verbose_name_plural = 'Branches'
        ordering = ['-is_headquarters', 'name']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class FiscalYear(ERPBaseModel):
    """Fiscal year definitions."""
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='fiscal_years'
    )
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Fiscal Year'
        verbose_name_plural = 'Fiscal Years'
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one current fiscal year per company
        if self.is_current:
            FiscalYear.objects.filter(
                company=self.company,
                is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class Sequence(TimeStampedModel):
    """Sequence generator for document numbering."""
    class SequenceType(models.TextChoices):
        INVOICE = 'invoice', 'Invoice'
        PAYMENT = 'payment', 'Payment'
        EXPENSE = 'expense', 'Expense'
        QUOTATION = 'quotation', 'Quotation'
        PURCHASE_ORDER = 'purchase_order', 'Purchase Order'
        EMPLOYEE = 'employee', 'Employee'
        CUSTOMER = 'customer', 'Customer'
        SUPPLIER = 'supplier', 'Supplier'
        SUPPLIER_INVOICE = 'supplier_invoice', 'Supplier Invoice'
        SUPPLIER_PAYMENT = 'supplier_payment', 'Supplier Payment'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='sequences'
    )
    sequence_type = models.CharField(max_length=30, choices=SequenceType.choices)
    prefix = models.CharField(max_length=20, blank=True)
    suffix = models.CharField(max_length=20, blank=True)
    next_number = models.PositiveIntegerField(default=1)
    padding = models.PositiveSmallIntegerField(default=5, help_text='Number of digits to pad')
    reset_period = models.CharField(
        max_length=20,
        choices=[
            ('never', 'Never'),
            ('yearly', 'Yearly'),
            ('monthly', 'Monthly'),
        ],
        default='never'
    )
    last_reset = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Sequence'
        verbose_name_plural = 'Sequences'
        unique_together = ['company', 'sequence_type']

    def __str__(self):
        return f"{self.company.name} - {self.get_sequence_type_display()}"

    def get_next(self):
        """Get the next sequence number."""
        from django.utils import timezone
        
        # Check if reset is needed
        today = timezone.now().date()
        should_reset = False
        
        if self.reset_period == 'yearly' and self.last_reset:
            if self.last_reset.year != today.year:
                should_reset = True
        elif self.reset_period == 'monthly' and self.last_reset:
            if self.last_reset.month != today.month or self.last_reset.year != today.year:
                should_reset = True
        
        if should_reset:
            self.next_number = 1
            self.last_reset = today
        
        # Generate number
        number = str(self.next_number).zfill(self.padding)
        result = f"{self.prefix}{number}{self.suffix}"
        
        # Increment
        self.next_number += 1
        self.save()
        
        return result
