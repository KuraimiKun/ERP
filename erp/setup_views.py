"""
ERP Setup Wizard Views

Multi-step wizard for first-time ERP system setup.
"""

import datetime
from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse

from .models import (
    Currency, Company, FiscalYear, TaxRate, PaymentMethod,
    Account, Branch, Sequence, SystemSetting, ExpenseCategory,
)
from .setup_forms import (
    CurrencySetupForm, CompanySetupForm, FiscalYearSetupForm,
    TaxSetupForm, PaymentMethodsSetupForm, ChartOfAccountsSetupForm,
    SetupCompleteForm,
)

# Import tenant_required decorator and use it as staff_member_required
from .decorators import tenant_required as staff_member_required


# =============================================================================
# Setup Status Check
# =============================================================================

def is_setup_complete():
    """Check if ERP setup has been completed."""
    # Check if any company exists
    if not Company.objects.exists():
        return False
    
    # Check if base currency exists
    if not Currency.objects.filter(is_base=True).exists():
        return False
    
    # Check for setup complete flag in SystemSetting
    company = Company.objects.first()
    if company:
        setting = SystemSetting.objects.filter(
            company=company,
            key='setup.complete'
        ).first()
        if setting and setting.get_value():
            return True
    
    return False


def get_setup_progress(request):
    """Get current setup progress from session."""
    return request.session.get('erp_setup', {
        'current_step': 1,
        'currency_data': {},
        'company_data': {},
        'fiscal_year_data': {},
        'tax_data': {},
        'payment_methods_data': {},
        'chart_data': {},
    })


def save_setup_progress(request, data):
    """Save setup progress to session."""
    request.session['erp_setup'] = data
    request.session.modified = True


# =============================================================================
# Setup Wizard Views
# =============================================================================

SETUP_STEPS = [
    {'number': 1, 'name': 'العملة', 'icon': 'bi-currency-exchange'},
    {'number': 2, 'name': 'الشركة', 'icon': 'bi-building'},
    {'number': 3, 'name': 'السنة المالية', 'icon': 'bi-calendar3'},
    {'number': 4, 'name': 'الضرائب', 'icon': 'bi-percent'},
    {'number': 5, 'name': 'طرق الدفع', 'icon': 'bi-credit-card'},
    {'number': 6, 'name': 'الحسابات', 'icon': 'bi-journal-text'},
    {'number': 7, 'name': 'المراجعة', 'icon': 'bi-check-circle'},
]


@staff_member_required
def setup_wizard(request):
    """Main setup wizard dispatcher."""
    if is_setup_complete():
        return redirect('erp:dashboard')
    
    progress = get_setup_progress(request)
    current_step = progress.get('current_step', 1)
    
    # Redirect to the current step
    step_views = {
        1: 'erp:setup_step_currency',
        2: 'erp:setup_step_company',
        3: 'erp:setup_step_fiscal_year',
        4: 'erp:setup_step_tax',
        5: 'erp:setup_step_payment_methods',
        6: 'erp:setup_step_chart',
        7: 'erp:setup_step_review',
    }
    
    return redirect(step_views.get(current_step, 'erp:setup_step_currency'))


@staff_member_required
def setup_step_currency(request):
    """Step 1: Currency setup."""
    progress = get_setup_progress(request)
    
    if request.method == 'POST':
        form = CurrencySetupForm(request.POST)
        if form.is_valid():
            progress['currency_data'] = form.cleaned_data
            progress['current_step'] = 2
            save_setup_progress(request, progress)
            return redirect('erp:setup_step_company')
    else:
        initial = progress.get('currency_data', {})
        form = CurrencySetupForm(initial=initial)
    
    return render(request, 'erp/setup/step_currency.html', {
        'form': form,
        'steps': SETUP_STEPS,
        'current_step': 1,
        'progress': progress,
    })


