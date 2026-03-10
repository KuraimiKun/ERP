"""
Management command: import_expenses

Imports the synthetic expense claims dataset into the ERP system
for ML model testing (Expense Anomaly Detection).

Expected CSV file in datasets/:
  - expense_claims_dataset.csv   (~10,000 rows)

Usage:
    python manage.py import_expenses
    python manage.py import_expenses --tenant erp_pg_alkuraimi --company-id 1
    python manage.py import_expenses --limit 5000
    python manage.py import_expenses --clear
"""

import random
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Company,
    Currency,
    Department,
    Employee,
    Expense,
    ExpenseCategory,
    PaymentMethod,
)

DATASET_DIR = Path(__file__).resolve().parents[3] / "datasets"


class Command(BaseCommand):
    help = "Import the synthetic expense claims dataset into ERP for ML testing."

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
            "--limit", type=int, default=None,
            help="Max number of expenses to import.",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete previously imported expense data before importing.",
        )

    # ------------------------------------------------------------------
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

        # Resolve company
        if options["company_id"]:
            company = Company.objects.using(self.db).filter(id=options["company_id"]).first()
            if not company:
                raise CommandError(f"Company id={options['company_id']} not found.")
        else:
            company = Company.objects.using(self.db).first()
            if not company:
                raise CommandError("No company found in this tenant DB.")
        self.company = company
        self.stdout.write(self.style.HTTP_INFO(f"Company: {company.name} (id={company.id})"))

        # Ensure reference data
        self.currency = self._ensure_currency()
        self.categories = self._ensure_categories()
        self.departments = self._ensure_departments()
        self.employees = self._get_employees()
        self.payment_methods = self._ensure_payment_methods()

        # Optional clear
        if options["clear"]:
            self._clear_expense_data()

        # Load CSV
        csv_path = DATASET_DIR / "expense_claims_dataset.csv"
        if not csv_path.exists():
            raise CommandError(
                f"Dataset not found: {csv_path}\n"
                "Run: python datasets/generate_synthetic.py"
            )
        df = pd.read_csv(csv_path)
        if options["limit"]:
            df = df.head(options["limit"])
        self.stdout.write(f"Loaded {len(df)} expenses from dataset.")

        # Import
        self.stdout.write("\n[Phase 1] Importing expenses …")
        self._import_expenses(df)

        self.stdout.write(self.style.SUCCESS("\n✓ Expense import complete!"))
        self._print_summary()

    # ==================================================================
    def _ensure_currency(self):
        cur, _ = Currency.objects.using(self.db).get_or_create(
            code="USD",
            defaults={"name": "US Dollar", "symbol": "$",
                       "is_base": True, "exchange_rate": 1},
        )
        return cur

    def _ensure_categories(self):
        cat_names = [
            'Travel', 'Office Supplies', 'Software', 'Meals & Entertain',
            'Equipment', 'Professional Svcs', 'Utilities', 'Marketing',
            'Training', 'Maintenance', 'Miscellaneous',
        ]
        cat_map = {}
        for name in cat_names:
            code = name.upper().replace(' ', '_').replace('&', 'AND')[:20]
            cat, _ = ExpenseCategory.objects.using(self.db).get_or_create(
                company=self.company, name=name,
                defaults={"code": code, "is_active": True},
            )
            cat_map[name] = cat
        return cat_map

    def _ensure_departments(self):
        dept_codes = {
            'Sales': 'SALES', 'R&D': 'R_D', 'HR': 'HR',
            'Finance': 'FIN', 'Operations': 'OPS',
            'Marketing': 'MKT', 'IT': 'IT',
        }
        dept_map = {}
        for name, code in dept_codes.items():
            dept, _ = Department.objects.using(self.db).get_or_create(
                company=self.company, code=code,
                defaults={"name": name, "is_active": True},
            )
            dept_map[name] = dept
        return dept_map

    def _get_employees(self):
        employees = list(
            Employee.objects.using(self.db).filter(
                company=self.company, employment_status='active',
            )[:200]
        )
        return employees if employees else None

    def _ensure_payment_methods(self):
        methods = {}
        for code, name in [('cash', 'Cash'), ('bank', 'Bank Transfer'), ('card', 'Credit Card')]:
            pm, _ = PaymentMethod.objects.using(self.db).get_or_create(
                company=self.company, code=code,
                defaults={"name": name, "is_active": True},
            )
            methods[code] = pm
        return methods

    def _clear_expense_data(self):
        self.stdout.write(self.style.WARNING("Clearing previously imported expense data …"))
        cnt = Expense.all_objects.using(self.db).filter(
            expense_number__startswith="EXP-"
        ).delete()[0]
        self.stdout.write(f"  Expenses deleted: {cnt}")

    # ==================================================================
    def _import_expenses(self, df):
        existing = set(
            Expense.objects.using(self.db)
            .filter(expense_number__startswith="EXP-")
            .values_list("expense_number", flat=True)
        )

        created = 0
        skipped = 0
        pm_list = list(self.payment_methods.values())

        for _, row in df.iterrows():
            exp_num = row['expense_number']
            if exp_num in existing:
                skipped += 1
                continue

            cat = self.categories.get(row['category'])
            if not cat:
                continue

            # Map employee — use the dataset's employee_id if possible
            employee = None
            if self.employees:
                # Deterministic mapping from dataset employee_id to DB employees
                emp_idx = hash(row.get('employee_id', '')) % len(self.employees)
                employee = self.employees[emp_idx]

            expense = Expense(
                company=self.company,
                expense_number=exp_num,
                expense_date=pd.to_datetime(row['expense_date']).date(),
                category=cat,
                employee=employee,
                description=row.get('description', f"Expense {exp_num}"),
                currency=self.currency,
                amount=Decimal(str(row['amount'])),
                tax_amount=Decimal(str(row.get('tax_amount', 0))),
                total_amount=Decimal(str(row.get('total_amount', row['amount']))),
                payment_method=random.choice(pm_list),
                status=row.get('status', 'approved'),
            )
            expense.save(using=self.db)
            created += 1

            if created % 1000 == 0:
                self.stdout.write(f"  … {created} expenses imported")

        self.stdout.write(f"  Created: {created}, Skipped (existing): {skipped}")

    # ==================================================================
    def _print_summary(self):
        expenses = Expense.objects.using(self.db).filter(
            company=self.company, expense_number__startswith="EXP-"
        )
        total = expenses.count()
        total_amount = sum(float(e.total_amount) for e in expenses.only('total_amount')[:10000])
        approved = expenses.filter(status='approved').count()

        self.stdout.write("\n  Summary:")
        self.stdout.write(f"    Expenses:     {total}")
        self.stdout.write(f"    Approved:     {approved}")
        self.stdout.write(f"    Total value:  ${total_amount:,.2f}")
