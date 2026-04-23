"""
ERP Setup Wizard Views

Multi-step wizard for first-time ERP system setup.
All user-facing strings go through Django i18n ({% trans %} in templates,
gettext_lazy in forms).  Default *data* (account names, categories …) is
stored in the database using the language active at setup time, with Arabic
always written to the ``name_ar`` field for bilingual reports.
"""

import datetime
import traceback
import logging
from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.utils.translation import get_language, gettext as _

from .models import (
    Currency,
    Company,
    FiscalYear,
    TaxRate,
    PaymentMethod,
    Account,
    Branch,
    Sequence,
    SystemSetting,
    ExpenseCategory,
    AssetCategory,
    InventoryValuationConfig,
)
from .setup_forms import (
    CurrencySetupForm,
    CompanySetupForm,
    FiscalYearSetupForm,
    TaxSetupForm,
    PaymentMethodsSetupForm,
    ChartOfAccountsSetupForm,
    SetupCompleteForm,
)
from .setup_defaults import (
    get_text,
    get_setup_steps,
    CURRENCY_MAP,
    get_chart_of_accounts,
    TAX_PRESETS,
    ZERO_TAX_NAME,
    PAYMENT_METHODS,
    EXPENSE_CATEGORIES,
    ASSET_CATEGORIES,
    SEQUENCES,
    HQ_BRANCH_NAME,
    get_default_fiscal_year_name,
    get_default_timezone,
    SETUP_SUCCESS_MSG,
    SETUP_ERROR_MSG,
)

# Import tenant_required decorator and use it as staff_member_required
from .decorators import tenant_required as staff_member_required


# =============================================================================
# Language helper
# =============================================================================


def _lang() -> str:
    """Return the current active language code (ar / en / id)."""
    return get_language() or "en"


# =============================================================================
# Setup Status Check
# =============================================================================


def is_setup_complete():
    """Check if ERP setup has been completed."""
    if not Company.objects.exists():
        return False
    if not Currency.objects.filter(is_base=True).exists():
        return False
    company = Company.objects.first()
    if company:
        setting = SystemSetting.objects.filter(company=company, key="setup.complete").first()
        if setting and setting.get_value():
            return True
    return False


def get_setup_progress(request):
    """Get current setup progress from session."""
    return request.session.get(
        "erp_setup",
        {
            "current_step": 1,
            "currency_data": {},
            "company_data": {},
            "fiscal_year_data": {},
            "tax_data": {},
            "payment_methods_data": {},
            "chart_data": {},
        },
    )


def save_setup_progress(request, data):
    """Save setup progress to session."""
    request.session["erp_setup"] = data
    request.session.modified = True


# =============================================================================
# Setup Wizard Views
# =============================================================================


@staff_member_required
def setup_wizard(request):
    """Main setup wizard dispatcher."""
    if is_setup_complete():
        return redirect("erp:dashboard")

    progress = get_setup_progress(request)
    current_step = progress.get("current_step", 1)

    step_views = {
        1: "erp:setup_step_currency",
        2: "erp:setup_step_company",
        3: "erp:setup_step_fiscal_year",
        4: "erp:setup_step_tax",
        5: "erp:setup_step_payment_methods",
        6: "erp:setup_step_chart",
        7: "erp:setup_step_review",
    }

    return redirect(step_views.get(current_step, "erp:setup_step_currency"))


def _render_step(request, template, form, step_number, progress, extra_ctx=None):
    """Shared renderer for wizard steps."""
    lang = _lang()
    ctx = {
        "form": form,
        "steps": get_setup_steps(lang),
        "current_step": step_number,
        "progress": progress,
        "LANGUAGE_CODE": lang,
    }
    if extra_ctx:
        ctx.update(extra_ctx)
    return render(request, template, ctx)


@staff_member_required
def setup_step_currency(request):
    """Step 1: Currency setup."""
    progress = get_setup_progress(request)

    if request.method == "POST":
        form = CurrencySetupForm(request.POST)
        if form.is_valid():
            progress["currency_data"] = form.cleaned_data
            progress["current_step"] = 2
            save_setup_progress(request, progress)
            return redirect("erp:setup_step_company")
    else:
        initial = progress.get("currency_data", {})
        form = CurrencySetupForm(initial=initial)

    return _render_step(request, "erp/setup/step_currency.html", form, 1, progress)


