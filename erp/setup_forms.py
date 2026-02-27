"""
ERP Setup Wizard Forms

Multi-step forms for first-time ERP system setup.
All labels use gettext_lazy for i18n; dynamic choice lists are rebuilt
per-request via __init__ so they match the active language.
"""

from django import forms
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _, get_language
from decimal import Decimal

from .models import Currency, Company, FiscalYear, TaxRate, PaymentMethod, Account
from .setup_defaults import (
    get_currency_choices,
    get_tax_preset_choices,
    get_chart_preset_choices,
    get_fiscal_start_choices,
    get_text,
    DEFAULT_COUNTRY,
)


class BootstrapFormMixin:
    """Add Bootstrap classes to all form fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'form-control'
                field.widget.attrs.setdefault('rows', 3)
            else:
                field.widget.attrs['class'] = 'form-control'


# =============================================================================
# Step 1: Currency Setup
# =============================================================================

class CurrencySetupForm(BootstrapFormMixin, forms.Form):
    """Step 1: Setup base currency."""

    base_currency = forms.ChoiceField(
        choices=[],
        initial='SAR',
        label=_('Base Currency'),
        help_text=_('Choose the base currency for the system. It will be used in all financial transactions.'),
    )

    custom_currency_code = forms.CharField(
        max_length=3,
        required=False,
        label=_('Currency Code'),
        help_text=_('Currency code (3 letters), e.g. SAR, USD'),
    )

    custom_currency_name = forms.CharField(
        max_length=100,
        required=False,
        label=_('Currency Name'),
    )

    custom_currency_symbol = forms.CharField(
        max_length=10,
        required=False,
        label=_('Currency Symbol'),
        help_text=_('e.g. ر.س, $, €'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = get_language() or 'en'
        self.fields['base_currency'].choices = get_currency_choices(lang)

    def clean(self):
        cleaned_data = super().clean()
        base_currency = cleaned_data.get('base_currency')

        if base_currency == 'OTHER':
            if not cleaned_data.get('custom_currency_code'):
                self.add_error('custom_currency_code', _('Required when choosing a custom currency'))
            if not cleaned_data.get('custom_currency_name'):
                self.add_error('custom_currency_name', _('Required when choosing a custom currency'))
            if not cleaned_data.get('custom_currency_symbol'):
                self.add_error('custom_currency_symbol', _('Required when choosing a custom currency'))

        return cleaned_data


# =============================================================================
# Step 2: Company Setup
# =============================================================================

class CompanySetupForm(BootstrapFormMixin, forms.Form):
    """Step 2: Setup company information."""

    name = forms.CharField(
        max_length=255,
        label=_('Company Name'),
        help_text=_('The trade / display name of the company'),
    )

    name_ar = forms.CharField(
        max_length=255,
        required=False,
        label=_('Company Name (Arabic)'),
    )

    legal_name = forms.CharField(
        max_length=255,
        required=False,
        label=_('Legal Name'),
        help_text=_('Official registered name'),
    )

    email = forms.EmailField(
        label=_('Email'),
        help_text=_('Official company email'),
    )

    phone = forms.CharField(
        max_length=20,
        label=_('Phone Number'),
    )

    tax_number = forms.CharField(
        max_length=50,
        required=False,
        label=_('Tax Registration Number'),
        help_text=_('VAT / Tax ID number'),
    )

    commercial_register = forms.CharField(
        max_length=50,
        required=False,
        label=_('Commercial Register'),
    )

    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        label=_('Address'),
    )

    city = forms.CharField(
        max_length=100,
        label=_('City'),
    )

    country = forms.CharField(
        max_length=100,
        label=_('Country'),
    )

    postal_code = forms.CharField(
        max_length=20,
        required=False,
        label=_('Postal Code'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = get_language() or 'en'
        self.fields['country'].initial = get_text(DEFAULT_COUNTRY, lang)


# =============================================================================
# Step 3: Fiscal Year Setup
# =============================================================================

class FiscalYearSetupForm(BootstrapFormMixin, forms.Form):
    """Step 3: Setup fiscal year."""

    fiscal_year_start = forms.ChoiceField(
        choices=[],
        initial=1,
        label=_('Fiscal Year Start'),
        help_text=_('The month the fiscal year begins'),
    )

    fiscal_year_name = forms.CharField(
        max_length=50,
        label=_('Fiscal Year Name'),
        help_text=_('e.g. FY2026'),
    )

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Start Date'),
    )

    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('End Date'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = get_language() or 'en'
        self.fields['fiscal_year_start'].choices = get_fiscal_start_choices(lang)


# =============================================================================
# Step 4: Tax Setup
# =============================================================================

class TaxSetupForm(BootstrapFormMixin, forms.Form):
    """Step 4: Setup tax rates."""

    tax_preset = forms.ChoiceField(
        choices=[],
        initial='sa_vat',
        label=_('Tax Preset'),
        help_text=_('Choose the tax type appropriate for your country'),
    )

    custom_tax_name = forms.CharField(
        max_length=100,
        required=False,
        label=_('Tax Name'),
    )

    custom_tax_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        validators=[MinValueValidator(Decimal('0'))],
        label=_('Tax Rate (%)'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = get_language() or 'en'
        self.fields['tax_preset'].choices = get_tax_preset_choices(lang)


# =============================================================================
# Step 5: Payment Methods Setup
# =============================================================================

class PaymentMethodsSetupForm(BootstrapFormMixin, forms.Form):
    """Step 5: Setup payment methods."""

    enable_cash = forms.BooleanField(
        initial=True,
        required=False,
        label=_('Cash'),
        help_text=_('Cash payment'),
    )

    enable_bank_transfer = forms.BooleanField(
        initial=True,
        required=False,
        label=_('Bank Transfer'),
        help_text=_('Wire / bank transfer'),
    )

    enable_credit_card = forms.BooleanField(
        initial=True,
        required=False,
        label=_('Credit Card'),
        help_text=_('Credit card payment'),
    )

    enable_mada = forms.BooleanField(
        initial=True,
        required=False,
        label=_('Mada'),
        help_text=_('Mada debit card'),
    )

    enable_stc_pay = forms.BooleanField(
        initial=False,
        required=False,
        label=_('STC Pay'),
    )

    enable_apple_pay = forms.BooleanField(
        initial=False,
        required=False,
        label=_('Apple Pay'),
    )

    bank_name = forms.CharField(
        max_length=255,
        required=False,
        label=_('Bank Name'),
        help_text=_('Primary bank for the company'),
    )

    bank_account = forms.CharField(
        max_length=50,
        required=False,
        label=_('Account Number'),
    )

    iban = forms.CharField(
        max_length=50,
        required=False,
        label=_('IBAN'),
    )


# =============================================================================
# Step 6: Chart of Accounts Setup
# =============================================================================

class ChartOfAccountsSetupForm(BootstrapFormMixin, forms.Form):
    """Step 6: Setup chart of accounts."""

    chart_preset = forms.ChoiceField(
        choices=[],
        initial='standard',
        label=_('Chart of Accounts Preset'),
        help_text=_('Choose the chart of accounts suitable for your business'),
    )

    create_sample_data = forms.BooleanField(
        initial=False,
        required=False,
        label=_('Create sample data'),
        help_text=_('Add sample customers and invoices for learning'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = get_language() or 'en'
        self.fields['chart_preset'].choices = get_chart_preset_choices(lang)


# =============================================================================
# Complete Form for All Steps
# =============================================================================

class SetupCompleteForm(forms.Form):
    """Final confirmation form."""

    confirm = forms.BooleanField(
        required=True,
        label=_('I confirm that all information is correct'),
    )

    accept_terms = forms.BooleanField(
        required=True,
        label=_('I accept the terms of use'),
    )