@staff_member_required
def setup_step_company(request):
    """Step 2: Company setup."""
    progress = get_setup_progress(request)
    
    if request.method == 'POST':
        form = CompanySetupForm(request.POST)
        if form.is_valid():
            progress['company_data'] = form.cleaned_data
            progress['current_step'] = 3
            save_setup_progress(request, progress)
            return redirect('erp:setup_step_fiscal_year')
    else:
        initial = progress.get('company_data', {})
        form = CompanySetupForm(initial=initial)
    
    return render(request, 'erp/setup/step_company.html', {
        'form': form,
        'steps': SETUP_STEPS,
        'current_step': 2,
        'progress': progress,
    })


@staff_member_required
def setup_step_fiscal_year(request):
    """Step 3: Fiscal year setup."""
    progress = get_setup_progress(request)
    
    # Default dates
    today = timezone.now().date()
    default_start = datetime.date(today.year, 1, 1)
    default_end = datetime.date(today.year, 12, 31)
    
    if request.method == 'POST':
        form = FiscalYearSetupForm(request.POST)
        if form.is_valid():
            # Convert dates to ISO strings for JSON serialization
            data = form.cleaned_data.copy()
            if 'start_date' in data and data['start_date']:
                data['start_date'] = data['start_date'].isoformat()
            if 'end_date' in data and data['end_date']:
                data['end_date'] = data['end_date'].isoformat()
            progress['fiscal_year_data'] = data
            progress['current_step'] = 4
            save_setup_progress(request, progress)
            return redirect('erp:setup_step_tax')
    else:
        initial = progress.get('fiscal_year_data', {
            'fiscal_year_name': f'السنة المالية {today.year}',
            'start_date': default_start.isoformat(),
            'end_date': default_end.isoformat(),
        })
        form = FiscalYearSetupForm(initial=initial)
    
    return render(request, 'erp/setup/step_fiscal_year.html', {
        'form': form,
        'steps': SETUP_STEPS,
        'current_step': 3,
        'progress': progress,
    })


@staff_member_required
def setup_step_tax(request):
    """Step 4: Tax setup."""
    progress = get_setup_progress(request)
    
    if request.method == 'POST':
        form = TaxSetupForm(request.POST)
        if form.is_valid():
            progress['tax_data'] = form.cleaned_data
            progress['current_step'] = 5
            save_setup_progress(request, progress)
            return redirect('erp:setup_step_payment_methods')
    else:
        initial = progress.get('tax_data', {})
        form = TaxSetupForm(initial=initial)
    
    return render(request, 'erp/setup/step_tax.html', {
        'form': form,
        'steps': SETUP_STEPS,
        'current_step': 4,
        'progress': progress,
    })


@staff_member_required
def setup_step_payment_methods(request):
    """Step 5: Payment methods setup."""
    progress = get_setup_progress(request)
    
    if request.method == 'POST':
        form = PaymentMethodsSetupForm(request.POST)
        if form.is_valid():
            progress['payment_methods_data'] = form.cleaned_data
            progress['current_step'] = 6
            save_setup_progress(request, progress)
            return redirect('erp:setup_step_chart')
    else:
        initial = progress.get('payment_methods_data', {})
        form = PaymentMethodsSetupForm(initial=initial)
    
    return render(request, 'erp/setup/step_payment_methods.html', {
        'form': form,
        'steps': SETUP_STEPS,
        'current_step': 5,
        'progress': progress,
    })


@staff_member_required
def setup_step_chart(request):
    """Step 6: Chart of accounts setup."""
    progress = get_setup_progress(request)
    
    if request.method == 'POST':
        form = ChartOfAccountsSetupForm(request.POST)
        if form.is_valid():
            progress['chart_data'] = form.cleaned_data
            progress['current_step'] = 7
            save_setup_progress(request, progress)
            return redirect('erp:setup_step_review')
    else:
        initial = progress.get('chart_data', {})
        form = ChartOfAccountsSetupForm(initial=initial)
    
    return render(request, 'erp/setup/step_chart.html', {
        'form': form,
        'steps': SETUP_STEPS,
        'current_step': 6,
        'progress': progress,
    })