@staff_member_required
def setup_step_company(request):
    """Step 2: Company setup."""
    progress = get_setup_progress(request)

    if request.method == "POST":
        form = CompanySetupForm(request.POST)
        if form.is_valid():
            progress["company_data"] = form.cleaned_data
            progress["current_step"] = 3
            save_setup_progress(request, progress)
            return redirect("erp:setup_step_fiscal_year")
    else:
        initial = progress.get("company_data", {})
        form = CompanySetupForm(initial=initial)

    return _render_step(request, "erp/setup/step_company.html", form, 2, progress)


@staff_member_required
def setup_step_fiscal_year(request):
    """Step 3: Fiscal year setup."""
    progress = get_setup_progress(request)
    lang = _lang()

    today = timezone.now().date()
    default_start = datetime.date(today.year, 1, 1)
    default_end = datetime.date(today.year, 12, 31)

    if request.method == "POST":
        form = FiscalYearSetupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data.copy()
            if "start_date" in data and data["start_date"]:
                data["start_date"] = data["start_date"].isoformat()
            if "end_date" in data and data["end_date"]:
                data["end_date"] = data["end_date"].isoformat()
            progress["fiscal_year_data"] = data
            progress["current_step"] = 4
            save_setup_progress(request, progress)
            return redirect("erp:setup_step_tax")
    else:
        initial = progress.get(
            "fiscal_year_data",
            {
                "fiscal_year_name": get_default_fiscal_year_name(today.year, lang),
                "start_date": default_start.isoformat(),
                "end_date": default_end.isoformat(),
            },
        )
        form = FiscalYearSetupForm(initial=initial)

    return _render_step(request, "erp/setup/step_fiscal_year.html", form, 3, progress)


@staff_member_required
def setup_step_tax(request):
    """Step 4: Tax setup."""
    progress = get_setup_progress(request)

    if request.method == "POST":
        form = TaxSetupForm(request.POST)
        if form.is_valid():
            progress["tax_data"] = form.cleaned_data
            progress["current_step"] = 5
            save_setup_progress(request, progress)
            return redirect("erp:setup_step_payment_methods")
    else:
        initial = progress.get("tax_data", {})
        form = TaxSetupForm(initial=initial)

    return _render_step(request, "erp/setup/step_tax.html", form, 4, progress)


@staff_member_required
def setup_step_payment_methods(request):
    """Step 5: Payment methods setup."""
    progress = get_setup_progress(request)

    if request.method == "POST":
        form = PaymentMethodsSetupForm(request.POST)
        if form.is_valid():
            progress["payment_methods_data"] = form.cleaned_data
            progress["current_step"] = 6
            save_setup_progress(request, progress)
            return redirect("erp:setup_step_chart")
    else:
        initial = progress.get("payment_methods_data", {})
        form = PaymentMethodsSetupForm(initial=initial)

    return _render_step(request, "erp/setup/step_payment_methods.html", form, 5, progress)


@staff_member_required
def setup_step_chart(request):
    """Step 6: Chart of accounts setup."""
    progress = get_setup_progress(request)

    if request.method == "POST":
        form = ChartOfAccountsSetupForm(request.POST)
        if form.is_valid():
            progress["chart_data"] = form.cleaned_data
            progress["current_step"] = 7
            save_setup_progress(request, progress)
            return redirect("erp:setup_step_review")
    else:
        initial = progress.get("chart_data", {})
        form = ChartOfAccountsSetupForm(initial=initial)

    return _render_step(request, "erp/setup/step_chart.html", form, 6, progress)


@staff_member_required
def setup_step_review(request):
    """Step 7: Review and confirm."""
    progress = get_setup_progress(request)
    lang = _lang()

    if request.method == "POST":
        form = SetupCompleteForm(request.POST)
        if form.is_valid():
            try:
                execute_setup(request, progress)
                if "erp_setup" in request.session:
                    del request.session["erp_setup"]
                messages.success(request, get_text(SETUP_SUCCESS_MSG, lang))
                return redirect("erp:dashboard")
            except Exception as e:
                tb = traceback.format_exc()
                logging.getLogger("erp.setup").error("Setup error:\n%s", tb)
                print("=== SETUP ERROR TRACEBACK ===")
                print(tb)
                print("=== END TRACEBACK ===")
                messages.error(request, get_text(SETUP_ERROR_MSG, lang) + str(e))
    else:
        form = SetupCompleteForm()

    return _render_step(request, "erp/setup/step_review.html", form, 7, progress)


