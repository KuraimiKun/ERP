"""
ERP Setup Wizard Forms

Multi-step forms for first-time ERP system setup.
"""

from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal

from .models import Currency, Company, FiscalYear, TaxRate, PaymentMethod, Account


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
    
    CURRENCY_CHOICES = [
        ('SAR', 'ريال سعودي (SAR)'),
        ('AED', 'درهم إماراتي (AED)'),
        ('USD', 'دولار أمريكي (USD)'),
        ('EUR', 'يورو (EUR)'),
        ('GBP', 'جنيه إسترليني (GBP)'),
        ('EGP', 'جنيه مصري (EGP)'),
        ('KWD', 'دينار كويتي (KWD)'),
        ('QAR', 'ريال قطري (QAR)'),
        ('BHD', 'دينار بحريني (BHD)'),
        ('OMR', 'ريال عماني (OMR)'),
        ('JOD', 'دينار أردني (JOD)'),
        ('OTHER', 'عملة أخرى'),
    ]
    
    base_currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        initial='SAR',
        label='العملة الأساسية',
        help_text='اختر العملة الأساسية للنظام. سيتم استخدامها في جميع المعاملات المالية.',
    )
    
    custom_currency_code = forms.CharField(
        max_length=3,
        required=False,
        label='رمز العملة',
        help_text='رمز العملة (3 أحرف) مثل SAR, USD',
    )
    
    custom_currency_name = forms.CharField(
        max_length=100,
        required=False,
        label='اسم العملة',
    )
    
    custom_currency_symbol = forms.CharField(
        max_length=10,
        required=False,
        label='رمز العملة',
        help_text='مثل: ر.س، $، €',
    )
    
    def clean(self):
        cleaned_data = super().clean()
        base_currency = cleaned_data.get('base_currency')
        
        if base_currency == 'OTHER':
            if not cleaned_data.get('custom_currency_code'):
                self.add_error('custom_currency_code', 'مطلوب عند اختيار عملة أخرى')
            if not cleaned_data.get('custom_currency_name'):
                self.add_error('custom_currency_name', 'مطلوب عند اختيار عملة أخرى')
            if not cleaned_data.get('custom_currency_symbol'):
                self.add_error('custom_currency_symbol', 'مطلوب عند اختيار عملة أخرى')
        
        return cleaned_data


# =============================================================================
# Step 2: Company Setup
# =============================================================================

class CompanySetupForm(BootstrapFormMixin, forms.Form):
    """Step 2: Setup company information."""
    
    name = forms.CharField(
        max_length=255,
        label='اسم الشركة',
        help_text='الاسم التجاري للشركة',
    )
    
    name_ar = forms.CharField(
        max_length=255,
        required=False,
        label='اسم الشركة (عربي)',
    )
    
    legal_name = forms.CharField(
        max_length=255,
        required=False,
        label='الاسم القانوني',
        help_text='الاسم الرسمي المسجل',
    )
    
    email = forms.EmailField(
        label='البريد الإلكتروني',
        help_text='البريد الإلكتروني الرسمي للشركة',
    )
    
    phone = forms.CharField(
        max_length=20,
        label='رقم الهاتف',
    )
    
    tax_number = forms.CharField(
        max_length=50,
        required=False,
        label='الرقم الضريبي',
        help_text='رقم التسجيل الضريبي/VAT',
    )
    
    commercial_register = forms.CharField(
        max_length=50,
        required=False,
        label='السجل التجاري',
    )
    
    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        label='العنوان',
    )
    
    city = forms.CharField(
        max_length=100,
        label='المدينة',
    )
    
    country = forms.CharField(
        max_length=100,
        initial='المملكة العربية السعودية',
        label='الدولة',
    )
    
    postal_code = forms.CharField(
        max_length=20,
        required=False,
        label='الرمز البريدي',
    )


# =============================================================================
# Step 3: Fiscal Year Setup
# =============================================================================

class FiscalYearSetupForm(BootstrapFormMixin, forms.Form):
    """Step 3: Setup fiscal year."""
    
    FISCAL_START_CHOICES = [
        (1, 'يناير (السنة الميلادية)'),
        (4, 'أبريل'),
        (7, 'يوليو'),
        (10, 'أكتوبر'),
    ]
    
    fiscal_year_start = forms.ChoiceField(
        choices=FISCAL_START_CHOICES,
        initial=1,
        label='بداية السنة المالية',
        help_text='الشهر الذي تبدأ فيه السنة المالية',
    )
    
    fiscal_year_name = forms.CharField(
        max_length=50,
        label='اسم السنة المالية',
        help_text='مثال: 2026 أو FY2026',
    )
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='تاريخ البداية',
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='تاريخ النهاية',
    )


