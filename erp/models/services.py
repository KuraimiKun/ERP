"""
Service/Product management models for the ERP system.
Tracks services offered, products, pricing, and packages.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from .base import ERPBaseModel, TimeStampedModel
import uuid


def service_image_path(instance, filename):
    """Generate upload path for service images."""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f'erp/services/{new_filename}'


def product_image_path(instance, filename):
    """Generate upload path for product images."""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f'erp/products/{new_filename}'


class ServiceCategory(TimeStampedModel):
    """Categories for services."""
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='service_categories'
    )
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Service Category'
        verbose_name_plural = 'Service Categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class ServicePricing(ERPBaseModel):
    """Pricing definitions for services."""
    class PricingType(models.TextChoices):
        FIXED = 'fixed', 'Fixed Price'
        TIERED = 'tiered', 'Tiered Pricing'
        VARIABLE = 'variable', 'Variable'
        QUOTE = 'quote', 'Quote Required'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='service_pricings'
    )
    
    # Link to website service (optional, for reference)
    website_service_name = models.CharField(max_length=255, blank=True, help_text='Name of the service on website')
    
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services'
    )
    
    # Pricing
    pricing_type = models.CharField(max_length=20, choices=PricingType.choices, default=PricingType.FIXED)
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='service_pricings'
    )
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Our cost')
    
    # Tax
    tax_rate = models.ForeignKey(
        'erp.TaxRate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_pricings'
    )
    is_tax_inclusive = models.BooleanField(default=False)
    
    # Accounting
    income_account = models.ForeignKey(
        'erp.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='income_services'
    )
    expense_account = models.ForeignKey(
        'erp.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense_services'
    )
    
    # Commission
    agent_commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Commission percentage for agents'
    )
    
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Service Pricing'
        verbose_name_plural = 'Service Pricings'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def profit_margin(self):
        """Calculate profit margin percentage."""
        if self.base_price > 0:
            return ((self.base_price - self.cost_price) / self.base_price) * 100
        return 0


class PriceTier(TimeStampedModel):
    """Price tiers for tiered pricing services."""
    service_pricing = models.ForeignKey(
        ServicePricing,
        on_delete=models.CASCADE,
        related_name='price_tiers'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    min_quantity = models.PositiveIntegerField(default=1)
    max_quantity = models.PositiveIntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Price Tier'
        verbose_name_plural = 'Price Tiers'
        ordering = ['min_quantity']

    def __str__(self):
        return f"{self.service_pricing.name} - {self.name}"


class ServicePackage(ERPBaseModel):
    """Bundled service packages."""
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='service_packages'
    )
    
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=service_image_path, null=True, blank=True)
    
    # Pricing
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='service_packages'
    )
    regular_price = models.DecimalField(max_digits=12, decimal_places=2)
    package_price = models.DecimalField(max_digits=12, decimal_places=2, help_text='Discounted package price')
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Validity
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Service Package'
        verbose_name_plural = 'Service Packages'
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def discount_amount(self):
        return self.regular_price - self.package_price

    @property
    def discount_percent(self):
        if self.regular_price > 0:
            return ((self.regular_price - self.package_price) / self.regular_price) * 100
        return 0


class PackageItem(TimeStampedModel):
    """Items included in a service package."""
    package = models.ForeignKey(
        ServicePackage,
        on_delete=models.CASCADE,
        related_name='items'
    )
    service_pricing = models.ForeignKey(
        ServicePricing,
        on_delete=models.CASCADE,
        related_name='package_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    included_in_price = models.BooleanField(default=True, help_text='Is this included in package price or charged extra?')
    extra_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Package Item'
        verbose_name_plural = 'Package Items'
        unique_together = ['package', 'service_pricing']

    def __str__(self):
        return f"{self.package.name} - {self.service_pricing.name}"


class Quote(ERPBaseModel):
    """Sales quotes/proposals."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        VIEWED = 'viewed', 'Viewed'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        EXPIRED = 'expired', 'Expired'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='quotes'
    )
    customer = models.ForeignKey(
        'erp.Customer',
        on_delete=models.PROTECT,
        related_name='quotes'
    )
    
    # Quote details
    quote_number = models.CharField(max_length=50, unique=True)
    quote_date = models.DateField()
    valid_until = models.DateField()
    
    # Reference
    reference = models.CharField(max_length=100, blank=True)
    lead = models.ForeignKey(
        'erp.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotes'
    )
    
    # Amounts
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='quotes'
    )
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    
    # Conversion
    converted_to_invoice = models.ForeignKey(
        'erp.Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_quote'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Prepared by
    prepared_by = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prepared_quotes'
    )

    class Meta:
        verbose_name = 'Quote'
        verbose_name_plural = 'Quotes'
        ordering = ['-quote_date', '-id']

    def __str__(self):
        return f"{self.quote_number} - {self.customer.name}"

    def calculate_totals(self):
        """Calculate quote totals from line items."""
        lines = self.lines.all()
        self.subtotal = sum(line.line_total for line in lines)
        self.discount_amount = self.subtotal * (self.discount_percent / 100)
        self.tax_amount = sum(line.tax_amount for line in lines)
        self.total_amount = self.subtotal - self.discount_amount + self.tax_amount


