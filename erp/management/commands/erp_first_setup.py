import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from erp.models import (
    Account,
    AssetCategory,
    Branch,
    Company,
    Currency,
    ExpenseCategory,
    FiscalYear,
    InventoryValuationConfig,
    PaymentMethod,
    Sequence,
    SystemSetting,
    TaxRate,
)
from erp.setup_defaults import (
    ASSET_CATEGORIES,
    CURRENCY_MAP,
    EXPENSE_CATEGORIES,
    HQ_BRANCH_NAME,
    PAYMENT_METHODS,
    SEQUENCES,
    get_chart_of_accounts,
    get_default_fiscal_year_name,
    get_default_timezone,
    get_text,
)

# Map string type aliases to Account.AccountType enum values
_ACCOUNT_TYPE_MAP = {
    'ASSET': Account.AccountType.ASSET,
    'LIABILITY': Account.AccountType.LIABILITY,
    'EQUITY': Account.AccountType.EQUITY,
    'INCOME': Account.AccountType.INCOME,
    'EXPENSE': Account.AccountType.EXPENSE,
}


class Command(BaseCommand):
    help = "Interactive first-time ERP setup with recommended defaults."

    def add_arguments(self, parser):
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help="Apply defaults without prompts.",
        )
        parser.add_argument(
            "--language",
            default="en",
            choices=["ar", "en", "id"],
            help="Language for default data names (ar/en/id). Default: en.",
        )
        parser.add_argument(
            "--company-name",
            default="Tourista ERP",
            help="Company display name.",
        )
        parser.add_argument(
            "--company-email",
            default="info@example.com",
            help="Primary company email.",
        )
        parser.add_argument(
            "--company-phone",
            default="0000000000",
            help="Primary company phone.",
        )
        parser.add_argument(
            "--company-country",
            default="Saudi Arabia",
            help="Company country.",
        )
        parser.add_argument(
            "--company-city",
            default="Riyadh",
            help="Company city.",
        )
        parser.add_argument(
            "--base-currency",
            default="SAR",
            help="ISO code for base currency (e.g., SAR, USD, IDR).",
        )
        parser.add_argument(
            "--chart-preset",
            default="standard",
            choices=["standard", "travel_agency", "services", "minimal"],
            help="Chart of accounts preset. Default: standard.",
        )

    def handle(self, *args, **options):
        non_interactive = options["non_interactive"]
        self.lang = options["language"]
        company_name = options["company_name"]
        company_email = options["company_email"]
        company_phone = options["company_phone"]
        company_country = options["company_country"]
        company_city = options["company_city"]
        base_currency_code = options["base_currency"].upper()
        chart_preset = options["chart_preset"]

        if not non_interactive:
            self.stdout.write(self.style.WARNING("Running in interactive mode. Press Enter to accept defaults."))
            self.lang = input(f"Data language (ar/en/id) [{self.lang}]: ") or self.lang
            company_name = input(f"Company name [{company_name}]: ") or company_name
            company_email = input(f"Company email [{company_email}]: ") or company_email
            company_phone = input(f"Company phone [{company_phone}]: ") or company_phone
            company_country = input(f"Company country [{company_country}]: ") or company_country
            company_city = input(f"Company city [{company_city}]: ") or company_city
            base_currency_code = (input(f"Base currency code [{base_currency_code}]: ") or base_currency_code).upper()
            chart_preset = input(f"Chart preset (standard/travel_agency/services/minimal) [{chart_preset}]: ") or chart_preset

        with transaction.atomic():
            currency = self._ensure_base_currency(code=base_currency_code)
            company = self._ensure_company(
                name=company_name,
                email=company_email,
                phone=company_phone,
                country=company_country,
                city=company_city,
                currency=currency,
            )
            branch = self._ensure_branch(company)
            fiscal_year = self._ensure_fiscal_year(company)
            accounts = self._ensure_accounts(company, chart_preset)
            tax_rate = self._ensure_tax_rates(company)
            payment_methods = self._ensure_payment_methods(company, accounts)
            expense_categories = self._ensure_expense_categories(company, accounts)
            asset_categories = self._ensure_asset_categories(company, accounts)
            inventory_config = self._ensure_inventory_config(company, accounts)
            sequences = self._ensure_sequences(company)
            settings = self._ensure_system_settings(company, currency, company_email)

        self.stdout.write("\nSummary:")
        self.stdout.write(f"  Language: {self.lang}")
        self.stdout.write(f"  Base currency: {currency.code} ({currency.name})")
        self.stdout.write(f"  Company: {company.name}")
        self.stdout.write(f"  Branch: {branch.name}")
        self.stdout.write(f"  Fiscal year: {fiscal_year.name}")
        self.stdout.write(f"  Chart preset: {chart_preset}")
        self.stdout.write(f"  Accounts created/kept: {len(accounts)}")
        self.stdout.write(f"  Tax rates ensured: {len(tax_rate)}")
        self.stdout.write(f"  Payment methods ensured: {len(payment_methods)}")
        self.stdout.write(f"  Expense categories ensured: {len(expense_categories)}")
        self.stdout.write(f"  Asset categories ensured: {len(asset_categories)}")
        self.stdout.write(f"  Inventory valuation config: {'OK' if inventory_config else 'skipped'}")
        self.stdout.write(f"  Sequences ensured: {len(sequences)}")
        self.stdout.write(f"  System settings ensured: {len(settings)}")
        self.stdout.write(self.style.SUCCESS("First-time ERP defaults are in place."))

    # ------------------------------------------------------------------
    # Ensurers
    # ------------------------------------------------------------------
    def _ensure_base_currency(self, code: str) -> Currency:
        currency = Currency.objects.filter(is_base=True).first()
        if currency:
            return currency

        info = CURRENCY_MAP.get(code, {})
        name = get_text(info.get('name', code), self.lang) if info else code
        name_ar = get_text(info.get('name', code), 'ar') if info else code
        symbol = info.get('symbol', code) if info else code

        defaults = {
            "code": code,
            "name": name,
            "name_ar": name_ar,
            "symbol": symbol,
            "exchange_rate": Decimal("1.0"),
            "is_base": True,
            "is_active": True,
        }
        currency, created = Currency.objects.get_or_create(code=code, defaults=defaults)
        if not currency.is_base:
            currency.is_base = True
            currency.save(update_fields=["is_base"])
        return currency

    def _ensure_company(self, name, email, phone, country, city, currency) -> Company:
        company = Company.objects.order_by("id").first()
        if company:
            return company

        address = "Set your address in Company settings"
        return Company.objects.create(
            name=name,
            email=email,
            phone=phone,
            address=address,
            city=city,
            country=country,
            base_currency=currency,
            fiscal_year_start=1,
        )

    def _ensure_branch(self, company: Company) -> Branch:
        branch = company.branches.filter(is_headquarters=True).first()
        if branch:
            return branch
        hq_name = get_text(HQ_BRANCH_NAME, self.lang)
        branch, _ = Branch.objects.get_or_create(
            company=company,
            name=hq_name,
            defaults={
                "code": "HQ",
                "name_ar": get_text(HQ_BRANCH_NAME, 'ar'),
                "address": "Set your HQ address",
                "city": company.city,
                "country": company.country,
                "is_headquarters": True,
                "is_active": True,
            },
        )
        return branch

    def _ensure_fiscal_year(self, company: Company) -> FiscalYear:
        fy = company.fiscal_years.filter(is_current=True).first()
        if fy:
            return fy
        today = timezone.now().date()
        start = datetime.date(today.year, 1, 1)
        end = datetime.date(today.year, 12, 31)
        fy = FiscalYear.objects.create(
            company=company,
            name=get_default_fiscal_year_name(today.year, self.lang),
            start_date=start,
            end_date=end,
            is_current=True,
        )
        return fy

    def _ensure_accounts(self, company: Company, chart_preset: str = 'standard'):
        chart = get_chart_of_accounts(chart_preset)

        accounts: dict[str, Account] = {}
        for item in chart:
            parent = accounts.get(item.get("parent"))
            name = get_text(item['name'], self.lang)
            name_ar = get_text(item['name'], 'ar')
            acct_type = _ACCOUNT_TYPE_MAP[item['type']]
            acc, created = Account.objects.get_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": name,
                    "name_ar": name_ar,
                    "account_type": acct_type,
                    "parent": parent,
                    "is_system": True,
                },
            )
            if not acc.parent and parent:
                acc.parent = parent
                acc.save(update_fields=["parent"])
            accounts[item["code"]] = acc
        return accounts

    def _ensure_tax_rates(self, company: Company):
        rates = [
            {"name": get_text({'ar': 'ضريبة القيمة المضافة', 'en': 'Standard VAT', 'id': 'PPN Standar'}, self.lang),
             "name_ar": 'ضريبة القيمة المضافة',
             "rate": Decimal("15.00"), "is_default": True},
        ]
        created = []
        for item in rates:
            tax, _ = TaxRate.objects.get_or_create(
                company=company,
                name=item["name"],
                defaults={
                    "rate": item["rate"],
                    "is_default": item.get("is_default", False),
                    "is_active": True,
                },
            )
            created.append(tax)
        return created

    def _ensure_payment_methods(self, company: Company, accounts: dict[str, Account]):
        created = []
        for item in PAYMENT_METHODS:
            pm, _ = PaymentMethod.objects.get_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": get_text(item['name'], self.lang),
                    "name_ar": get_text(item['name'], 'ar'),
                    "account": accounts.get(item['account_code']),
                    "requires_reference": item.get("requires_ref", False),
                    "is_active": True,
                },
            )
            created.append(pm)
        return created

    def _ensure_expense_categories(self, company: Company, accounts: dict[str, Account]):
        created: dict[str, ExpenseCategory] = {}
        for item in EXPENSE_CATEGORIES:
            parent_obj = created.get(item.get("parent"))
            cat, _ = ExpenseCategory.objects.get_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": get_text(item['name'], self.lang),
                    "name_ar": get_text(item['name'], 'ar'),
                    "parent": parent_obj,
                    "account": accounts.get(item['account_code']),
                    "is_active": True,
                },
            )
            created[item["code"]] = cat
        return list(created.values())

    def _ensure_asset_categories(self, company: Company, accounts: dict[str, Account]):
        """Create recommended fixed-asset categories with proper GL mappings."""
        created = []
        for item in ASSET_CATEGORIES:
            method_map = {
                'STRAIGHT_LINE': AssetCategory.DepreciationMethod.STRAIGHT_LINE,
                'DECLINING_BALANCE': AssetCategory.DepreciationMethod.DECLINING_BALANCE,
            }
            cat, _ = AssetCategory.objects.get_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": get_text(item['name'], self.lang),
                    "name_ar": get_text(item['name'], 'ar'),
                    "depreciation_method": method_map[item['method']],
                    "useful_life_months": item["useful_life"],
                    "salvage_value_percent": item["salvage_pct"],
                    "asset_account": accounts.get(item["asset_acct"]),
                    "depreciation_expense_account": accounts.get(item["depr_exp_acct"]),
                    "accumulated_depreciation_account": accounts.get(item["accum_depr_acct"]),
                    "disposal_gain_account": accounts.get(item["disposal_gain_acct"]),
                    "disposal_loss_account": accounts.get(item["disposal_loss_acct"]),
                    "acquisition_source_account": accounts.get(item["acq_source_acct"]),
                    "disposal_proceeds_account": accounts.get(item["disposal_proceeds_acct"]),
                    "revaluation_surplus_account": accounts.get(item["reval_surplus_acct"]),
                    "is_active": True,
                },
            )
            created.append(cat)
        return created

    def _ensure_inventory_config(self, company: Company, accounts):
        """Create default InventoryValuationConfig with recommended GL accounts."""
        config, _ = InventoryValuationConfig.objects.get_or_create(
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
        return config

    def _ensure_sequences(self, company: Company):
        created = []
        for seq_type_name, prefix in SEQUENCES:
            seq_type = getattr(Sequence.SequenceType, seq_type_name)
            seq, _ = Sequence.objects.get_or_create(
                company=company,
                sequence_type=seq_type,
                defaults={
                    "prefix": prefix,
                    "next_number": 1,
                    "padding": 5,
                    "reset_period": "never",
                },
            )
            created.append(seq)
        return created

    def _ensure_system_settings(self, company: Company, currency: Currency, company_email: str):
        tz = get_default_timezone(currency.code)
        settings = [
            {
                "key": "general.language",
                "value": self.lang,
                "setting_type": SystemSetting.SettingType.STRING,
                "category": "general",
                "description": "Default UI language (ar/en/id).",
            },
            {
                "key": "general.timezone",
                "value": tz,
                "setting_type": SystemSetting.SettingType.STRING,
                "category": "general",
                "description": "Default timezone for the company.",
            },
            {
                "key": "finance.base_currency",
                "value": currency.code,
                "setting_type": SystemSetting.SettingType.STRING,
                "category": "finance",
                "description": "Base currency code.",
            },
            {
                "key": "finance.default_tax_rate",
                "value": "15.00",
                "setting_type": SystemSetting.SettingType.DECIMAL,
                "category": "finance",
                "description": "Default VAT percentage.",
            },
            {
                "key": "finance.invoice_footer",
                "value": get_text({
                    'ar': 'شكراً لتعاملكم معنا.',
                    'en': 'Thank you for your business.',
                    'id': 'Terima kasih atas kerja samanya.',
                }, self.lang),
                "setting_type": SystemSetting.SettingType.TEXT,
                "category": "finance",
                "description": "Footer note printed on invoices.",
            },
            {
                "key": "branding.company_name",
                "value": company.name,
                "setting_type": SystemSetting.SettingType.STRING,
                "category": "branding",
                "description": "Display name for documents and emails.",
            },
            {
                "key": "branding.company_address",
                "value": company.address,
                "setting_type": SystemSetting.SettingType.TEXT,
                "category": "branding",
                "description": "Company address for documents.",
            },
            {
                "key": "email.default_sender",
                "value": company_email,
                "setting_type": SystemSetting.SettingType.STRING,
                "category": "email",
                "description": "Default from email for notifications.",
            },
            {
                "key": "notifications.enable_email",
                "value": "true",
                "setting_type": SystemSetting.SettingType.BOOLEAN,
                "category": "notifications",
                "description": "Send email notifications by default.",
            },
            {
                "key": "general.setup_language",
                "value": self.lang,
                "setting_type": SystemSetting.SettingType.STRING,
                "category": "general",
                "description": "Language used during initial setup.",
            },
        ]

        created = []
        for item in settings:
            setting, _ = SystemSetting.objects.get_or_create(
                company=company,
                key=item["key"],
                defaults={
                    "value": item["value"],
                    "setting_type": item.get("setting_type", SystemSetting.SettingType.STRING),
                    "category": item.get("category", "general"),
                    "description": item.get("description", ""),
                    "is_editable": True,
                },
            )
            created.append(setting)
        return created
