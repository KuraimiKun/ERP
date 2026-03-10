"""
ERP Forms – Fixed Assets Management

Forms for asset categories, assets, depreciation, disposal,
transfers, revaluations, and maintenance logs.
"""

from django import forms

from erp.models.fixed_assets import (
    AssetCategory, FixedAsset, DepreciationSchedule,
    AssetDisposal, AssetTransfer, AssetRevaluation,
    AssetMaintenanceLog,
)
from .mixins import BootstrapFormMixin, CompanyFilterMixin


# ── Asset Category ──────────────────────────────────────────────

class AssetCategoryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = AssetCategory
        fields = [
            'name', 'name_ar', 'code', 'description',
            'depreciation_method', 'useful_life_months', 'salvage_value_percent',
            'asset_account', 'depreciation_expense_account',
            'accumulated_depreciation_account',
            'disposal_gain_account', 'disposal_loss_account',
            'acquisition_source_account', 'disposal_proceeds_account',
            'revaluation_surplus_account',
            'is_active',
        ]


# ── Fixed Asset ─────────────────────────────────────────────────

class FixedAssetForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = FixedAsset
        fields = [
            'asset_number', 'name', 'name_ar', 'description', 'category',
            'acquisition_date', 'acquisition_cost', 'currency',
            'supplier', 'purchase_order', 'invoice_reference',
            'department', 'location', 'custodian',
            'serial_number', 'barcode',
            'depreciation_method', 'useful_life_months', 'salvage_value',
            'depreciation_start_date',
            'asset_account', 'depreciation_expense_account',
            'accumulated_depreciation_account',
            'acquisition_source_account',
            'total_estimated_units',
            'notes',
        ]
        widgets = {
            'acquisition_date': forms.DateInput(attrs={'type': 'date'}),
            'depreciation_start_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.company:
            self.fields['category'].queryset = AssetCategory.objects.filter(
                company=self.company, is_active=True,
            )


# ── Depreciation Schedule (manual entry / override) ────────────

class DepreciationScheduleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DepreciationSchedule
        fields = ['period_date', 'depreciation_amount', 'notes']
        widgets = {
            'period_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


# ── Asset Disposal ──────────────────────────────────────────────

class AssetDisposalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetDisposal
        fields = [
            'disposal_date', 'disposal_type', 'sale_amount',
            'buyer_name', 'reason',
        ]
        widgets = {
            'disposal_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }


# ── Asset Transfer ──────────────────────────────────────────────

class AssetTransferForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = AssetTransfer
        fields = [
            'transfer_date',
            'from_department', 'to_department',
            'from_location', 'to_location',
            'from_custodian', 'to_custodian',
            'reason',
        ]
        widgets = {
            'transfer_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }


# ── Asset Revaluation ──────────────────────────────────────────

class AssetRevaluationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssetRevaluation
        fields = [
            'revaluation_date', 'new_value', 'reason', 'appraiser',
        ]
        widgets = {
            'revaluation_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }


# ── Asset Maintenance Log ──────────────────────────────────────

class AssetMaintenanceLogForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = AssetMaintenanceLog
        fields = [
            'maintenance_type', 'description',
            'scheduled_date', 'completion_date',
            'cost', 'vendor', 'performed_by',
            'status', 'notes',
        ]
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'completion_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


# ── Generate Depreciation (utility form) ───────────────────────

class GenerateDepreciationForm(BootstrapFormMixin, forms.Form):
    """Form to batch-generate depreciation schedules for an asset."""
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    periods = forms.IntegerField(
        min_value=1, max_value=600,
        help_text='Number of monthly periods to generate',
    )
