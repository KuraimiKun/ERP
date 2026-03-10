"""
Fixed Assets Management models for the ERP system.

Provides enterprise-grade fixed asset tracking with:
  - Asset Categories & Asset Register
  - Depreciation Schedules (straight-line, declining balance, units-of-production)
  - Asset Disposal with gain/loss calculation
  - Asset Transfers between departments/locations
  - Asset Revaluation
  - Maintenance Logs
  - Full journal entry integration for every financial event
"""

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models, transaction
from django.core.validators import MinValueValidator

from .base import ERPBaseModel, TimeStampedModel


# ────────────────────────────────────────────────────────────────
# Asset Category
# ────────────────────────────────────────────────────────────────

class AssetCategory(ERPBaseModel):
    """Classification of fixed assets with default accounting and depreciation settings."""

    class DepreciationMethod(models.TextChoices):
        STRAIGHT_LINE = 'straight_line', 'Straight Line'
        DECLINING_BALANCE = 'declining_balance', 'Declining Balance'
        DOUBLE_DECLINING = 'double_declining', 'Double Declining Balance'
        UNITS_OF_PRODUCTION = 'units_of_production', 'Units of Production'
        NO_DEPRECIATION = 'no_depreciation', 'No Depreciation'

    company = models.ForeignKey(
        'erp.Company', on_delete=models.CASCADE,
        related_name='asset_categories',
    )
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)

    # Default depreciation settings
    depreciation_method = models.CharField(
        max_length=30,
        choices=DepreciationMethod.choices,
        default=DepreciationMethod.STRAIGHT_LINE,
    )
    useful_life_months = models.PositiveIntegerField(
        default=60,
        help_text='Default useful life in months',
    )
    salvage_value_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Default salvage value as % of cost',
    )

    # Default GL accounts (linked to Chart of Accounts)
    asset_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_category_asset',
        help_text='Fixed Asset account (e.g. 1500 – Equipment)',
    )
    depreciation_expense_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_category_depr_expense',
        help_text='Depreciation Expense account',
    )
    accumulated_depreciation_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_category_accum_depr',
        help_text='Accumulated Depreciation account (contra-asset)',
    )
    disposal_gain_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_category_disposal_gain',
        help_text='Gain on Disposal (income)',
    )
    disposal_loss_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_category_disposal_loss',
        help_text='Loss on Disposal (expense)',
    )
    acquisition_source_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_category_acq_source',
        help_text='Cash / Bank / AP account credited on acquisition',
    )
    disposal_proceeds_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_category_disposal_proceeds',
        help_text='Cash / Receivable account debited on disposal sale',
    )
    revaluation_surplus_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_category_reval_surplus',
        help_text='Revaluation Surplus account (equity)',
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Asset Category'
        verbose_name_plural = 'Asset Categories'
        ordering = ['name']
        unique_together = [('company', 'code')]

    def __str__(self):
        prefix = f"[{self.code}] " if self.code else ''
        return f"{prefix}{self.name}"


# ────────────────────────────────────────────────────────────────
# Fixed Asset (The Register)
# ────────────────────────────────────────────────────────────────