@staff_member_required
def setup_step_review(request):
    """Step 7: Review and confirm."""
    progress = get_setup_progress(request)
    
    if request.method == 'POST':
        form = SetupCompleteForm(request.POST)
        if form.is_valid():
            # Execute the setup
            try:
                execute_setup(request, progress)
                # Clear session data
                if 'erp_setup' in request.session:
                    del request.session['erp_setup']
                messages.success(request, 'تم إعداد النظام بنجاح! مرحباً بك في نظام إدارة المؤسسات.')
                return redirect('erp:dashboard')
            except Exception as e:
                messages.error(request, f'حدث خطأ أثناء الإعداد: {str(e)}')
    else:
        form = SetupCompleteForm()
    
    return render(request, 'erp/setup/step_review.html', {
        'form': form,
        'steps': SETUP_STEPS,
        'current_step': 7,
        'progress': progress,
    })


@staff_member_required
def setup_go_back(request, step):
    """Go back to a previous step."""
    progress = get_setup_progress(request)
    if step >= 1 and step <= 7:
        progress['current_step'] = step
        save_setup_progress(request, progress)
    
    step_views = {
        1: 'erp:setup_step_currency',
        2: 'erp:setup_step_company',
        3: 'erp:setup_step_fiscal_year',
        4: 'erp:setup_step_tax',
        5: 'erp:setup_step_payment_methods',
        6: 'erp:setup_step_chart',
        7: 'erp:setup_step_review',
    }
    
    return redirect(step_views.get(step, 'erp:setup_step_currency'))


# =============================================================================
# Execute Setup
# =============================================================================