@staff_member_required
def setup_go_back(request, step):
    """Go back to a previous step."""
    progress = get_setup_progress(request)
    if 1 <= step <= 7:
        progress["current_step"] = step
        save_setup_progress(request, progress)

    step_views = {
        1: "erp:setup_step_currency",
        2: "erp:setup_step_company",
        3: "erp:setup_step_fiscal_year",
        4: "erp:setup_step_tax",
        5: "erp:setup_step_payment_methods",
        6: "erp:setup_step_chart",
        7: "erp:setup_step_review",
    }

    return redirect(step_views.get(step, "erp:setup_step_currency"))


# =============================================================================
# Execute Setup
# =============================================================================

# Map from short type strings used in setup_defaults to Account.AccountType
_ACCOUNT_TYPE_MAP = {
    "ASSET": Account.AccountType.ASSET,
    "LIABILITY": Account.AccountType.LIABILITY,
    "EQUITY": Account.AccountType.EQUITY,
    "INCOME": Account.AccountType.INCOME,
    "EXPENSE": Account.AccountType.EXPENSE,
}


@transaction.atomic
def execute_setup(request, progress):
    """Execute the actual setup based on collected data."""

    # Ensure the current user exists in the tenant database so that
    # FK references (created_by, etc.) satisfy DB constraints.
    from tenants.routers import get_current_db_alias
    from tenants.services.database_service import sync_user_to_tenant_db

    _db = get_current_db_alias()
    if _db and _db != "default":
        sync_user_to_tenant_db(request.user, _db)

    lang = _lang()  # language chosen by the user at setup time

    currency_data = progress.get("currency_data", {})
    company_data = progress.get("company_data", {})
    fiscal_year_data = progress.get("fiscal_year_data", {})
    tax_data = progress.get("tax_data", {})
    payment_methods_data = progress.get("payment_methods_data", {})
    chart_data = progress.get("chart_data", {})

    # -------------------------------------------------------------------------
    # Step 1: Create Currency
    # -------------------------------------------------------------------------
    currency_code = currency_data.get("base_currency", "SAR")

    if currency_code == "OTHER":
        code = currency_data.get("custom_currency_code", "XXX").upper()
        name = currency_data.get("custom_currency_name", "Custom Currency")
        name_ar = name
        symbol = currency_data.get("custom_currency_symbol", code)
    else:
        code = currency_code
        info = CURRENCY_MAP.get(code, {})
        if info:
            name = get_text(info["name"], lang)
            name_ar = get_text(info["name"], "ar")
            symbol = info["symbol"]
        else:
            name = code
            name_ar = code
            symbol = code

    Currency.objects.update(is_base=False)

    currency, _created = Currency.objects.update_or_create(
        code=code,
        defaults={
            "name": name,
            "name_ar": name_ar,
            "symbol": symbol,
            "exchange_rate": Decimal("1.0"),
            "is_base": True,
            "is_active": True,
        },
    )

    # -------------------------------------------------------------------------
    # Step 2: Create Company
    # -------------------------------------------------------------------------
    company = Company.objects.create(
        name=company_data.get("name", _("My Company")),
        name_ar=company_data.get("name_ar", ""),
        legal_name=company_data.get("legal_name", ""),
        email=company_data.get("email", "info@example.com"),
        phone=company_data.get("phone", ""),
        tax_number=company_data.get("tax_number", ""),
        commercial_register=company_data.get("commercial_register", ""),
        address=company_data.get("address", ""),
        city=company_data.get("city", ""),
        country=company_data.get("country", ""),
        postal_code=company_data.get("postal_code", ""),
        base_currency=currency,
        fiscal_year_start=int(fiscal_year_data.get("fiscal_year_start", 1)),
        bank_name=payment_methods_data.get("bank_name", ""),
        bank_account=payment_methods_data.get("bank_account", ""),
        iban=payment_methods_data.get("iban", ""),
        created_by=request.user,
    )

    # Create HQ Branch
    Branch.objects.create(
        company=company,
        name=get_text(HQ_BRANCH_NAME, lang),
        name_ar=get_text(HQ_BRANCH_NAME, "ar"),
        code="HQ",
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
    start_date_str = fiscal_year_data.get("start_date")
    end_date_str = fiscal_year_data.get("end_date")

    start_date = (
        datetime.date.fromisoformat(start_date_str)
        if isinstance(start_date_str, str)
        else start_date_str or datetime.date(timezone.now().year, 1, 1)
    )
    end_date = (
        datetime.date.fromisoformat(end_date_str)
        if isinstance(end_date_str, str)
        else end_date_str or datetime.date(timezone.now().year, 12, 31)
    )

    FiscalYear.objects.create(
        company=company,
        name=fiscal_year_data.get(
            "fiscal_year_name",
            get_default_fiscal_year_name(timezone.now().year, lang),
        ),
        start_date=start_date,
        end_date=end_date,
        is_current=True,
        created_by=request.user,
    )

    # -------------------------------------------------------------------------
    # Step 4: Create Tax Rates
    # -------------------------------------------------------------------------
    tax_preset = tax_data.get("tax_preset", "sa_vat")

    if tax_preset in TAX_PRESETS:
        preset_info = TAX_PRESETS[tax_preset]
        TaxRate.objects.create(
            company=company,
            name=get_text(preset_info["name"], lang),
            name_ar=get_text(preset_info["name"], "ar"),
            rate=preset_info["rate"],
            is_default=True,
            is_active=True,
        )
    elif tax_preset == "custom":
        custom_name = tax_data.get("custom_tax_name", _("Tax"))
        TaxRate.objects.create(
            company=company,
            name=custom_name,
            name_ar=custom_name,
            rate=tax_data.get("custom_tax_rate", Decimal("0")),
            is_default=True,
            is_active=True,
        )

    # Zero tax rate (always created)
    if tax_preset != "none":
        TaxRate.objects.create(
            company=company,
            name=get_text(ZERO_TAX_NAME, lang),
            name_ar=get_text(ZERO_TAX_NAME, "ar"),
            rate=Decimal("0"),
            is_default=False,
            is_active=True,
        )

    # -------------------------------------------------------------------------
    # Step 5: Create Chart of Accounts
    # -------------------------------------------------------------------------
    chart_preset = chart_data.get("chart_preset", "standard")
    accounts = create_chart_of_accounts(company, chart_preset, request.user, lang)

    # -------------------------------------------------------------------------
    # Step 6: Create Payment Methods
    # -------------------------------------------------------------------------
    bank_account_obj = accounts.get("1020")

    # Map form field names → PAYMENT_METHODS codes
    _pm_field_map = {
        "enable_cash": "CASH",
        "enable_bank_transfer": "BANK",
        "enable_credit_card": "CC",
        "enable_mada": "MADA",
        "enable_stc_pay": "STCPAY",
        "enable_apple_pay": "APPLEPAY",
    }

    for field_name, pm_code in _pm_field_map.items():
        if payment_methods_data.get(
            field_name, field_name in ("enable_cash", "enable_bank_transfer", "enable_credit_card", "enable_mada")
        ):
            pm_def = next((p for p in PAYMENT_METHODS if p["code"] == pm_code), None)
            if pm_def:
                acct = accounts.get(pm_def["account_code"], bank_account_obj)
                PaymentMethod.objects.create(
                    company=company,
                    name=get_text(pm_def["name"], lang),
                    name_ar=get_text(pm_def["name"], "ar"),
                    code=pm_code,
                    account=acct,
                    requires_reference=pm_def["requires_ref"],
                    is_active=True,
                )

    # -------------------------------------------------------------------------
    # Step 7: Create Expense Categories
    # -------------------------------------------------------------------------
    created_categories = {}
    for cat_def in EXPENSE_CATEGORIES:
        parent = created_categories.get(cat_def["parent"])
        cat = ExpenseCategory.objects.create(
            company=company,
            name=get_text(cat_def["name"], lang),
            name_ar=get_text(cat_def["name"], "ar"),
            code=cat_def["code"],
            parent=parent,
            account=accounts.get(cat_def["account_code"]),
            is_active=True,
        )
        created_categories[cat_def["code"]] = cat

    # -------------------------------------------------------------------------
    # Step 8: Create Asset Categories (professional defaults)
    # -------------------------------------------------------------------------
    for ac_def in ASSET_CATEGORIES:
        method_value = getattr(AssetCategory.DepreciationMethod, ac_def["method"], ac_def["method"])
        AssetCategory.objects.create(
            company=company,
            name=get_text(ac_def["name"], lang),
            code=ac_def["code"],
            depreciation_method=method_value,
            useful_life_months=ac_def["useful_life"],
            salvage_value_percent=ac_def["salvage_pct"],
            asset_account=accounts.get(ac_def["asset_acct"]),
            depreciation_expense_account=accounts.get(ac_def["depr_exp_acct"]),
            accumulated_depreciation_account=accounts.get(ac_def["accum_depr_acct"]),
            disposal_gain_account=accounts.get(ac_def["disposal_gain_acct"]),
            disposal_loss_account=accounts.get(ac_def["disposal_loss_acct"]),
            acquisition_source_account=accounts.get(ac_def["acq_source_acct"]),
            disposal_proceeds_account=accounts.get(ac_def["disposal_proceeds_acct"]),
            revaluation_surplus_account=accounts.get(ac_def["reval_surplus_acct"]),
            is_active=True,
        )

    # -------------------------------------------------------------------------
    # Step 9: Create Inventory Valuation Config
    # -------------------------------------------------------------------------
    InventoryValuationConfig.objects.get_or_create(
        company=company,
        defaults={
            "valuation_method": InventoryValuationConfig.ValuationMethod.WEIGHTED_AVG,
            "inventory_account": accounts.get("1200"),
            "cogs_account": accounts.get("5100"),
            "grni_account": accounts.get("1400"),
            "adjustment_account": accounts.get("6200"),
            "write_off_account": accounts.get("6300"),
        },
    )

    # -------------------------------------------------------------------------
    # Step 10: Create Sequences
    # -------------------------------------------------------------------------
    for seq_type_name, prefix in SEQUENCES:
        seq_type = getattr(Sequence.SequenceType, seq_type_name)
        Sequence.objects.create(
            company=company,
            sequence_type=seq_type,
            prefix=prefix,
            next_number=1,
            padding=5,
            reset_period="never",
        )

    # -------------------------------------------------------------------------
    # Step 11: Create System Settings
    # -------------------------------------------------------------------------
    tz = get_default_timezone(code)

    settings_list = [
        ("setup.complete", "true", SystemSetting.SettingType.BOOLEAN, "system"),
        ("general.language", lang, SystemSetting.SettingType.STRING, "general"),
        ("general.timezone", tz, SystemSetting.SettingType.STRING, "general"),
        ("finance.base_currency", currency.code, SystemSetting.SettingType.STRING, "finance"),
        (
            "finance.default_tax_rate",
            str(TAX_PRESETS.get(tax_preset, {}).get("rate", "0")),
            SystemSetting.SettingType.DECIMAL,
            "finance",
        ),
        ("finance.invoice_footer", _("Thank you for your business."), SystemSetting.SettingType.TEXT, "finance"),
        ("branding.company_name", company.name, SystemSetting.SettingType.STRING, "branding"),
        ("branding.company_address", company.address, SystemSetting.SettingType.TEXT, "branding"),
        ("email.default_sender", company.email, SystemSetting.SettingType.STRING, "email"),
        ("notifications.enable_email", "true", SystemSetting.SettingType.BOOLEAN, "notifications"),
    ]

    for key, value, setting_type, category in settings_list:
        SystemSetting.objects.create(
            company=company,
            key=key,
            value=value,
            setting_type=setting_type,
            category=category,
            is_editable=key != "setup.complete",
        )

    return company


# =============================================================================
# Chart of Accounts Builder
# =============================================================================


def create_chart_of_accounts(company, preset, user, lang="ar"):
    """Create chart of accounts based on preset, using the professional
    structure from erp_first_setup with multilingual account names."""

    chart_items = get_chart_of_accounts(preset)

    accounts = {}
    for item in chart_items:
        parent = accounts.get(item.get("parent"))
        acct_type = _ACCOUNT_TYPE_MAP[item["type"]]
        acc = Account.objects.create(
            company=company,
            code=item["code"],
            name=get_text(item["name"], lang),
            name_ar=get_text(item["name"], "ar"),
            account_type=acct_type,
            parent=parent,
            is_system=True,
            is_active=True,
            created_by=user,
        )
        accounts[item["code"]] = acc

    return accounts