class QuoteLine(TimeStampedModel):
    """Quote line items."""
    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    # Product (optional)
    product = models.ForeignKey(
        'erp.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quote_lines'
    )
    
    # Service (optional)
    service_pricing = models.ForeignKey(
        ServicePricing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quote_lines'
    )
    
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Tax
    tax_rate = models.ForeignKey(
        'erp.TaxRate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quote_lines'
    )
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Totals
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Quote Line'
        verbose_name_plural = 'Quote Lines'
        ordering = ['id']

    def __str__(self):
        return f"{self.quote.quote_number} - {self.description[:50]}"

    def save(self, *args, **kwargs):
        subtotal = self.quantity * self.unit_price
        discount = subtotal * (self.discount_percent / 100)
        self.line_total = subtotal - discount
        
        if self.tax_rate:
            self.tax_amount = self.line_total * (self.tax_rate.rate / 100)
        else:
            self.tax_amount = 0
        
        super().save(*args, **kwargs)


# =========================================================================
# Products (physical and digital goods – linked to suppliers & invoices)
# =========================================================================

class ProductCategory(TimeStampedModel):
    """Categories for products."""
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='product_categories'
    )
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Product Category'
        verbose_name_plural = 'Product Categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Product(ERPBaseModel):
    """
    Products / inventory items.

    A product can optionally link to one or more suppliers, appear on
    invoices, purchase orders, and quotes.
    """

    class ProductType(models.TextChoices):
        PHYSICAL = 'physical', 'Physical Product'
        DIGITAL = 'digital', 'Digital Product'
        CONSUMABLE = 'consumable', 'Consumable'
        RAW_MATERIAL = 'raw_material', 'Raw Material'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='products'
    )

    # Identification
    sku = models.CharField('SKU', max_length=50, unique=True)
    barcode = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=product_image_path, null=True, blank=True)

    # Classification
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.PHYSICAL,
    )
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

    # Pricing
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='products'
    )
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Minimum price to preserve margin'
    )

    # Tax
    tax_rate = models.ForeignKey(
        'erp.TaxRate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

    # Inventory
    track_inventory = models.BooleanField(default=True)
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Alert when stock falls below this level'
    )
    reorder_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_of_measure = models.CharField(max_length=20, default='unit', help_text='e.g. unit, kg, m, litre')

    # Supplier link (preferred / default supplier for reordering)
    supplier = models.ForeignKey(
        'erp.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplied_products',
        help_text='Preferred supplier'
    )
    supplier_sku = models.CharField(max_length=50, blank=True, help_text="Supplier's part number")

    # Accounting
    income_account = models.ForeignKey(
        'erp.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='income_products'
    )
    expense_account = models.ForeignKey(
        'erp.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense_products'
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['name']

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def profit_margin(self):
        if self.selling_price > 0:
            return ((self.selling_price - self.cost_price) / self.selling_price) * 100
        return 0

    @property
    def is_low_stock(self):
        return self.track_inventory and self.quantity_on_hand <= self.reorder_level


class ProductSupplier(TimeStampedModel):
    """
    Many-to-many through table: a product can have multiple suppliers,
    each with their own price and lead time.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='product_suppliers'
    )
    supplier = models.ForeignKey(
        'erp.Supplier',
        on_delete=models.CASCADE,
        related_name='supplier_products'
    )
    supplier_sku = models.CharField(max_length=50, blank=True)
    supplier_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='product_supplier_prices'
    )
    lead_time_days = models.PositiveIntegerField(default=0, help_text='Delivery lead time in days')
    min_order_qty = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    is_preferred = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Product Supplier'
        verbose_name_plural = 'Product Suppliers'
        unique_together = ['product', 'supplier']
        ordering = ['-is_preferred', 'supplier__name']

    def __str__(self):
        return f"{self.product.name} ← {self.supplier.name}"