@transaction.atomic
def execute_setup(request, progress):
    """Execute the actual setup based on collected data."""
    
    currency_data = progress.get('currency_data', {})
    company_data = progress.get('company_data', {})
    fiscal_year_data = progress.get('fiscal_year_data', {})
    tax_data = progress.get('tax_data', {})
    payment_methods_data = progress.get('payment_methods_data', {})
    chart_data = progress.get('chart_data', {})
    
    # -------------------------------------------------------------------------
    # Step 1: Create Currency
    # -------------------------------------------------------------------------
    currency_code = currency_data.get('base_currency', 'SAR')
    
    currency_map = {
        'SAR': ('ريال سعودي', 'ر.س'),
        'AED': ('درهم إماراتي', 'د.إ'),
        'USD': ('دولار أمريكي', '$'),
        'EUR': ('يورو', '€'),
        'GBP': ('جنيه إسترليني', '£'),
        'EGP': ('جنيه مصري', 'ج.م'),
        'KWD': ('دينار كويتي', 'د.ك'),
        'QAR': ('ريال قطري', 'ر.ق'),
        'BHD': ('دينار بحريني', 'د.ب'),
        'OMR': ('ريال عماني', 'ر.ع'),
        'JOD': ('دينار أردني', 'د.أ'),
    }
    
    if currency_code == 'OTHER':
        code = currency_data.get('custom_currency_code', 'XXX').upper()
        name = currency_data.get('custom_currency_name', 'Custom Currency')
        symbol = currency_data.get('custom_currency_symbol', code)
    else:
        code = currency_code
        name, symbol = currency_map.get(code, (code, code))
    
    # Mark all existing currencies as non-base
    Currency.objects.update(is_base=False)
    
    currency, _ = Currency.objects.update_or_create(
        code=code,
        defaults={
            'name': name,
            'name_ar': name,
            'symbol': symbol,
            'exchange_rate': Decimal('1.0'),
            'is_base': True,
            'is_active': True,
        }
    )
    
    # -------------------------------------------------------------------------
    # Step 2: Create Company
    # -------------------------------------------------------------------------
    company = Company.objects.create(
        name=company_data.get('name', 'شركتي'),
        name_ar=company_data.get('name_ar', ''),
        legal_name=company_data.get('legal_name', ''),
        email=company_data.get('email', 'info@example.com'),
        phone=company_data.get('phone', ''),
        tax_number=company_data.get('tax_number', ''),
        commercial_register=company_data.get('commercial_register', ''),
        address=company_data.get('address', ''),
        city=company_data.get('city', ''),
        country=company_data.get('country', 'المملكة العربية السعودية'),
        postal_code=company_data.get('postal_code', ''),
        base_currency=currency,
        fiscal_year_start=int(fiscal_year_data.get('fiscal_year_start', 1)),
        bank_name=payment_methods_data.get('bank_name', ''),
        bank_account=payment_methods_data.get('bank_account', ''),
        iban=payment_methods_data.get('iban', ''),
        created_by=request.user,
    )
    
    # Create HQ Branch
    Branch.objects.create(
        company=company,
        name='المقر الرئيسي',
        name_ar='المقر الرئيسي',
        code='HQ',
        address=company.address,
        city=company.city,
        country=company.country,
        is_headquarters=True,
        is_active=True,
        created_by=request.user,
    )
    
    # -------------------------------------------------------------------------
    # Step 3: Create Fiscal Year
    # -------------------------------------------------------------------------
    # Parse date strings back to date objects
    start_date_str = fiscal_year_data.get('start_date')
    end_date_str = fiscal_year_data.get('end_date')
    
    if isinstance(start_date_str, str):
        start_date = datetime.date.fromisoformat(start_date_str)
    else:
        start_date = start_date_str or datetime.date(timezone.now().year, 1, 1)
    
    if isinstance(end_date_str, str):
        end_date = datetime.date.fromisoformat(end_date_str)
    else:
        end_date = end_date_str or datetime.date(timezone.now().year, 12, 31)
    
    FiscalYear.objects.create(
        company=company,
        name=fiscal_year_data.get('fiscal_year_name', f'السنة المالية {timezone.now().year}'),
        start_date=start_date,
        end_date=end_date,
        is_current=True,
        created_by=request.user,
    )
    
    # -------------------------------------------------------------------------
    # Step 4: Create Tax Rates
    # -------------------------------------------------------------------------
    tax_preset = tax_data.get('tax_preset', 'sa_vat')
    
    tax_presets = {
        'sa_vat': ('ضريبة القيمة المضافة', Decimal('15.00')),
        'ae_vat': ('ضريبة القيمة المضافة', Decimal('5.00')),
        'eg_vat': ('ضريبة القيمة المضافة', Decimal('14.00')),
    }
    
    if tax_preset in tax_presets:
        name, rate = tax_presets[tax_preset]
        TaxRate.objects.create(
            company=company,
            name=name,
            name_ar=name,
            rate=rate,
            is_default=True,
            is_active=True,
        )
    elif tax_preset == 'custom':
        TaxRate.objects.create(
            company=company,
            name=tax_data.get('custom_tax_name', 'ضريبة'),
            name_ar=tax_data.get('custom_tax_name', 'ضريبة'),
            rate=tax_data.get('custom_tax_rate', Decimal('0')),
            is_default=True,
            is_active=True,
        )
    
    # Zero tax rate
    TaxRate.objects.create(
        company=company,
        name='بدون ضريبة',
        name_ar='بدون ضريبة',
        rate=Decimal('0'),
        is_default=False,
        is_active=True,
    )
    
    # -------------------------------------------------------------------------
    # Step 5: Create Chart of Accounts
    # -------------------------------------------------------------------------
    chart_preset = chart_data.get('chart_preset', 'travel_agency')
    accounts = create_chart_of_accounts(company, chart_preset, request.user)
    
    # -------------------------------------------------------------------------
    # Step 6: Create Payment Methods
    # -------------------------------------------------------------------------
    cash_account = accounts.get('1010')
    bank_account = accounts.get('1020')
    
    payment_methods = []
    if payment_methods_data.get('enable_cash', True):
        payment_methods.append(('نقداً', 'CASH', cash_account, False))
    if payment_methods_data.get('enable_bank_transfer', True):
        payment_methods.append(('تحويل بنكي', 'BANK', bank_account, True))
    if payment_methods_data.get('enable_credit_card', True):
        payment_methods.append(('بطاقة ائتمان', 'CC', bank_account, True))
    if payment_methods_data.get('enable_mada', True):
        payment_methods.append(('مدى', 'MADA', bank_account, True))
    if payment_methods_data.get('enable_stc_pay', False):
        payment_methods.append(('STC Pay', 'STCPAY', bank_account, True))
    if payment_methods_data.get('enable_apple_pay', False):
        payment_methods.append(('Apple Pay', 'APPLEPAY', bank_account, True))
    
    for name, code, account, requires_ref in payment_methods:
        PaymentMethod.objects.create(
            company=company,
            name=name,
            name_ar=name,
            code=code,
            account=account,
            requires_reference=requires_ref,
            is_active=True,
        )
    
    # -------------------------------------------------------------------------
    # Step 7: Create Expense Categories
    # -------------------------------------------------------------------------
    expense_account = accounts.get('6000')
    
    expense_categories = [
        ('مصاريف عامة', 'GEN', None),
        ('مصاريف السفر', 'TRV', 'GEN'),
        ('مصاريف التسويق', 'MKT', 'GEN'),
        ('مصاريف الرواتب', 'SAL', 'GEN'),
        ('مصاريف المكتب', 'OFF', 'GEN'),
    ]
    
    created_categories = {}
    for name, code, parent_code in expense_categories:
        parent = created_categories.get(parent_code)
        cat = ExpenseCategory.objects.create(
            company=company,
            name=name,
            name_ar=name,
            code=code,
            parent=parent,
            account=expense_account,
            is_active=True,
        )
        created_categories[code] = cat
    
    # -------------------------------------------------------------------------
    # Step 8: Create Sequences
    # -------------------------------------------------------------------------
    sequences = [
        (Sequence.SequenceType.INVOICE, 'INV-'),
        (Sequence.SequenceType.PAYMENT, 'PAY-'),
        (Sequence.SequenceType.EXPENSE, 'EXP-'),
        (Sequence.SequenceType.QUOTATION, 'QUO-'),
        (Sequence.SequenceType.PURCHASE_ORDER, 'PO-'),
        (Sequence.SequenceType.EMPLOYEE, 'EMP-'),
        (Sequence.SequenceType.CUSTOMER, 'CUS-'),
        (Sequence.SequenceType.SUPPLIER, 'SUP-'),
    ]
    
    for seq_type, prefix in sequences:
        Sequence.objects.create(
            company=company,
            sequence_type=seq_type,
            prefix=prefix,
            next_number=1,
            padding=5,
            reset_period='never',
        )
    
    # -------------------------------------------------------------------------
    # Step 9: Create System Settings
    # -------------------------------------------------------------------------
    settings = [
        ('setup.complete', 'true', SystemSetting.SettingType.BOOLEAN, 'system'),
        ('general.language', 'ar', SystemSetting.SettingType.STRING, 'general'),
        ('general.timezone', 'Asia/Riyadh', SystemSetting.SettingType.STRING, 'general'),
        ('finance.base_currency', currency.code, SystemSetting.SettingType.STRING, 'finance'),
        ('branding.company_name', company.name, SystemSetting.SettingType.STRING, 'branding'),
    ]
    
    for key, value, setting_type, category in settings:
        SystemSetting.objects.create(
            company=company,
            key=key,
            value=value,
            setting_type=setting_type,
            category=category,
            is_editable=key != 'setup.complete',
        )
    
    return company