# =============================================================================
# Step 4: Tax Setup
# =============================================================================

class TaxSetupForm(BootstrapFormMixin, forms.Form):
    """Step 4: Setup tax rates."""
    
    TAX_PRESET_CHOICES = [
        ('sa_vat', 'ضريبة القيمة المضافة السعودية (15%)'),
        ('ae_vat', 'ضريبة القيمة المضافة الإماراتية (5%)'),
        ('eg_vat', 'ضريبة القيمة المضافة المصرية (14%)'),
        ('custom', 'ضريبة مخصصة'),
        ('none', 'بدون ضريبة'),
    ]
    
    tax_preset = forms.ChoiceField(
        choices=TAX_PRESET_CHOICES,
        initial='sa_vat',
        label='إعداد الضريبة',
        help_text='اختر نوع الضريبة المناسب لبلدك',
    )
    
    custom_tax_name = forms.CharField(
        max_length=100,
        required=False,
        label='اسم الضريبة',
    )
    
    custom_tax_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        validators=[MinValueValidator(Decimal('0'))],
        label='نسبة الضريبة (%)',
    )


# =============================================================================
# Step 5: Payment Methods Setup
# =============================================================================

class PaymentMethodsSetupForm(BootstrapFormMixin, forms.Form):
    """Step 5: Setup payment methods."""
    
    enable_cash = forms.BooleanField(
        initial=True,
        required=False,
        label='نقداً',
        help_text='الدفع النقدي',
    )
    
    enable_bank_transfer = forms.BooleanField(
        initial=True,
        required=False,
        label='تحويل بنكي',
        help_text='التحويل المصرفي',
    )
    
    enable_credit_card = forms.BooleanField(
        initial=True,
        required=False,
        label='بطاقة ائتمان',
        help_text='الدفع ببطاقة الائتمان',
    )
    
    enable_mada = forms.BooleanField(
        initial=True,
        required=False,
        label='مدى',
        help_text='بطاقة مدى',
    )
    
    enable_stc_pay = forms.BooleanField(
        initial=False,
        required=False,
        label='STC Pay',
    )
    
    enable_apple_pay = forms.BooleanField(
        initial=False,
        required=False,
        label='Apple Pay',
    )
    
    bank_name = forms.CharField(
        max_length=255,
        required=False,
        label='اسم البنك',
        help_text='البنك الرئيسي للشركة',
    )
    
    bank_account = forms.CharField(
        max_length=50,
        required=False,
        label='رقم الحساب',
    )
    
    iban = forms.CharField(
        max_length=50,
        required=False,
        label='رقم الآيبان (IBAN)',
    )


# =============================================================================
# Step 6: Chart of Accounts Setup
# =============================================================================

class ChartOfAccountsSetupForm(BootstrapFormMixin, forms.Form):
    """Step 6: Setup chart of accounts."""
    
    CHART_PRESET_CHOICES = [
        ('standard', 'الدليل المحاسبي القياسي'),
        ('travel_agency', 'دليل وكالات السفر'),
        ('services', 'دليل شركات الخدمات'),
        ('minimal', 'دليل مبسط'),
    ]
    
    chart_preset = forms.ChoiceField(
        choices=CHART_PRESET_CHOICES,
        initial='travel_agency',
        label='نوع الدليل المحاسبي',
        help_text='اختر الدليل المحاسبي المناسب لنشاطك',
    )
    
    create_sample_data = forms.BooleanField(
        initial=False,
        required=False,
        label='إنشاء بيانات تجريبية',
        help_text='إضافة عملاء وفواتير تجريبية للتعلم',
    )


# =============================================================================
# Complete Form for All Steps
# =============================================================================

class SetupCompleteForm(forms.Form):
    """Final confirmation form."""
    
    confirm = forms.BooleanField(
        required=True,
        label='أؤكد أن جميع البيانات صحيحة',
    )
    
    accept_terms = forms.BooleanField(
        required=True,
        label='أوافق على شروط الاستخدام',
    )
