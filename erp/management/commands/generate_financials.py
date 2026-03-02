"""
Management command: generate_financials

Creates journal entries, expenses, and updates account balances from
existing imported data (invoices, payments, payroll).

This bridges the imported Olist/IBM HR data into the full accounting
system so it shows in the financial module:
  - Journal entries for every invoice  (DR Receivable / CR Revenue)
  - Journal entries for every payment  (DR Cash / CR Receivable)
  - Journal entries for payroll        (DR Salary Expense / CR Salary Payable)
  - Expense records with categories
  - Recalculated account balances

Usage:
    python manage.py generate_financials
    python manage.py generate_financials --tenant kuraimitttt
    python manage.py generate_financials --clear   # remove generated entries first
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from itertools import islice

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Account,
    Company,
    Currency,
    Expense,
    ExpenseCategory,
    FiscalYear,
    Invoice,
    JournalEntry,
    JournalEntryLine,
    Payment,
    PaymentMethod,
    Payroll,
)

# Prefix so we can identify generated records
JE_PREFIX = "JE-GEN-"
EXP_PREFIX = "EXP-GEN-"


class Command(BaseCommand):
    help = "Generate journal entries, expenses, and update account balances from imported data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant", type=str, default=None,
            help="Tenant DB name. Defaults to first active tenant.",
        )
        parser.add_argument(
            "--company-id", type=int, default=None,
            help="Company ID. Defaults to first company.",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete previously generated financial data before generating.",
        )
        parser.add_argument(
            "--batch-size", type=int, default=5000,
            help="Batch size for bulk operations (default: 5000).",
        )

    def handle(self, *args, **options):
        db_alias = self._activate_tenant(options["tenant"])
        with TenantDatabaseContext(db_alias):
            self._run(options, db_alias)

    def _activate_tenant(self, tenant_name):
        if tenant_name is None:
            tenant_db = TenantDatabase.objects.filter(status="active").first()
            if not tenant_db:
                raise CommandError("No active tenant. Pass --tenant <name>.")
            self.stdout.write(self.style.WARNING(
                f"No --tenant given; using first active tenant: {tenant_db.name}"
            ))
        else:
            try:
                tenant_db = TenantDatabase.objects.get(name=tenant_name)
            except TenantDatabase.DoesNotExist:
                avail = list(TenantDatabase.objects.filter(status="active")
                             .values_list("name", flat=True))
                raise CommandError(f"Tenant '{tenant_name}' not found. Available: {avail}")
        return add_tenant_database(tenant_db)

    # ------------------------------------------------------------------
    def _run(self, options, db_alias):
        self.db = db_alias
        self.batch_size = options["batch_size"]

        # Resolve company
        if options["company_id"]:
            company = Company.objects.using(self.db).filter(id=options["company_id"]).first()
            if not company:
                raise CommandError(f"Company id={options['company_id']} not found.")
        else:
            company = Company.objects.using(self.db).first()
            if not company:
                raise CommandError("No company found.")
        self.company = company
        self.stdout.write(self.style.HTTP_INFO(f"Company: {company.name} (id={company.id})"))

        # Load accounts
        self.acct_map = {
            a.code: a for a in Account.objects.using(self.db).filter(
                company=company, is_active=True
            )
        }
        self._validate_accounts()

        # Ensure fiscal years cover the data
        self._ensure_fiscal_years()

        # Ensure expense categories
        self._ensure_expense_categories()

        # Optional clear
        if options["clear"]:
            self._clear_generated()

        # Phase 1: Invoice journal entries
        self.stdout.write("\n[Phase 1] Invoice journal entries …")
        self._generate_invoice_journals()

        # Phase 2: Payment journal entries
        self.stdout.write("\n[Phase 2] Payment journal entries …")
        self._generate_payment_journals()

        # Phase 3: Payroll journal entries
        self.stdout.write("\n[Phase 3] Payroll journal entries …")
        self._generate_payroll_journals()

        # Phase 4: Expenses
        self.stdout.write("\n[Phase 4] Generating expense records …")
        self._generate_expenses()

        # Phase 5: Recalculate account balances
        self.stdout.write("\n[Phase 5] Recalculating account balances …")
        self._recalculate_balances()

        self.stdout.write(self.style.SUCCESS("\n✓ Financial data generation complete!"))
        self._print_summary()

    # ==================================================================
    # Validation
    # ==================================================================
    def _validate_accounts(self):
        required = ['1010', '1020', '1100', '4100', '5100',
                     '6100', '2300', '2310', '2320']
        missing = [c for c in required if c not in self.acct_map]
        if missing:
            raise CommandError(f"Missing required accounts: {missing}")

    # ==================================================================
    # Fiscal years
    # ==================================================================
    def _ensure_fiscal_years(self):
        """Create fiscal years covering all imported data."""
        # Determine required year range from actual data
        from django.db.models import Min, Max
        inv_range = Invoice.objects.using(self.db).aggregate(
            mn=Min('invoice_date'), mx=Max('invoice_date')
        )
        pay_range = Payment.objects.using(self.db).aggregate(
            mn=Min('payment_date'), mx=Max('payment_date')
        )
        prl_range = Payroll.objects.using(self.db).aggregate(
            mn=Min('period_start'), mx=Max('period_end')
        )
        all_dates = [v for v in [
            inv_range['mn'], inv_range['mx'],
            pay_range['mn'], pay_range['mx'],
            prl_range['mn'], prl_range['mx'],
        ] if v is not None]
        if all_dates:
            min_year = min(d.year for d in all_dates)
            max_year = max(d.year for d in all_dates)
        else:
            min_year, max_year = 2026, 2026

        existing = set(
            FiscalYear.objects.using(self.db)
            .filter(company=self.company)
            .values_list("name", flat=True)
        )
        new_fys = []
        for year in range(min_year, max_year + 1):
            name = f"FY{year}"
            if name not in existing:
                new_fys.append(FiscalYear(
                    company=self.company,
                    name=name,
                    start_date=date(year, 1, 1),
                    end_date=date(year, 12, 31),
                    is_current=(year == 2026),
                ))
        if new_fys:
            FiscalYear.objects.using(self.db).bulk_create(new_fys)
            names = [fy.name for fy in new_fys]
            self.stdout.write(f"  Created fiscal years: {', '.join(names)}")
        self.fy_map = {
            fy.start_date.year: fy
            for fy in FiscalYear.objects.using(self.db).filter(company=self.company)
        }

    # ==================================================================
    # Expense categories
    # ==================================================================
    def _ensure_expense_categories(self):
        categories = [
            ("Office Supplies", "OFF"),
            ("Travel & Transport", "TRV"),
            ("Rent & Utilities", "RNT"),
            ("Marketing & Advertising", "MKT"),
            ("IT & Software", "ITS"),
            ("Maintenance & Repairs", "MNT"),
            ("Professional Services", "PRO"),
            ("Insurance", "INS"),
            ("Miscellaneous", "MSC"),
        ]
        self.exp_cats = {}
        for name, code in categories:
            cat, _ = ExpenseCategory.objects.using(self.db).get_or_create(
                company=self.company, code=code,
                defaults={"name": name, "is_active": True},
            )
            self.exp_cats[code] = cat

    # ==================================================================
    # Clear
    # ==================================================================
    def _clear_generated(self):
        self.stdout.write(self.style.WARNING("Clearing previously generated financial data …"))
        cnt = JournalEntryLine.objects.using(self.db).filter(
            journal_entry__entry_number__startswith=JE_PREFIX
        ).delete()[0]
        self.stdout.write(f"  JournalEntryLines deleted: {cnt}")

        cnt = JournalEntry.all_objects.using(self.db).filter(
            entry_number__startswith=JE_PREFIX
        ).delete()[0]
        self.stdout.write(f"  JournalEntries deleted: {cnt}")

        cnt = Expense.all_objects.using(self.db).filter(
            expense_number__startswith=EXP_PREFIX
        ).delete()[0]
        self.stdout.write(f"  Expenses deleted: {cnt}")

        # Reset all account balances to zero
        Account.objects.using(self.db).filter(company=self.company).update(
            current_balance=Decimal("0")
        )
        self.stdout.write("  Account balances reset to 0.")

    # ==================================================================
    # Phase 1: Invoice → Journal Entries
    # DR 1100 Accounts Receivable  /  CR 4100 Sales Revenue
    # ==================================================================
    def _generate_invoice_journals(self):
        ar_acct = self.acct_map['1100']   # Accounts Receivable
        rev_acct = self.acct_map['4100']  # Sales Revenue
        cogs_acct = self.acct_map['5100']  # Cost of Goods Sold
        inv_acct = self.acct_map.get('1200')  # Inventory (optional)

        existing = set(
            JournalEntry.objects.using(self.db)
            .filter(entry_number__startswith=f"{JE_PREFIX}INV-")
            .values_list("entry_number", flat=True)
        )

        invoices = list(
            Invoice.objects.using(self.db)
            .filter(company=self.company, status__in=['paid', 'partial', 'overdue', 'sent'])
            .exclude(total_amount=0)
            .values('id', 'invoice_number', 'invoice_date', 'total_amount',
                    'subtotal', 'tax_amount', 'customer__name')
        )
        self.stdout.write(f"  Invoices to process: {len(invoices)}")

        je_objs = []
        je_lines_map = {}  # entry_number -> [lines]

        for inv in invoices:
            entry_num = f"{JE_PREFIX}INV-{inv['invoice_number'][-12:]}"
            if entry_num in existing:
                continue
            inv_date = inv['invoice_date']
            fy = self.fy_map.get(inv_date.year)
            amount = inv['total_amount']

            je = JournalEntry(
                company=self.company,
                entry_number=entry_num,
                entry_date=inv_date,
                entry_type='invoice',
                description=f"Invoice {inv['invoice_number']} - {inv['customer__name'] or ''}",
                reference=inv['invoice_number'],
                fiscal_year=fy,
                total_debit=amount,
                total_credit=amount,
                status='posted',
            )
            je_objs.append(je)

            lines = [
                # DR Accounts Receivable
                {
                    'account': ar_acct,
                    'description': f"Receivable - {inv['invoice_number']}",
                    'debit_amount': amount,
                    'credit_amount': Decimal('0'),
                },
                # CR Sales Revenue
                {
                    'account': rev_acct,
                    'description': f"Revenue - {inv['invoice_number']}",
                    'debit_amount': Decimal('0'),
                    'credit_amount': amount,
                },
            ]

            # Also record COGS (estimated at 60% of subtotal)
            cost = (inv['subtotal'] * Decimal('0.6')).quantize(Decimal('0.01'))
            if cost > 0 and inv_acct:
                lines.extend([
                    {
                        'account': cogs_acct,
                        'description': f"COGS - {inv['invoice_number']}",
                        'debit_amount': cost,
                        'credit_amount': Decimal('0'),
                    },
                    {
                        'account': inv_acct,
                        'description': f"Inventory reduction - {inv['invoice_number']}",
                        'debit_amount': Decimal('0'),
                        'credit_amount': cost,
                    },
                ])
                # Update totals
                je.total_debit += cost
                je.total_credit += cost

            je_lines_map[entry_num] = lines

        # Bulk create journal entries
        self._bulk_create_journals(je_objs, je_lines_map, "Invoice")

    # ==================================================================
    # Phase 2: Payment → Journal Entries
    # DR 1010/1020 Cash/Bank  /  CR 1100 Accounts Receivable
    # ==================================================================
    def _generate_payment_journals(self):
        ar_acct = self.acct_map['1100']
        cash_acct = self.acct_map['1010']
        bank_acct = self.acct_map['1020']

        existing = set(
            JournalEntry.objects.using(self.db)
            .filter(entry_number__startswith=f"{JE_PREFIX}PAY-")
            .values_list("entry_number", flat=True)
        )

        payments = list(
            Payment.objects.using(self.db)
            .filter(company=self.company)
            .exclude(amount=0)
            .values('id', 'payment_number', 'payment_date', 'amount',
                    'payment_method__code', 'customer__name')
        )
        self.stdout.write(f"  Payments to process: {len(payments)}")

        je_objs = []
        je_lines_map = {}

        for pay in payments:
            entry_num = f"{JE_PREFIX}PAY-{pay['payment_number'][-12:]}"
            if entry_num in existing:
                continue
            pay_date = pay['payment_date']
            fy = self.fy_map.get(pay_date.year)
            amount = pay['amount']

            # Cash vs Bank based on payment method
            method_code = pay.get('payment_method__code', 'CASH')
            if method_code in ('BANK', 'CC', 'DC', 'MADA'):
                debit_acct = bank_acct
            else:
                debit_acct = cash_acct

            je = JournalEntry(
                company=self.company,
                entry_number=entry_num,
                entry_date=pay_date,
                entry_type='payment',
                description=f"Payment {pay['payment_number']} - {pay['customer__name'] or ''}",
                reference=pay['payment_number'],
                fiscal_year=fy,
                total_debit=amount,
                total_credit=amount,
                status='posted',
            )
            je_objs.append(je)
            je_lines_map[entry_num] = [
                {
                    'account': debit_acct,
                    'description': f"Payment received - {pay['payment_number']}",
                    'debit_amount': amount,
                    'credit_amount': Decimal('0'),
                },
                {
                    'account': ar_acct,
                    'description': f"Receivable settled - {pay['payment_number']}",
                    'debit_amount': Decimal('0'),
                    'credit_amount': amount,
                },
            ]

        self._bulk_create_journals(je_objs, je_lines_map, "Payment")

    # ==================================================================
    # Phase 3: Payroll → Journal Entries
    # DR 6100 Salary Expense  /  CR 2300 Salary Payable
    # DR 6100 -> CR 2310 Social Insurance, CR 2320 Income Tax
    # ==================================================================
    def _generate_payroll_journals(self):
        sal_exp = self.acct_map['6100']  # Salary Expense
        sal_pay = self.acct_map['2300']  # Salary Payable
        si_pay = self.acct_map['2310']   # Social Insurance Payable
        tax_pay = self.acct_map['2320']  # Income Tax Payable
        cash_acct = self.acct_map['1010']

        existing = set(
            JournalEntry.objects.using(self.db)
            .filter(entry_number__startswith=f"{JE_PREFIX}PRL-")
            .values_list("entry_number", flat=True)
        )

        payrolls = list(
            Payroll.objects.using(self.db)
            .filter(employee__company=self.company, status='paid')
            .values('id', 'employee__employee_id', 'employee__first_name',
                    'employee__last_name', 'period_start', 'period_end',
                    'gross_salary', 'net_salary', 'social_insurance',
                    'tax_deduction', 'total_deductions', 'payment_date')
        )
        self.stdout.write(f"  Payrolls to process: {len(payrolls)}")

        je_objs = []
        je_lines_map = {}

        for pr in payrolls:
            emp_id = pr['employee__employee_id']
            entry_num = f"{JE_PREFIX}PRL-{emp_id}-{pr['period_start'].strftime('%Y%m')}"
            if entry_num in existing:
                continue

            entry_date = pr['payment_date'] or pr['period_end']
            fy = self.fy_map.get(entry_date.year)
            gross = pr['gross_salary']
            net = pr['net_salary']
            si = pr['social_insurance']
            tax = pr['tax_deduction']
            emp_name = f"{pr['employee__first_name']} {pr['employee__last_name']}"

            total_debit = gross
            total_credit = gross

            je = JournalEntry(
                company=self.company,
                entry_number=entry_num,
                entry_date=entry_date,
                entry_type='payroll',
                description=f"Payroll {pr['period_start']} - {emp_name}",
                reference=emp_id,
                fiscal_year=fy,
                total_debit=total_debit,
                total_credit=total_credit,
                status='posted',
            )
            je_objs.append(je)

            lines = [
                # DR Salary Expense (gross)
                {
                    'account': sal_exp,
                    'description': f"Salary expense - {emp_name}",
                    'debit_amount': gross,
                    'credit_amount': Decimal('0'),
                },
                # CR Net Salary → Cash/Bank (what employee gets)
                {
                    'account': cash_acct,
                    'description': f"Net salary paid - {emp_name}",
                    'debit_amount': Decimal('0'),
                    'credit_amount': net,
                },
            ]
            # CR Social Insurance Payable
            if si > 0:
                lines.append({
                    'account': si_pay,
                    'description': f"Social insurance - {emp_name}",
                    'debit_amount': Decimal('0'),
                    'credit_amount': si,
                })
            # CR Income Tax Payable
            if tax > 0:
                lines.append({
                    'account': tax_pay,
                    'description': f"Income tax - {emp_name}",
                    'debit_amount': Decimal('0'),
                    'credit_amount': tax,
                })
            # If there are other deductions, put them in Salary Payable
            other_ded = gross - net - si - tax
            if other_ded > 0:
                lines.append({
                    'account': sal_pay,
                    'description': f"Other deductions - {emp_name}",
                    'debit_amount': Decimal('0'),
                    'credit_amount': other_ded,
                })

            je_lines_map[entry_num] = lines

        self._bulk_create_journals(je_objs, je_lines_map, "Payroll")

    # ==================================================================
    # Phase 4: Expenses
    # ==================================================================
    def _generate_expenses(self):
        existing_count = Expense.objects.using(self.db).filter(
            expense_number__startswith=EXP_PREFIX
        ).count()
        if existing_count > 0:
            self.stdout.write(f"  Skipping — {existing_count} expense records already exist.")
            return

        currency = self.company.base_currency
        if not currency:
            currency = Currency.objects.using(self.db).filter(code='USD').first()

        # Get a payment method
        pm = PaymentMethod.objects.using(self.db).filter(
            company=self.company, code='BANK'
        ).first()
        if not pm:
            pm = PaymentMethod.objects.using(self.db).filter(
                company=self.company
            ).first()

        # Generate monthly expenses for 2017-2018 (Olist period) + 2024 (payroll period)
        expense_templates = [
            ("OFF", "Office supplies", 200, 800),
            ("RNT", "Monthly rent", 2000, 5000),
            ("RNT", "Electricity & water", 300, 1200),
            ("TRV", "Employee travel", 500, 2000),
            ("MKT", "Marketing campaign", 1000, 5000),
            ("ITS", "Software subscriptions", 200, 1500),
            ("MNT", "Equipment maintenance", 100, 800),
            ("INS", "Business insurance", 500, 2000),
            ("PRO", "Consulting fees", 1000, 5000),
            ("MSC", "Miscellaneous expenses", 50, 500),
        ]
        account_map = {
            "OFF": self.acct_map.get('6700'),  # Office Supplies
            "RNT": self.acct_map.get('6600'),  # Rent & Utilities
            "TRV": self.acct_map.get('6500'),  # Travel
            "MKT": self.acct_map.get('6700'),  # General
            "ITS": self.acct_map.get('6700'),  # General
            "MNT": self.acct_map.get('6700'),  # General
            "INS": self.acct_map.get('6700'),  # General
            "PRO": self.acct_map.get('6700'),  # General
            "MSC": self.acct_map.get('6700'),  # General
        }

        # Generate monthly expenses covering the same period as invoices & payroll
        from django.db.models import Min, Max
        inv_range = Invoice.objects.using(self.db).aggregate(
            mn=Min('invoice_date'), mx=Max('invoice_date')
        )
        start_date = inv_range['mn'] or date(2026, 1, 1)
        end_date = inv_range['mx'] or date(2026, 12, 31)
        # Cap to current date + 1 month so expenses don't extend far into the future
        cap_date = date(2026, 3, 31)  # approx current period
        if end_date > cap_date:
            end_date = cap_date

        months = []
        d = date(start_date.year, start_date.month, 1)
        while d <= end_date:
            months.append(d)
            if d.month == 12:
                d = date(d.year + 1, 1, 1)
            else:
                d = date(d.year, d.month + 1, 1)

        new_expenses = []
        je_objs = []
        je_lines_map = {}
        counter = 0

        for month_date in months:
            for cat_code, desc, min_amt, max_amt in expense_templates:
                counter += 1
                amt = Decimal(str(random.randint(min_amt, max_amt)))
                exp_date = month_date + timedelta(days=random.randint(0, 27))
                exp_num = f"{EXP_PREFIX}{counter:06d}"

                new_expenses.append(Expense(
                    company=self.company,
                    expense_number=exp_num,
                    expense_date=exp_date,
                    category=self.exp_cats.get(cat_code),
                    description=f"{desc} - {exp_date.strftime('%B %Y')}",
                    currency=currency,
                    amount=amt,
                    tax_amount=Decimal('0'),
                    total_amount=amt,
                    payment_method=pm,
                    account=account_map.get(cat_code),
                    status='paid',
                ))

                # Journal entry for the expense
                entry_num = f"{JE_PREFIX}EXP-{counter:06d}"
                fy = self.fy_map.get(exp_date.year)
                exp_acct = account_map.get(cat_code) or self.acct_map.get('6700')
                cash_acct = self.acct_map['1010']

                je = JournalEntry(
                    company=self.company,
                    entry_number=entry_num,
                    entry_date=exp_date,
                    entry_type='expense',
                    description=f"Expense: {desc} - {exp_date.strftime('%B %Y')}",
                    reference=exp_num,
                    fiscal_year=fy,
                    total_debit=amt,
                    total_credit=amt,
                    status='posted',
                )
                je_objs.append(je)
                je_lines_map[entry_num] = [
                    {
                        'account': exp_acct,
                        'description': desc,
                        'debit_amount': amt,
                        'credit_amount': Decimal('0'),
                    },
                    {
                        'account': cash_acct,
                        'description': f"Cash paid - {desc}",
                        'debit_amount': Decimal('0'),
                        'credit_amount': amt,
                    },
                ]

        if new_expenses:
            Expense.objects.using(self.db).bulk_create(new_expenses, batch_size=2000)
            self.stdout.write(self.style.SUCCESS(f"  Expenses created: {len(new_expenses)}"))

        self._bulk_create_journals(je_objs, je_lines_map, "Expense")

    # ==================================================================
    # Phase 5: Recalculate balances
    # ==================================================================
    def _recalculate_balances(self):
        accounts = Account.objects.using(self.db).filter(
            company=self.company, is_active=True
        )
        updated = 0
        for acct in accounts:
            old_bal = acct.current_balance
            acct.recalculate_balance(db_alias=self.db)
            if acct.current_balance != old_bal:
                acct.save(update_fields=['current_balance'])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"  Accounts updated: {updated}"))

    # ==================================================================
    # Helpers
    # ==================================================================
    def _bulk_create_journals(self, je_objs, je_lines_map, label):
        """Bulk create journal entries + lines, splitting into batches."""
        if not je_objs:
            self.stdout.write(f"  No new {label} journal entries to create.")
            return

        total_je = len(je_objs)
        total_lines = 0

        # Process in batches
        for batch_start in range(0, len(je_objs), self.batch_size):
            batch = je_objs[batch_start:batch_start + self.batch_size]
            JournalEntry.objects.using(self.db).bulk_create(batch, batch_size=self.batch_size)

        # Refresh to get PKs
        created_entries = {
            je.entry_number: je
            for je in JournalEntry.objects.using(self.db).filter(
                entry_number__in=list(je_lines_map.keys())
            )
        }

        # Create lines
        all_lines = []
        for entry_num, lines_data in je_lines_map.items():
            je = created_entries.get(entry_num)
            if not je:
                continue
            for ld in lines_data:
                all_lines.append(JournalEntryLine(
                    journal_entry=je,
                    account=ld['account'],
                    description=ld['description'],
                    debit_amount=ld['debit_amount'],
                    credit_amount=ld['credit_amount'],
                ))

        if all_lines:
            # Bulk create lines WITHOUT triggering save() signal
            # (which would recalculate JE totals per line — too slow)
            total_lines = len(all_lines)
            for batch_start in range(0, len(all_lines), self.batch_size):
                batch = all_lines[batch_start:batch_start + self.batch_size]
                JournalEntryLine.objects.using(self.db).bulk_create(
                    batch, batch_size=self.batch_size
                )

        self.stdout.write(self.style.SUCCESS(
            f"  {label} journal entries: {total_je}, lines: {total_lines}"
        ))

    # ==================================================================
    # Summary
    # ==================================================================
    def _print_summary(self):
        self.stdout.write(self.style.HTTP_INFO("\n--- Financial Summary ---"))

        je_total = JournalEntry.objects.using(self.db).filter(
            entry_number__startswith=JE_PREFIX
        ).count()
        je_lines = JournalEntryLine.objects.using(self.db).filter(
            journal_entry__entry_number__startswith=JE_PREFIX
        ).count()
        exp_total = Expense.objects.using(self.db).filter(
            expense_number__startswith=EXP_PREFIX
        ).count()
        self.stdout.write(f"  Journal Entries: {je_total}")
        self.stdout.write(f"  Journal Lines: {je_lines}")
        self.stdout.write(f"  Expenses: {exp_total}")

        self.stdout.write("\n  Account Balances:")
        for acct in Account.objects.using(self.db).filter(
            company=self.company, is_active=True
        ).exclude(current_balance=0).order_by('code'):
            self.stdout.write(f"    {acct.code} {acct.name}: {acct.current_balance:,.2f}")