def create_chart_of_accounts(company, preset, user):
    """Create chart of accounts based on preset."""
    
    # Standard chart used for all presets as base
    base_chart = [
        # Assets
        {'code': '1000', 'name': 'الأصول', 'type': Account.AccountType.ASSET},
        {'code': '1010', 'name': 'الصندوق', 'type': Account.AccountType.ASSET, 'parent': '1000'},
        {'code': '1020', 'name': 'البنك', 'type': Account.AccountType.ASSET, 'parent': '1000'},
        {'code': '1100', 'name': 'الذمم المدينة', 'type': Account.AccountType.ASSET, 'parent': '1000'},
        {'code': '1200', 'name': 'المخزون', 'type': Account.AccountType.ASSET, 'parent': '1000'},
        {'code': '1300', 'name': 'الأصول الثابتة', 'type': Account.AccountType.ASSET, 'parent': '1000'},
        
        # Liabilities
        {'code': '2000', 'name': 'الالتزامات', 'type': Account.AccountType.LIABILITY},
        {'code': '2100', 'name': 'الذمم الدائنة', 'type': Account.AccountType.LIABILITY, 'parent': '2000'},
        {'code': '2200', 'name': 'ضريبة القيمة المضافة المستحقة', 'type': Account.AccountType.LIABILITY, 'parent': '2000'},
        {'code': '2300', 'name': 'رواتب مستحقة', 'type': Account.AccountType.LIABILITY, 'parent': '2000'},
        
        # Equity
        {'code': '3000', 'name': 'حقوق الملكية', 'type': Account.AccountType.EQUITY},
        {'code': '3100', 'name': 'رأس المال', 'type': Account.AccountType.EQUITY, 'parent': '3000'},
        {'code': '3200', 'name': 'الأرباح المحتجزة', 'type': Account.AccountType.EQUITY, 'parent': '3000'},
        
        # Income
        {'code': '4000', 'name': 'الإيرادات', 'type': Account.AccountType.INCOME},
        {'code': '4100', 'name': 'إيرادات المبيعات', 'type': Account.AccountType.INCOME, 'parent': '4000'},
        {'code': '4200', 'name': 'إيرادات الخدمات', 'type': Account.AccountType.INCOME, 'parent': '4000'},
        
        # Expenses
        {'code': '5000', 'name': 'تكلفة المبيعات', 'type': Account.AccountType.EXPENSE},
        {'code': '6000', 'name': 'المصاريف التشغيلية', 'type': Account.AccountType.EXPENSE},
        {'code': '6100', 'name': 'مصاريف الرواتب', 'type': Account.AccountType.EXPENSE, 'parent': '6000'},
        {'code': '6200', 'name': 'مصاريف الإيجار', 'type': Account.AccountType.EXPENSE, 'parent': '6000'},
        {'code': '6300', 'name': 'مصاريف المرافق', 'type': Account.AccountType.EXPENSE, 'parent': '6000'},
        {'code': '6400', 'name': 'مصاريف التسويق', 'type': Account.AccountType.EXPENSE, 'parent': '6000'},
        {'code': '6500', 'name': 'مصاريف إدارية', 'type': Account.AccountType.EXPENSE, 'parent': '6000'},
    ]
    
    # Travel agency specific accounts
    travel_accounts = [
        {'code': '4110', 'name': 'إيرادات التذاكر', 'type': Account.AccountType.INCOME, 'parent': '4100'},
        {'code': '4120', 'name': 'إيرادات الفنادق', 'type': Account.AccountType.INCOME, 'parent': '4100'},
        {'code': '4130', 'name': 'إيرادات الرحلات السياحية', 'type': Account.AccountType.INCOME, 'parent': '4100'},
        {'code': '4140', 'name': 'إيرادات التأشيرات', 'type': Account.AccountType.INCOME, 'parent': '4100'},
        {'code': '4150', 'name': 'عمولات شركات الطيران', 'type': Account.AccountType.INCOME, 'parent': '4100'},
        {'code': '5100', 'name': 'تكلفة التذاكر', 'type': Account.AccountType.EXPENSE, 'parent': '5000'},
        {'code': '5200', 'name': 'تكلفة الفنادق', 'type': Account.AccountType.EXPENSE, 'parent': '5000'},
        {'code': '5300', 'name': 'تكلفة النقل', 'type': Account.AccountType.EXPENSE, 'parent': '5000'},
    ]
    
    if preset == 'travel_agency':
        base_chart.extend(travel_accounts)
    elif preset == 'services':
        base_chart.extend([
            {'code': '4210', 'name': 'إيرادات الاستشارات', 'type': Account.AccountType.INCOME, 'parent': '4200'},
            {'code': '4220', 'name': 'إيرادات الصيانة', 'type': Account.AccountType.INCOME, 'parent': '4200'},
        ])
    
    accounts = {}
    for item in base_chart:
        parent = accounts.get(item.get('parent'))
        acc = Account.objects.create(
            company=company,
            code=item['code'],
            name=item['name'],
            name_ar=item['name'],
            account_type=item['type'],
            parent=parent,
            is_system=True,
            is_active=True,
            created_by=user,
        )
        accounts[item['code']] = acc
    
    return accounts
