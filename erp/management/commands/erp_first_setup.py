import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from erp.models import (
    Account,
    Branch,
    Company,
    Currency,
    ExpenseCategory,
    FiscalYear,
    PaymentMethod,
    Sequence,
    SystemSetting,
    TaxRate,
)


class Command(BaseCommand):
    help = "Interactive first-time ERP setup with recommended defaults."

    def add_arguments(self, parser):
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help="Apply defaults without prompts.",
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
            help="ISO code for base currency (e.g., SAR, USD).",
        )

    def handle(self, *args, **options):
        non_interactive = options["non_interactive"]
        company_name = options["company_name"]
        company_email = options["company_email"]
        company_phone = options["company_phone"]
        company_country = options["company_country"]
        company_city = options["company_city"]
        base_currency_code = options["base_currency"].upper()

        if not non_interactive:
            self.stdout.write(self.style.WARNING("Running in interactive mode. Press Enter to accept defaults."))
            company_name = input(f"Company name [{company_name}]: ") or company_name
            company_email = input(f"Company email [{company_email}]: ") or company_email
            company_phone = input(f"Company phone [{company_phone}]: ") or company_phone
            company_country = input(f"Company country [{company_country}]: ") or company_country
            company_city = input(f"Company city [{company_city}]: ") or company_city
            base_currency_code = (input(f"Base currency code [{base_currency_code}]: ") or base_currency_code).upper()

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
            accounts = self._ensure_accounts(company)
            tax_rate = self._ensure_tax_rates(company)
            payment_methods = self._ensure_payment_methods(company, accounts)
            expense_categories = self._ensure_expense_categories(company, accounts)
            sequences = self._ensure_sequences(company)
            settings = self._ensure_system_settings(company, currency, company_email)

        self.stdout.write("\nSummary:")
        self.stdout.write(f"  Base currency: {currency.code} ({currency.name})")
        self.stdout.write(f"  Company: {company.name}")
        self.stdout.write(f"  Branch: {branch.name}")
        self.stdout.write(f"  Fiscal year: {fiscal_year.name}")
        self.stdout.write(f"  Accounts created/kept: {len(accounts)}")
        self.stdout.write(f"  Tax rates ensured: {len(tax_rate)}")
        self.stdout.write(f"  Payment methods ensured: {len(payment_methods)}")
        self.stdout.write(f"  Expense categories ensured: {len(expense_categories)}")
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

        defaults = {
            "code": code,
            "name": "Saudi Riyal" if code == "SAR" else code,
            "symbol": code,
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
        branch, _ = Branch.objects.get_or_create(
            company=company,
            name="Headquarters",
            defaults={
                "code": "HQ",
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
            name=f"FY{today.year}",
            start_date=start,
            end_date=end,
            is_current=True,
        )
        return fy

    def _ensure_accounts(self, company: Company):
        chart = [
            {"code": "1000", "name": "Assets", "type": Account.AccountType.ASSET},
            {"code": "1010", "name": "Cash", "type": Account.AccountType.ASSET, "parent": "1000"},
            {"code": "1020", "name": "Bank", "type": Account.AccountType.ASSET, "parent": "1000"},
            {"code": "1200", "name": "Accounts Receivable", "type": Account.AccountType.ASSET, "parent": "1000"},
            {"code": "2000", "name": "Liabilities", "type": Account.AccountType.LIABILITY},
            {"code": "2100", "name": "Accounts Payable", "type": Account.AccountType.LIABILITY, "parent": "2000"},
            {"code": "3000", "name": "Equity", "type": Account.AccountType.EQUITY},
            {"code": "4000", "name": "Sales Revenue", "type": Account.AccountType.INCOME},
            {"code": "5000", "name": "Cost of Sales", "type": Account.AccountType.EXPENSE},
            {"code": "6000", "name": "Operating Expenses", "type": Account.AccountType.EXPENSE},
            {"code": "6100", "name": "Travel Expenses", "type": Account.AccountType.EXPENSE, "parent": "6000"},
        ]

        accounts = {}
        for item in chart:
            parent = accounts.get(item.get("parent"))
            acc, created = Account.objects.get_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "account_type": item["type"],
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
            {"name": "Standard VAT", "rate": Decimal("15.00"), "is_default": True},
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

    def _ensure_payment_methods(self, company: Company, accounts):
        methods = [
            {"name": "Cash", "code": "CASH", "account": accounts.get("1010")},
            {"name": "Bank Transfer", "code": "BANK", "account": accounts.get("1020"), "requires_reference": True},
        ]
        created = []
        for item in methods:
            pm, _ = PaymentMethod.objects.get_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "account": item.get("account"),
                    "requires_reference": item.get("requires_reference", False),
                    "is_active": True,
                },
            )
            created.append(pm)
        return created

    def _ensure_expense_categories(self, company: Company, accounts):
        categories = [
            {"name": "General", "code": "GEN", "account": accounts.get("6000")},
            {"name": "Travel", "code": "TRV", "account": accounts.get("6100"), "parent": "GEN"},
        ]
        created = {}
        for item in categories:
            parent_obj = created.get(item.get("parent"))
            cat, _ = ExpenseCategory.objects.get_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "parent": parent_obj,
                    "account": item.get("account"),
                    "is_active": True,
                },
            )
            created[item["code"]] = cat
        return list(created.values())

    def _ensure_sequences(self, company: Company):
        sequences = [
            (Sequence.SequenceType.INVOICE, "INV-"),
            (Sequence.SequenceType.PAYMENT, "PAY-"),
            (Sequence.SequenceType.EXPENSE, "EXP-"),
            (Sequence.SequenceType.QUOTATION, "QUO-"),
            (Sequence.SequenceType.PURCHASE_ORDER, "PO-"),
            (Sequence.SequenceType.EMPLOYEE, "EMP-"),
            (Sequence.SequenceType.CUSTOMER, "CUS-"),
            (Sequence.SequenceType.SUPPLIER, "SUP-"),
        ]
        created = []
        for seq_type, prefix in sequences:
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
        settings = [
            {
                "key": "general.language",
                "value": "ar",
                "setting_type": SystemSetting.SettingType.STRING,
                "category": "general",
                "description": "Default UI language (ar/en).",
            },
            {
                "key": "general.timezone",
                "value": "Asia/Riyadh",
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
                "value": "Thank you for your business.",
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