class FixedAsset(ERPBaseModel):
    """
    The main Asset Register record.

    Every financial mutation (acquisition, depreciation, disposal,
    revaluation) creates a JournalEntry linked back here.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        FULLY_DEPRECIATED = 'fully_depreciated', 'Fully Depreciated'
        DISPOSED = 'disposed', 'Disposed'
        UNDER_MAINTENANCE = 'under_maintenance', 'Under Maintenance'

    company = models.ForeignKey(
        'erp.Company', on_delete=models.CASCADE,
        related_name='fixed_assets',
    )
    asset_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        AssetCategory, on_delete=models.PROTECT, related_name='assets',
    )

    # Acquisition info
    acquisition_date = models.DateField()
    acquisition_cost = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    currency = models.ForeignKey(
        'erp.Currency', on_delete=models.PROTECT,
        related_name='fixed_assets',
    )
    supplier = models.ForeignKey(
        'erp.Supplier', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='fixed_assets',
    )
    purchase_order = models.ForeignKey(
        'erp.PurchaseOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='fixed_assets',
    )
    invoice_reference = models.CharField(max_length=100, blank=True)

    # Location / assignment
    department = models.ForeignKey(
        'erp.Department', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='fixed_assets',
    )
    location = models.CharField(max_length=255, blank=True, help_text='Physical location')
    custodian = models.ForeignKey(
        'erp.Employee', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='custodian_assets',
    )
    serial_number = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=100, blank=True)

    # Depreciation settings (can override category defaults)
    depreciation_method = models.CharField(
        max_length=30,
        choices=AssetCategory.DepreciationMethod.choices,
        default=AssetCategory.DepreciationMethod.STRAIGHT_LINE,
    )
    useful_life_months = models.PositiveIntegerField(default=60)
    salvage_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )
    depreciation_start_date = models.DateField(null=True, blank=True)

    # Running totals (updated by posting depreciation / revaluation)
    accumulated_depreciation = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )
    current_book_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )

    # GL accounts (fallback to category if blank)
    asset_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fixed_asset_asset',
    )
    depreciation_expense_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fixed_asset_depr_expense',
    )
    accumulated_depreciation_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fixed_asset_accum_depr',
    )
    acquisition_source_account = models.ForeignKey(
        'erp.Account', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fixed_asset_acq_source',
        help_text='Cash / Bank / AP account credited on acquisition',
    )

    status = models.CharField(
        max_length=25, choices=Status.choices, default=Status.DRAFT,
    )
    disposal_date = models.DateField(null=True, blank=True)
    disposal_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    notes = models.TextField(blank=True)

    # Optional: units-of-production fields
    total_estimated_units = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Total estimated units for units-of-production method',
    )
    units_produced = models.PositiveIntegerField(
        default=0,
        help_text='Cumulative units produced so far',
    )

    class Meta:
        verbose_name = 'Fixed Asset'
        verbose_name_plural = 'Fixed Assets'
        ordering = ['-acquisition_date']

    def __str__(self):
        return f"{self.asset_number} – {self.name}"

    # ── Computed helpers ──

    @property
    def depreciable_amount(self):
        """Cost less salvage value."""
        return self.acquisition_cost - self.salvage_value

    @property
    def remaining_book_value(self):
        """Cost less accumulated depreciation."""
        return self.acquisition_cost - self.accumulated_depreciation

    def get_account(self, attr):
        """Return asset-level account, falling back to category."""
        local = getattr(self, attr, None)
        if local:
            return local
        return getattr(self.category, attr, None)

    # ── Depreciation calculation ──

    def calculate_monthly_depreciation(self, extra_units=0):
        """
        Return the depreciation amount for one month (or one unit-batch).
        """
        if self.depreciation_method == AssetCategory.DepreciationMethod.NO_DEPRECIATION:
            return Decimal('0.00')

        if self.depreciation_method == AssetCategory.DepreciationMethod.STRAIGHT_LINE:
            if self.useful_life_months == 0:
                return Decimal('0.00')
            return (self.depreciable_amount / self.useful_life_months).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            )

        if self.depreciation_method == AssetCategory.DepreciationMethod.DECLINING_BALANCE:
            rate = Decimal(1) / Decimal(self.useful_life_months) * 12
            return (self.remaining_book_value * rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            )

        if self.depreciation_method == AssetCategory.DepreciationMethod.DOUBLE_DECLINING:
            rate = Decimal(2) / Decimal(self.useful_life_months) * 12
            return (self.remaining_book_value * rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            )

        if self.depreciation_method == AssetCategory.DepreciationMethod.UNITS_OF_PRODUCTION:
            if not self.total_estimated_units:
                return Decimal('0.00')
            cost_per_unit = self.depreciable_amount / Decimal(self.total_estimated_units)
            return (cost_per_unit * Decimal(extra_units)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            )

        return Decimal('0.00')

    # ── Activation (acquisition journal) ──

    @transaction.atomic
    def activate(self, user, db_alias='default'):
        """
        Post the acquisition journal entry and mark asset as *active*.
        Dr  Asset Account
            Cr  Cash / Payable
        """
        from erp.models import JournalEntry, JournalEntryLine, FiscalYear

        if self.status != self.Status.DRAFT:
            return

        self.status = self.Status.ACTIVE
        self.current_book_value = self.acquisition_cost
        if not self.depreciation_start_date:
            self.depreciation_start_date = self.acquisition_date
        self.save(update_fields=[
            'status', 'current_book_value', 'depreciation_start_date',
        ])

        asset_acct = self.get_account('asset_account')
        source_acct = self.get_account('acquisition_source_account')
        if not asset_acct or not source_acct:
            return  # no journal without accounts

        fiscal_year = FiscalYear.objects.filter(
            company=self.company, is_current=True,
        ).first()

        je = JournalEntry.objects.create(
            company=self.company,
            entry_number=f"FA-ACQ-{self.asset_number}",
            entry_date=self.acquisition_date,
            entry_type='manual',
            description=f"Acquisition of fixed asset: {self.name}",
            reference=self.asset_number,
            fiscal_year=fiscal_year,
            status='draft',
            created_by=user,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=asset_acct,
            description=f"Fixed asset – {self.name}",
            debit_amount=self.acquisition_cost,
            credit_amount=Decimal('0.00'),
            reference_type='FixedAsset',
            reference_id=self.pk,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=source_acct,
            description=f"Acquisition source – {self.name}",
            debit_amount=Decimal('0.00'),
            credit_amount=self.acquisition_cost,
            reference_type='FixedAsset',
            reference_id=self.pk,
        )

        # Post the journal entry so account balances are updated
        je.calculate_totals()
        je.save(update_fields=['total_debit', 'total_credit'])
        je.post(user)
        return je


# ────────────────────────────────────────────────────────────────
# Depreciation Schedule
# ────────────────────────────────────────────────────────────────

class DepreciationSchedule(TimeStampedModel):
    """
    One row per depreciation period.
    Posting creates JournalEntry:
        Dr  Depreciation Expense
            Cr  Accumulated Depreciation
    """

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        POSTED = 'posted', 'Posted'
        CANCELLED = 'cancelled', 'Cancelled'

    asset = models.ForeignKey(
        FixedAsset, on_delete=models.CASCADE,
        related_name='depreciation_schedule',
    )
    period_date = models.DateField(help_text='End of depreciation period')
    depreciation_amount = models.DecimalField(max_digits=15, decimal_places=2)
    accumulated_total = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        help_text='Running total after this period',
    )
    book_value_after = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.SCHEDULED,
    )
    journal_entry = models.ForeignKey(
        'erp.JournalEntry', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='depreciation_entries',
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Depreciation Schedule'
        verbose_name_plural = 'Depreciation Schedules'
        ordering = ['asset', 'period_date']
        unique_together = [('asset', 'period_date')]

    def __str__(self):
        return f"{self.asset.asset_number} – {self.period_date}"

    @transaction.atomic
    def post(self, user):
        """Create journal entry and update asset balances."""
        from erp.models import JournalEntry, JournalEntryLine, FiscalYear
        from django.utils import timezone

        if self.status != self.Status.SCHEDULED:
            return

        asset = self.asset
        depr_exp_acct = asset.get_account('depreciation_expense_account')
        accum_depr_acct = asset.get_account('accumulated_depreciation_account')
        if not depr_exp_acct or not accum_depr_acct:
            raise ValueError('Depreciation and Accumulated Depreciation accounts must be set.')

        fiscal_year = FiscalYear.objects.filter(
            company=asset.company, is_current=True,
        ).first()

        je = JournalEntry.objects.create(
            company=asset.company,
            entry_number=f"FA-DEP-{asset.asset_number}-{self.period_date.strftime('%Y%m')}",
            entry_date=self.period_date,
            entry_type='adjustment',
            description=f"Depreciation – {asset.name} ({self.period_date.strftime('%b %Y')})",
            reference=asset.asset_number,
            fiscal_year=fiscal_year,
            status='draft',
            created_by=user,
        )
        JournalEntryLine.objects.create(
            journal_entry=je, account=depr_exp_acct,
            description=f"Depreciation expense – {asset.name}",
            debit_amount=self.depreciation_amount,
            credit_amount=Decimal('0.00'),
            reference_type='FixedAsset', reference_id=asset.pk,
        )
        JournalEntryLine.objects.create(
            journal_entry=je, account=accum_depr_acct,
            description=f"Accumulated depreciation – {asset.name}",
            debit_amount=Decimal('0.00'),
            credit_amount=self.depreciation_amount,
            reference_type='FixedAsset', reference_id=asset.pk,
        )

        # Post the journal entry so account balances are updated
        je.calculate_totals()
        je.save(update_fields=['total_debit', 'total_credit'])
        je.post(user)

        # Update schedule row
        self.status = self.Status.POSTED
        self.journal_entry = je
        self.posted_by = user
        self.posted_at = timezone.now()
        self.save()

        # Update asset running totals
        asset.accumulated_depreciation += self.depreciation_amount
        asset.current_book_value = asset.acquisition_cost - asset.accumulated_depreciation
        if asset.current_book_value <= asset.salvage_value:
            asset.status = FixedAsset.Status.FULLY_DEPRECIATED
        asset.save(update_fields=[
            'accumulated_depreciation', 'current_book_value', 'status',
        ])

        return je


# ────────────────────────────────────────────────────────────────
# Asset Disposal
# ────────────────────────────────────────────────────────────────

class AssetDisposal(ERPBaseModel):
    """
    Records the sale / write-off of a fixed asset.
    Journal entries handle gain/loss:
        Dr  Cash / Receivable         (sale_amount)
        Dr  Accumulated Depreciation  (accum)
        Dr  Loss on Disposal          (if loss)
            Cr  Fixed Asset Account   (original cost)
            Cr  Gain on Disposal      (if gain)
    """

    class DisposalType(models.TextChoices):
        SALE = 'sale', 'Sale'
        SCRAP = 'scrap', 'Scrap / Write-Off'
        DONATION = 'donation', 'Donation'
        TRADE_IN = 'trade_in', 'Trade-In'
        THEFT_LOSS = 'theft_loss', 'Theft / Loss'

    asset = models.OneToOneField(
        FixedAsset, on_delete=models.CASCADE,
        related_name='disposal',
    )
    disposal_date = models.DateField()
    disposal_type = models.CharField(
        max_length=20, choices=DisposalType.choices, default=DisposalType.SALE,
    )
    sale_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )
    buyer_name = models.CharField(max_length=255, blank=True)
    reason = models.TextField(blank=True)

    # Computed on save
    book_value_at_disposal = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )
    gain_loss = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        help_text='Positive = gain, negative = loss',
    )

    journal_entry = models.ForeignKey(
        'erp.JournalEntry', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='disposal_entries',
    )

    class Meta:
        verbose_name = 'Asset Disposal'
        verbose_name_plural = 'Asset Disposals'
        ordering = ['-disposal_date']

    def __str__(self):
        return f"Disposal of {self.asset.asset_number} – {self.disposal_date}"

    @transaction.atomic
    def process(self, user):
        """Calculate gain/loss, create journal entry, mark asset disposed."""
        from erp.models import JournalEntry, JournalEntryLine, FiscalYear

        asset = self.asset
        self.book_value_at_disposal = asset.current_book_value
        self.gain_loss = self.sale_amount - self.book_value_at_disposal
        self.save(update_fields=['book_value_at_disposal', 'gain_loss'])

        asset_acct = asset.get_account('asset_account')
        accum_depr_acct = asset.get_account('accumulated_depreciation_account')
        gain_acct = asset.category.disposal_gain_account
        loss_acct = asset.category.disposal_loss_account

        fiscal_year = FiscalYear.objects.filter(
            company=asset.company, is_current=True,
        ).first()

        je = JournalEntry.objects.create(
            company=asset.company,
            entry_number=f"FA-DSP-{asset.asset_number}",
            entry_date=self.disposal_date,
            entry_type='manual',
            description=f"Disposal of fixed asset: {asset.name}",
            reference=asset.asset_number,
            fiscal_year=fiscal_year,
            status='draft',
            created_by=user,
        )

        lines = []

        # Dr Accumulated Depreciation (remove contra-asset)
        if accum_depr_acct and asset.accumulated_depreciation > 0:
            lines.append(JournalEntryLine(
                journal_entry=je, account=accum_depr_acct,
                description=f"Remove accumulated depreciation – {asset.name}",
                debit_amount=asset.accumulated_depreciation,
                credit_amount=Decimal('0.00'),
                reference_type='FixedAsset', reference_id=asset.pk,
            ))

        # Dr Cash / Receivable (sale proceeds)
        proceeds_acct = getattr(asset.category, 'disposal_proceeds_account', None)
        if self.sale_amount > 0 and proceeds_acct:
            lines.append(JournalEntryLine(
                journal_entry=je, account=proceeds_acct,
                description=f"Sale proceeds – {asset.name}",
                debit_amount=self.sale_amount,
                credit_amount=Decimal('0.00'),
                reference_type='AssetDisposal', reference_id=self.pk,
            ))

        # Cr Fixed Asset Account (remove from books)
        if asset_acct:
            lines.append(JournalEntryLine(
                journal_entry=je, account=asset_acct,
                description=f"Dispose fixed asset – {asset.name}",
                debit_amount=Decimal('0.00'),
                credit_amount=asset.acquisition_cost,
                reference_type='FixedAsset', reference_id=asset.pk,
            ))

        # Gain or Loss
        if self.gain_loss > 0 and gain_acct:
            lines.append(JournalEntryLine(
                journal_entry=je, account=gain_acct,
                description=f"Gain on disposal – {asset.name}",
                debit_amount=Decimal('0.00'),
                credit_amount=self.gain_loss,
                reference_type='AssetDisposal', reference_id=self.pk,
            ))
        elif self.gain_loss < 0 and loss_acct:
            lines.append(JournalEntryLine(
                journal_entry=je, account=loss_acct,
                description=f"Loss on disposal – {asset.name}",
                debit_amount=abs(self.gain_loss),
                credit_amount=Decimal('0.00'),
                reference_type='AssetDisposal', reference_id=self.pk,
            ))

        JournalEntryLine.objects.bulk_create(lines)

        # Post the journal entry so account balances are updated
        je.calculate_totals()
        je.save(update_fields=['total_debit', 'total_credit'])
        je.post(user)

        self.journal_entry = je
        self.save(update_fields=['journal_entry'])

        # Update asset status
        asset.status = FixedAsset.Status.DISPOSED
        asset.disposal_date = self.disposal_date
        asset.disposal_amount = self.sale_amount
        asset.save(update_fields=['status', 'disposal_date', 'disposal_amount'])

        return je


# ────────────────────────────────────────────────────────────────
# Asset Transfer
# ────────────────────────────────────────────────────────────────

class AssetTransfer(ERPBaseModel):
    """Transfer an asset between departments, locations or custodians."""

    asset = models.ForeignKey(
        FixedAsset, on_delete=models.CASCADE, related_name='transfers',
    )
    transfer_date = models.DateField()

    from_department = models.ForeignKey(
        'erp.Department', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asset_transfers_out',
    )
    to_department = models.ForeignKey(
        'erp.Department', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asset_transfers_in',
    )
    from_location = models.CharField(max_length=255, blank=True)
    to_location = models.CharField(max_length=255, blank=True)
    from_custodian = models.ForeignKey(
        'erp.Employee', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asset_transfers_from',
    )
    to_custodian = models.ForeignKey(
        'erp.Employee', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asset_transfers_to',
    )
    reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_asset_transfers',
    )

    class Meta:
        verbose_name = 'Asset Transfer'
        verbose_name_plural = 'Asset Transfers'
        ordering = ['-transfer_date']

    def __str__(self):
        return f"Transfer {self.asset.asset_number} on {self.transfer_date}"

    @transaction.atomic
    def apply(self):
        """Apply the transfer to the asset record."""
        asset = self.asset
        if self.to_department:
            asset.department = self.to_department
        if self.to_location:
            asset.location = self.to_location
        if self.to_custodian:
            asset.custodian = self.to_custodian
        asset.save(update_fields=['department', 'location', 'custodian'])


# ────────────────────────────────────────────────────────────────
# Asset Revaluation
# ────────────────────────────────────────────────────────────────

class AssetRevaluation(ERPBaseModel):
    """
    Revalue an asset up or down.
    Journal:
        Increase → Dr Asset Account, Cr Revaluation Surplus (or reverse accumulated depreciation)
        Decrease → Dr Revaluation Loss, Cr Asset Account
    """

    asset = models.ForeignKey(
        FixedAsset, on_delete=models.CASCADE, related_name='revaluations',
    )
    revaluation_date = models.DateField()
    old_value = models.DecimalField(max_digits=15, decimal_places=2)
    new_value = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    reason = models.TextField(blank=True)
    appraiser = models.CharField(max_length=255, blank=True, help_text='Name of appraiser / valuer')

    journal_entry = models.ForeignKey(
        'erp.JournalEntry', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='revaluation_entries',
    )

    class Meta:
        verbose_name = 'Asset Revaluation'
        verbose_name_plural = 'Asset Revaluations'
        ordering = ['-revaluation_date']

    def __str__(self):
        return f"Revaluation {self.asset.asset_number} – {self.revaluation_date}"

    @property
    def revaluation_amount(self):
        return self.new_value - self.old_value

    @transaction.atomic
    def process(self, user):
        """Create journal entry and update asset book value."""
        from erp.models import JournalEntry, JournalEntryLine, FiscalYear

        asset = self.asset
        diff = self.new_value - self.old_value
        if diff == 0:
            return

        asset_acct = asset.get_account('asset_account')
        if not asset_acct:
            return

        fiscal_year = FiscalYear.objects.filter(
            company=asset.company, is_current=True,
        ).first()

        je = JournalEntry.objects.create(
            company=asset.company,
            entry_number=f"FA-REV-{asset.asset_number}-{self.revaluation_date.strftime('%Y%m%d')}",
            entry_date=self.revaluation_date,
            entry_type='adjustment',
            description=f"Revaluation of {asset.name}: {self.old_value} → {self.new_value}",
            reference=asset.asset_number,
            fiscal_year=fiscal_year,
            status='draft',
            created_by=user,
        )

        surplus_acct = getattr(asset.category, 'revaluation_surplus_account', None)
        contra_acct = surplus_acct or asset_acct  # fallback to asset account

        if diff > 0:
            # Increase: Dr Asset Account, Cr Revaluation Surplus
            JournalEntryLine.objects.bulk_create([
                JournalEntryLine(
                    journal_entry=je, account=asset_acct,
                    description=f"Revaluation increase \u2013 {asset.name}",
                    debit_amount=abs(diff), credit_amount=Decimal('0.00'),
                    reference_type='AssetRevaluation', reference_id=self.pk,
                ),
                JournalEntryLine(
                    journal_entry=je, account=contra_acct,
                    description=f"Revaluation surplus \u2013 {asset.name}",
                    debit_amount=Decimal('0.00'), credit_amount=abs(diff),
                    reference_type='AssetRevaluation', reference_id=self.pk,
                ),
            ])
        else:
            # Decrease: Dr Revaluation Loss/Surplus, Cr Asset Account
            JournalEntryLine.objects.bulk_create([
                JournalEntryLine(
                    journal_entry=je, account=contra_acct,
                    description=f"Revaluation decrease \u2013 {asset.name}",
                    debit_amount=abs(diff), credit_amount=Decimal('0.00'),
                    reference_type='AssetRevaluation', reference_id=self.pk,
                ),
                JournalEntryLine(
                    journal_entry=je, account=asset_acct,
                    description=f"Revaluation decrease \u2013 {asset.name}",
                    debit_amount=Decimal('0.00'), credit_amount=abs(diff),
                    reference_type='AssetRevaluation', reference_id=self.pk,
                ),
            ])

        # Post the journal entry so account balances are updated
        je.calculate_totals()
        je.save(update_fields=['total_debit', 'total_credit'])
        je.post(user)

        self.journal_entry = je
        self.save(update_fields=['journal_entry'])

        # Update asset
        asset.current_book_value = self.new_value
        asset.save(update_fields=['current_book_value'])

        return je


# ────────────────────────────────────────────────────────────────
# Asset Maintenance Log
# ────────────────────────────────────────────────────────────────

class AssetMaintenanceLog(ERPBaseModel):
    """Track maintenance, repairs, and inspections for a fixed asset."""

    class MaintenanceType(models.TextChoices):
        PREVENTIVE = 'preventive', 'Preventive'
        CORRECTIVE = 'corrective', 'Corrective / Repair'
        INSPECTION = 'inspection', 'Inspection'
        UPGRADE = 'upgrade', 'Upgrade'
        CALIBRATION = 'calibration', 'Calibration'

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    asset = models.ForeignKey(
        FixedAsset, on_delete=models.CASCADE, related_name='maintenance_logs',
    )
    maintenance_type = models.CharField(
        max_length=20, choices=MaintenanceType.choices,
        default=MaintenanceType.CORRECTIVE,
    )
    description = models.TextField()
    scheduled_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )
    vendor = models.CharField(max_length=255, blank=True, help_text='Service provider name')
    performed_by = models.ForeignKey(
        'erp.Employee', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asset_maintenance_performed',
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.SCHEDULED,
    )
    notes = models.TextField(blank=True)

    # Optional expense linkage
    expense = models.ForeignKey(
        'erp.Expense', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asset_maintenance_logs',
    )

    class Meta:
        verbose_name = 'Asset Maintenance Log'
        verbose_name_plural = 'Asset Maintenance Logs'
        ordering = ['-scheduled_date']

    def __str__(self):
        return f"{self.get_maintenance_type_display()} – {self.asset.asset_number}"
