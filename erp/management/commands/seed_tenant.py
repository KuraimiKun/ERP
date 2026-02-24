"""
Management command: seed_tenant

Seeds realistic test data for a company/tenant using the hybrid approach:
  - Phase 1 (Master Data):   Factory Boy -> 1 DB hit per row, clean FK handling.
  - Phase 2 (Transactions):  Pre-load ID lists -> bulk_create() -> minimal DB round trips.

Usage:
    python manage.py seed_tenant                        # seeds first company, medium scale
    python manage.py seed_tenant --company-id 2 --scale large
    python manage.py seed_tenant --scale xl --clear
    python manage.py seed_tenant --scale tiny --no-transactions
"""

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from itertools import islice

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Account,
    Attendance,
    Campaign,
    Company,
    Currency,
    Customer,
    Department,
    Employee,
    Expense,
    ExpenseCategory,
    FiscalYear,
    Invoice,
    InvoiceLine,
    JournalEntry,
    JournalEntryLine,
    Lead,
    LeadActivity,
    Payment,
    PaymentMethod,
    Payroll,
    Product,
    ProductCategory,
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    QuoteLine,
    ServiceCategory,
    ServicePricing,
    Supplier,
    SupplierContact,
    SupplierDocument,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierPayment,
    SupplierPaymentAllocation,
    Task,
    TaxRate,
)

# --- Scale Configuration ------------------------------------------------------

# Master-data row counts per scale
MASTER_SCALE = {
    "tiny":   dict(depts=3,  employees=5,   customers=10,  suppliers=5,   products=10,  services=5,   leads=10,  campaigns=2),
    "small":  dict(depts=5,  employees=20,  customers=50,  suppliers=20,  products=50,  services=20,  leads=50,  campaigns=5),
    "medium": dict(depts=8,  employees=50,  customers=200, suppliers=50,  products=200, services=50,  leads=200, campaigns=10),
    "large":  dict(depts=10, employees=100, customers=500, suppliers=100, products=500, services=100, leads=500, campaigns=20),
    "xl":     dict(depts=15, employees=200, customers=1000,suppliers=200, products=1000,services=200, leads=1000,campaigns=30),
}

# Transactional row counts per scale
TRANSACTION_SCALE = {
    "tiny":   dict(invoices=50,    pos=20,    quotes=30,   expenses=30,   journal_entries=50,   attendance_days=30,  payroll_months=2),
    "small":  dict(invoices=500,   pos=100,   quotes=200,  expenses=150,  journal_entries=300,  attendance_days=90,  payroll_months=3),
    "medium": dict(invoices=2000,  pos=400,   quotes=800,  expenses=600,  journal_entries=1000, attendance_days=180, payroll_months=6),
    "large":  dict(invoices=10000, pos=2000,  quotes=4000, expenses=2000, journal_entries=5000, attendance_days=365, payroll_months=12),
    "xl":     dict(invoices=50000, pos=10000, quotes=20000,expenses=8000, journal_entries=20000,attendance_days=730, payroll_months=24),
}


# --- Helpers ------------------------------------------------------------------

def _uid(prefix: str = "", length: int = 8) -> str:
    """Short unique hex ID, optionally prefixed."""
    token = uuid.uuid4().hex[:length].upper()
    return f"{prefix}{token}" if prefix else token


def _rdate(days_back_max: int = 730, days_back_min: int = 0) -> date:
    """Random date in the past [days_back_min, days_back_max] days."""
    offset = random.randint(days_back_min, days_back_max)
    return date.today() - timedelta(days=offset)


def _rdecimal(lo: int, hi: int) -> Decimal:
    """Random Decimal in [lo, hi) with 2 decimal places."""
    return Decimal(str(round(random.uniform(lo, hi), 2)))


def _chunked(iterable, size: int):
    """Yield successive fixed-size chunks from an iterable."""
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk


def _bulk(model, objs, batch_size: int = 2000, msg_prefix: str = ""):
    """Bulk-create a list of unsaved model instances in batches."""
    total = len(objs)
    created = 0
    for chunk in _chunked(objs, batch_size):
        model.objects.bulk_create(chunk, ignore_conflicts=True)
        created += len(chunk)
    return created


# --- Command ------------------------------------------------------------------

class Command(BaseCommand):
    help = "Seed realistic test data for a tenant company (hybrid Factory Boy + bulk_create)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-id",
            type=int,
            default=None,
            help="ID of the company to seed (default: first company in DB).",
        )
        parser.add_argument(
            "--scale",
            choices=list(MASTER_SCALE.keys()),
            default="medium",
            help="Data volume: tiny / small / medium (default) / large / xl.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing non-system data for this company before seeding.",
        )
        parser.add_argument(
            "--no-master",
            action="store_true",
            help="Skip Phase 1 (master data). Requires existing customers/products.",
        )
        parser.add_argument(
            "--no-transactions",
            action="store_true",
            help="Skip Phase 2 (transactional bulk data).",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            default=None,
            help="Tenant database name (e.g. erp_pg_alkuraimi). Required unless --company-id points to a DB already in context.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Optional random seed for reproducible output.",
        )

    # --- Entry point ----------------------------------------------------------

    def handle(self, *args, **options):
        if options["seed"] is not None:
            random.seed(options["seed"])

        # -- Set up tenant DB context -----------------------------------------
        db_alias = self._activate_tenant(options["tenant"])
        with TenantDatabaseContext(db_alias):
            self._run(options)

    def _activate_tenant(self, tenant_name: str | None) -> str:
        """Resolve and register the tenant database, return its alias."""
        if tenant_name is None:
            # Try the first active tenant as a convenience
            tenant_db = TenantDatabase.objects.filter(status="active").first()
            if not tenant_db:
                raise CommandError(
                    "No active tenant database found. "
                    "Run 'migrate_tenants' first or pass --tenant <name>."
                )
            self.stdout.write(
                self.style.WARNING(
                    f"No --tenant specified; using first active tenant: {tenant_db.name}"
                )
            )
        else:
            try:
                tenant_db = TenantDatabase.objects.get(name=tenant_name)
            except TenantDatabase.DoesNotExist:
                available = list(
                    TenantDatabase.objects.filter(status="active").values_list("name", flat=True)
                )
                raise CommandError(
                    f"Tenant '{tenant_name}' not found. Available: {available or 'none'}"
                )
        return add_tenant_database(tenant_db)

    def _run(self, options):
        """Main seeding logic, called inside the tenant DB context."""
        scale = options["scale"]
        master_cfg = MASTER_SCALE[scale]
        txn_cfg = TRANSACTION_SCALE[scale]

        # -- Resolve company --------------------------------------------------
        company = self._get_company(options["company_id"])
        self.stdout.write(self.style.HTTP_INFO(f"\n[Company] {company.name}  (id={company.id})"))
        self.stdout.write(self.style.HTTP_INFO(f"[Scale]   {scale}"))

        # -- Optional clear ---------------------------------------------------
        if options["clear"]:
            self._clear_company_data(company)

        # -- Resolve required references --------------------------------------
        currency = company.base_currency
        fiscal_year = FiscalYear.objects.filter(company=company).order_by("-start_date").first()
        tax_rates = list(TaxRate.objects.filter(company=company, is_active=True))
        if not tax_rates:
            tax_rates = [self._ensure_default_tax_rate(company)]

        payment_methods = list(PaymentMethod.objects.filter(company=company, is_active=True))
        if not payment_methods:
            payment_methods = [self._ensure_default_payment_method(company)]

        accounts = self._get_account_buckets(company)

        # -- Phase 1: Master data (Factory Boy) -------------------------------
        ctx = {}
        if not options["no_master"]:
            self.stdout.write(self.style.WARNING("\n-- Phase 1: Master Data (Factory Boy) --"))
            ctx = self._seed_master_data(company, currency, tax_rates, master_cfg)
        else:
            self.stdout.write(self.style.WARNING("\n-- Phase 1 skipped (--no-master) --"))
            ctx = self._load_existing_ids(company, currency)

        # -- Phase 2: Transactions (bulk_create) ------------------------------
        if not options["no_transactions"]:
            self.stdout.write(self.style.WARNING("\n-- Phase 2: Transactions (bulk_create) --"))
            self._seed_transactions(company, currency, fiscal_year, tax_rates, payment_methods, accounts, ctx, txn_cfg)
        else:
            self.stdout.write(self.style.WARNING("\n-- Phase 2 skipped (--no-transactions) --"))

        self.stdout.write(self.style.SUCCESS("\n[OK]  Seeding complete!\n"))

    # --- Helpers: setup -------------------------------------------------------

    def _get_company(self, company_id) -> Company:
        if company_id:
            try:
                return Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                raise CommandError(f"Company with id={company_id} not found.")
        company = Company.objects.first()
        if not company:
            raise CommandError("No company found. Run 'erp_first_setup' first.")
        return company

    def _ensure_default_tax_rate(self, company):
        tr, _ = TaxRate.objects.get_or_create(
            company=company,
            name="VAT 15%",
            defaults={"rate": Decimal("15.00"), "is_default": True, "is_active": True},
        )
        return tr

    def _ensure_default_payment_method(self, company):
        pm, _ = PaymentMethod.objects.get_or_create(
            company=company,
            code="CASH",
            defaults={"name": "Cash", "is_active": True},
        )
        return pm

    def _get_account_buckets(self, company) -> dict:
        """Return {type: [account_ids]} for use in bulk creates."""
        qs = Account.objects.filter(company=company, is_active=True)
        buckets = {"income": [], "expense": [], "asset": [], "liability": [], "equity": []}
        for acc in qs.values("id", "account_type"):
            t = acc["account_type"]
            if t in buckets:
                buckets[t].append(acc["id"])
        return buckets

    def _clear_company_data(self, company):
        self.stdout.write(self.style.ERROR(f"[CLEAR] Deleting existing data for company {company.id}..."))
        # ERPBaseModel subclasses have `all_objects` (bypasses SoftDeleteManager).
        # TimeStampedModel subclasses (line items, activity, attendance) have no soft-delete
        # so plain `.objects` already covers all rows.
        with transaction.atomic():
            # Transactional first (FK deps), then master
            JournalEntryLine.objects.filter(journal_entry__company=company).delete()
            JournalEntry.all_objects.filter(company=company).delete()
            InvoiceLine.objects.filter(invoice__company=company).delete()
            Payment.all_objects.filter(company=company).delete()
            Invoice.all_objects.filter(company=company).delete()
            PurchaseOrderLine.objects.filter(purchase_order__company=company).delete()
            PurchaseOrder.all_objects.filter(company=company).delete()
            QuoteLine.objects.filter(quote__company=company).delete()
            Quote.all_objects.filter(company=company).delete()
            Expense.all_objects.filter(company=company).delete()
            Payroll.all_objects.filter(employee__company=company).delete()
            Attendance.objects.filter(employee__company=company).delete()
            LeadActivity.objects.filter(lead__company=company).delete()
            Lead.all_objects.filter(company=company).delete()
            Task.all_objects.filter(company=company).delete()
            Campaign.all_objects.filter(company=company).delete()
            Customer.all_objects.filter(company=company).delete()
            # Supplier sub-models (PROTECT FKs block Supplier deletion if skipped)
            SupplierPaymentAllocation.objects.filter(invoice__supplier__company=company).delete()
            SupplierPayment.all_objects.filter(supplier__company=company).delete()
            SupplierInvoiceLine.objects.filter(invoice__supplier__company=company).delete()
            SupplierInvoice.all_objects.filter(supplier__company=company).delete()
            SupplierDocument.objects.filter(supplier__company=company).delete()
            SupplierContact.objects.filter(supplier__company=company).delete()
            Supplier.all_objects.filter(company=company).delete()
            Employee.all_objects.filter(company=company).delete()
            Product.all_objects.filter(company=company).delete()
            ServicePricing.all_objects.filter(company=company).delete()
            ProductCategory.objects.filter(company=company).delete()
            ServiceCategory.objects.filter(company=company).delete()
            ExpenseCategory.objects.filter(company=company).delete()
            Department.all_objects.filter(company=company).delete()
        self.stdout.write(self.style.SUCCESS("   Done."))

    def _load_existing_ids(self, company, currency) -> dict:
        """Load existing master-data IDs when --no-master is set."""
        return {
            "customer_ids": list(Customer.objects.filter(company=company).values_list("id", flat=True)),
            "supplier_ids": list(Supplier.objects.filter(company=company).values_list("id", flat=True)),
            "employee_ids": list(Employee.objects.filter(company=company).values_list("id", flat=True)),
            "product_ids":  list(Product.objects.filter(company=company).values_list("id", flat=True)),
            "service_ids":  list(ServicePricing.objects.filter(company=company).values_list("id", flat=True)),
            "exp_cat_ids":  list(ExpenseCategory.objects.filter(company=company).values_list("id", flat=True)),
            "currency_id":  currency.id,
        }

    # --- Phase 1: Master data via Factory Boy ---------------------------------

    def _seed_master_data(self, company, currency, tax_rates, cfg: dict) -> dict:
        from erp.factories import (
            CampaignFactory,
            CustomerFactory,
            DepartmentFactory,
            EmployeeFactory,
            ExpenseCategoryFactory,
            LeadFactory,
            ProductCategoryFactory,
            ProductFactory,
            ServiceCategoryFactory,
            ServicePricingFactory,
            SupplierFactory,
            TaskFactory,
        )

        tax_rate = tax_rates[0]

        # Departments
        depts = DepartmentFactory.create_batch(cfg["depts"], company=company)
        dept_ids = [d.id for d in depts]
        self.stdout.write(f"   [OK] {len(depts):>6,}  Departments")

        # Expense categories
        exp_cats = ExpenseCategoryFactory.create_batch(
            min(cfg["depts"] + 4, 10), company=company
        )
        exp_cat_ids = [e.id for e in exp_cats]
        self.stdout.write(f"   [OK] {len(exp_cats):>6,}  Expense Categories")

        # Service categories
        svc_cats = ServiceCategoryFactory.create_batch(
            min(cfg["depts"], 8), company=company
        )
        self.stdout.write(f"   [OK] {len(svc_cats):>6,}  Service Categories")

        # Product categories
        prod_cats = ProductCategoryFactory.create_batch(
            min(cfg["depts"], 8), company=company
        )
        self.stdout.write(f"   [OK] {len(prod_cats):>6,}  Product Categories")

        # Employees
        employees = EmployeeFactory.create_batch(
            cfg["employees"],
            company=company,
            currency=currency,
            department=random.choice(depts),
        )
        employee_ids = [e.id for e in employees]
        self.stdout.write(f"   [OK] {len(employees):>6,}  Employees")

        # Customers
        customers = CustomerFactory.create_batch(
            cfg["customers"],
            company=company,
            currency=currency,
        )
        customer_ids = [c.id for c in customers]
        self.stdout.write(f"   [OK] {len(customers):>6,}  Customers")

        # Suppliers
        suppliers = SupplierFactory.create_batch(
            cfg["suppliers"],
            company=company,
            currency=currency,
        )
        supplier_ids = [s.id for s in suppliers]
        self.stdout.write(f"   [OK] {len(suppliers):>6,}  Suppliers")

        # Services
        services = ServicePricingFactory.create_batch(
            cfg["services"],
            company=company,
            currency=currency,
            category=random.choice(svc_cats),
            tax_rate=tax_rate,
        )
        service_ids = [s.id for s in services]
        self.stdout.write(f"   [OK] {len(services):>6,}  Services")

        # Products
        products = ProductFactory.create_batch(
            cfg["products"],
            company=company,
            currency=currency,
            category=random.choice(prod_cats),
            tax_rate=tax_rate,
            supplier=random.choice(suppliers),
        )
        product_ids = [p.id for p in products]
        self.stdout.write(f"   [OK] {len(products):>6,}  Products")

        # Leads
        leads = LeadFactory.create_batch(
            cfg["leads"],
            company=company,
            assigned_to=random.choice(employees),
        )
        self.stdout.write(f"   [OK] {len(leads):>6,}  Leads")

        # Lead activities (2-5 per lead, bulk)
        lead_activity_objs = []
        activity_types = ["call", "email", "meeting", "note", "whatsapp"]
        for lead in leads:
            for _ in range(random.randint(1, 4)):
                lead_activity_objs.append(
                    LeadActivity(
                        lead=lead,
                        activity_type=random.choice(activity_types),
                        subject=f"Follow-up {_uid()}",
                        description="Auto-generated activity.",
                        activity_date=timezone.now() - timedelta(days=random.randint(1, 360)),
                        is_completed=random.choice([True, False]),
                        performed_by_id=random.choice(employee_ids),
                    )
                )
        _bulk(LeadActivity, lead_activity_objs)
        self.stdout.write(f"   [OK] {len(lead_activity_objs):>6,}  Lead Activities")

        # Campaigns
        campaigns = CampaignFactory.create_batch(cfg["campaigns"], company=company)
        self.stdout.write(f"   [OK] {len(campaigns):>6,}  Campaigns")

        # Tasks (1 per employee on avg)
        task_statuses = ["todo", "in_progress", "on_hold", "completed", "cancelled"]
        task_priorities = ["low", "medium", "high", "urgent"]
        task_objs = []
        for _ in range(cfg["employees"] * 2):
            task_objs.append(
                Task(
                    company=company,
                    title=f"Task {_uid('T-')}",
                    description="Auto-generated task.",
                    status=random.choice(task_statuses),
                    priority=random.choice(task_priorities),
                    due_date=timezone.now() + timedelta(days=random.randint(-30, 180)),
                    assigned_to_id=random.choice(employee_ids),
                )
            )
        _bulk(Task, task_objs)
        self.stdout.write(f"   [OK] {len(task_objs):>6,}  Tasks")

        return {
            "customer_ids": customer_ids,
            "supplier_ids": supplier_ids,
            "employee_ids": employee_ids,
            "product_ids":  product_ids,
            "service_ids":  service_ids,
            "exp_cat_ids":  exp_cat_ids,
            "currency_id":  currency.id,
        }

    # --- Phase 2: Transactions via bulk_create -------------------------------

    def _seed_transactions(self, company, currency, fiscal_year, tax_rates, payment_methods, accounts, ctx, cfg):
        customer_ids  = ctx["customer_ids"]
        supplier_ids  = ctx["supplier_ids"]
        employee_ids  = ctx["employee_ids"]
        product_ids   = ctx["product_ids"]
        service_ids   = ctx["service_ids"]
        exp_cat_ids   = ctx["exp_cat_ids"]
        currency_id   = ctx["currency_id"]
        tax_rate_ids  = [t.id for t in tax_rates]
        pm_ids        = [p.id for p in payment_methods]

        if not customer_ids or not supplier_ids or not product_ids:
            self.stdout.write(self.style.WARNING("   [WARN] Not enough master data; skipping transactions."))
            return

        # Income/expense account IDs (fallback to any account if type missing)
        income_acc_ids  = accounts.get("income")  or accounts.get("asset") or []
        expense_acc_ids = accounts.get("expense") or accounts.get("asset") or []
        asset_acc_ids   = accounts.get("asset")   or []
        all_acc_ids     = income_acc_ids + expense_acc_ids + asset_acc_ids

        # -- Invoices + Lines ---------------------------------------------------
        self._seed_invoices(company, customer_ids, currency_id, tax_rate_ids, cfg["invoices"])

        # -- Payments ----------------------------------------------------------
        self._seed_payments(company, customer_ids, currency_id, pm_ids, cfg["invoices"] // 3)

        # -- Purchase Orders + Lines --------------------------------------------
        self._seed_purchase_orders(company, supplier_ids, product_ids, currency_id, tax_rate_ids, cfg["pos"])

        # -- Quotes + Lines ----------------------------------------------------
        self._seed_quotes(company, customer_ids, product_ids, service_ids, currency_id, tax_rate_ids, cfg["quotes"])

        # -- Expenses ---------------------------------------------------------
        self._seed_expenses(company, employee_ids, supplier_ids, exp_cat_ids, currency_id, pm_ids, cfg["expenses"])

        # -- Attendance --------------------------------------------------------
        self._seed_attendance(employee_ids, cfg["attendance_days"])

        # -- Payroll -----------------------------------------------------------
        self._seed_payroll(employee_ids, currency_id, cfg["payroll_months"])

        # -- Journal Entries + Lines -------------------------------------------
        if all_acc_ids:
            self._seed_journal_entries(company, fiscal_year, all_acc_ids, cfg["journal_entries"])

    # -- Invoices --------------------------------------------------------------

    def _seed_invoices(self, company, customer_ids, currency_id, tax_rate_ids, count):
        STATUSES = ["draft", "sent", "partial", "paid", "overdue"]
        TYPES    = ["standard", "standard", "standard", "credit", "debit"]  # weight standard

        # Global offset to avoid unique constraint collisions
        offset = Invoice.objects.count()

        invoice_objs = []
        line_objs    = []

        for n in range(count):
            inv_date  = _rdate(730)
            due_date  = inv_date + timedelta(days=random.choice([15, 30, 45, 60]))
            subtotal  = _rdecimal(100, 50000)
            tax_pct   = Decimal(random.choice(["0", "5", "15"]))
            tax_amt   = round(subtotal * tax_pct / 100, 2)
            total     = subtotal + tax_amt
            status    = random.choice(STATUSES)
            paid      = total if status == "paid" else (subtotal / 2 if status in ("partial",) else Decimal("0"))
            balance   = total - paid

            inv = Invoice(
                company_id=company.id,
                customer_id=random.choice(customer_ids),
                invoice_number=f"INV{offset + n + 1:09d}",
                invoice_type=random.choice(TYPES),
                invoice_date=inv_date,
                due_date=due_date,
                currency_id=currency_id,
                subtotal=subtotal,
                discount_amount=Decimal("0"),
                tax_amount=tax_amt,
                total_amount=total,
                paid_amount=paid,
                balance_due=balance,
                status=status,
            )
            invoice_objs.append(inv)

        created_invoices = Invoice.objects.bulk_create(invoice_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created_invoices):>6,}  Invoices")

        # Lines: 1-5 lines per invoice
        for inv in created_invoices:
            lines_per_inv = random.randint(1, 5)
            line_total    = round(inv.subtotal / lines_per_inv, 2)
            for _ in range(lines_per_inv):
                qty       = Decimal(str(random.randint(1, 10)))
                unit_price = round(line_total / qty, 2)
                tax_r_id  = random.choice(tax_rate_ids) if tax_rate_ids else None
                line_objs.append(
                    InvoiceLine(
                        invoice_id=inv.id,
                        description=f"Item {_uid()}",
                        quantity=qty,
                        unit_price=unit_price,
                        tax_rate_id=tax_r_id,
                        tax_amount=round(unit_price * qty * Decimal("0.15"), 2),
                        line_total=round(unit_price * qty, 2),
                    )
                )

        count_lines = _bulk(InvoiceLine, line_objs)
        self.stdout.write(f"   [OK] {len(line_objs):>6,}  Invoice Lines")

    # -- Payments --------------------------------------------------------------

    def _seed_payments(self, company, customer_ids, currency_id, pm_ids, count):
        offset = Payment.objects.count()
        PTYPES = ["received", "received", "refund"]
        objs   = []
        for n in range(count):
            amt = _rdecimal(100, 20000)
            objs.append(
                Payment(
                    company_id=company.id,
                    customer_id=random.choice(customer_ids),
                    payment_number=f"PMT{offset + n + 1:09d}",
                    payment_type=random.choice(PTYPES),
                    payment_date=_rdate(730),
                    payment_method_id=random.choice(pm_ids),
                    currency_id=currency_id,
                    amount=amt,
                    allocated_amount=amt,
                    unallocated_amount=Decimal("0"),
                )
            )
        c = _bulk(Payment, objs)
        self.stdout.write(f"   [OK] {c:>6,}  Payments")

    # -- Purchase Orders --------------------------------------------------------

    def _seed_purchase_orders(self, company, supplier_ids, product_ids, currency_id, tax_rate_ids, count):
        offset = PurchaseOrder.objects.count()
        STATUSES = ["draft", "pending", "approved", "sent", "received"]
        po_objs  = []
        line_objs = []

        for n in range(count):
            po_date   = _rdate(730)
            exp_date  = po_date + timedelta(days=random.randint(7, 60))
            subtotal  = _rdecimal(500, 100000)
            tax_amt   = round(subtotal * Decimal("0.15"), 2)
            total     = subtotal + tax_amt

            po = PurchaseOrder(
                company_id=company.id,
                supplier_id=random.choice(supplier_ids),
                po_number=f"PO{offset + n + 1:09d}",
                po_date=po_date,
                expected_date=exp_date,
                currency_id=currency_id,
                subtotal=subtotal,
                discount_amount=Decimal("0"),
                tax_amount=tax_amt,
                total_amount=total,
                paid_amount=Decimal("0"),
                balance_due=total,
                status=random.choice(STATUSES),
            )
            po_objs.append(po)

        created_pos = PurchaseOrder.objects.bulk_create(po_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created_pos):>6,}  Purchase Orders")

        for po in created_pos:
            n_lines   = random.randint(1, 6)
            line_total = round(po.subtotal / n_lines, 2)
            for _ in range(n_lines):
                qty        = Decimal(str(random.randint(1, 20)))
                unit_price = round(line_total / qty, 2)
                line_objs.append(
                    PurchaseOrderLine(
                        purchase_order_id=po.id,
                        product_id=random.choice(product_ids),
                        description=f"Purchase item {_uid()}",
                        quantity=qty,
                        unit_price=unit_price,
                        tax_rate_id=random.choice(tax_rate_ids) if tax_rate_ids else None,
                        tax_amount=round(unit_price * qty * Decimal("0.15"), 2),
                        line_total=round(unit_price * qty, 2),
                    )
                )

        c = _bulk(PurchaseOrderLine, line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  PO Lines")

    # -- Quotes ----------------------------------------------------------------

    def _seed_quotes(self, company, customer_ids, product_ids, service_ids, currency_id, tax_rate_ids, count):
        offset = Quote.objects.count()
        STATUSES = ["draft", "sent", "accepted", "declined", "expired"]
        quote_objs = []
        line_objs  = []

        for n in range(count):
            q_date   = _rdate(730)
            valid_until = q_date + timedelta(days=random.randint(7, 30))
            subtotal = _rdecimal(200, 50000)
            tax_amt  = round(subtotal * Decimal("0.15"), 2)
            total    = subtotal + tax_amt

            quote_objs.append(
                Quote(
                    company_id=company.id,
                    customer_id=random.choice(customer_ids),
                    quote_number=f"QT{offset + n + 1:09d}",
                    quote_date=q_date,
                    valid_until=valid_until,
                    currency_id=currency_id,
                    subtotal=subtotal,
                    discount_percent=Decimal("0"),
                    discount_amount=Decimal("0"),
                    tax_amount=tax_amt,
                    total_amount=total,
                    status=random.choice(STATUSES),
                )
            )

        created_quotes = Quote.objects.bulk_create(quote_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created_quotes):>6,}  Quotes")

        item_pool = product_ids + service_ids
        for quote in created_quotes:
            n_lines  = random.randint(1, 4)
            line_total = round(quote.subtotal / n_lines, 2)
            for _ in range(n_lines):
                qty        = Decimal(str(random.randint(1, 10)))
                unit_price = round(line_total / qty, 2)
                line_objs.append(
                    QuoteLine(
                        quote_id=quote.id,
                        description=f"Service/Product {_uid()}",
                        quantity=qty,
                        unit_price=unit_price,
                        tax_rate_id=random.choice(tax_rate_ids) if tax_rate_ids else None,
                        tax_amount=round(unit_price * qty * Decimal("0.15"), 2),
                        line_total=round(unit_price * qty, 2),
                    )
                )

        c = _bulk(QuoteLine, line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Quote Lines")

    # -- Expenses --------------------------------------------------------------

    def _seed_expenses(self, company, employee_ids, supplier_ids, exp_cat_ids, currency_id, pm_ids, count):
        if not exp_cat_ids:
            self.stdout.write("   [!]  No expense categories; skipping expenses.")
            return
        offset   = Expense.objects.count()
        STATUSES = ["draft", "submitted", "approved", "paid"]
        objs     = []
        for n in range(count):
            amt    = _rdecimal(50, 5000)
            tax    = round(amt * Decimal("0.15"), 2)
            total  = amt + tax
            objs.append(
                Expense(
                    company_id=company.id,
                    expense_number=f"EXP{offset + n + 1:09d}",
                    expense_date=_rdate(365),
                    category_id=random.choice(exp_cat_ids),
                    supplier_id=random.choice(supplier_ids),
                    employee_id=random.choice(employee_ids),
                    description="Auto-generated expense",
                    currency_id=currency_id,
                    amount=amt,
                    tax_amount=tax,
                    total_amount=total,
                    payment_method_id=random.choice(pm_ids) if pm_ids else None,
                    status=random.choice(STATUSES),
                )
            )
        c = _bulk(Expense, objs)
        self.stdout.write(f"   [OK] {c:>6,}  Expenses")

    # -- Attendance ------------------------------------------------------------

    def _seed_attendance(self, employee_ids, days_back: int):
        """Generate attendance records for each employee for the last N working days."""
        from datetime import date as date_cls
        today    = date_cls.today()
        objs     = []
        seen     = set()   # (employee_id, date) -- unique_together constraint

        working_days = [
            today - timedelta(days=d)
            for d in range(days_back)
            if (today - timedelta(days=d)).weekday() < 5  # Mon-Fri
        ]

        for emp_id in employee_ids:
            for work_date in working_days:
                key = (emp_id, work_date)
                if key in seen:
                    continue
                seen.add(key)
                is_present  = random.random() > 0.05   # 95% attendance rate
                is_late     = is_present and random.random() < 0.10
                late_mins   = random.randint(5, 60) if is_late else 0
                hours       = Decimal(str(round(random.uniform(6.5, 9.0), 2))) if is_present else Decimal("0")
                overtime    = max(Decimal("0"), hours - Decimal("8"))
                objs.append(
                    Attendance(
                        employee_id=emp_id,
                        date=work_date,
                        is_present=is_present,
                        is_late=is_late,
                        late_minutes=late_mins,
                        hours_worked=hours,
                        overtime_hours=overtime,
                    )
                )

        c = _bulk(Attendance, objs)
        self.stdout.write(f"   [OK] {c:>6,}  Attendance Records")

    # -- Payroll ---------------------------------------------------------------

    def _seed_payroll(self, employee_ids, currency_id, months: int):
        """Generate payroll for last N months for each employee."""
        from datetime import date as date_cls
        today  = date_cls.today()
        objs   = []
        seen   = set()   # (employee_id, period_start, period_end)

        # Fetch basic salaries once
        sal_map = dict(Employee.objects.filter(id__in=employee_ids).values_list("id", "basic_salary"))

        for month_offset in range(months):
            # Go back month_offset months
            year  = today.year
            month = today.month - month_offset
            while month <= 0:
                month += 12
                year  -= 1
            from calendar import monthrange
            period_start = date_cls(year, month, 1)
            period_end   = date_cls(year, month, monthrange(year, month)[1])

            for emp_id in employee_ids:
                key = (emp_id, period_start, period_end)
                if key in seen:
                    continue
                seen.add(key)

                basic         = Decimal(str(sal_map.get(emp_id, 5000)))
                housing       = round(basic * Decimal("0.25"), 2)
                transport     = round(basic * Decimal("0.10"), 2)
                other_allow   = _rdecimal(0, int(basic * Decimal("0.05")))
                bonus         = _rdecimal(0, int(basic * Decimal("0.20")))
                absence_ded   = _rdecimal(0, 200)
                late_ded      = _rdecimal(0, 100)
                social_ins    = round(basic * Decimal("0.09"), 2)
                gross         = basic + housing + transport + other_allow + bonus
                total_ded     = absence_ded + late_ded + social_ins
                net           = gross - total_ded

                objs.append(
                    Payroll(
                        employee_id=emp_id,
                        period_start=period_start,
                        period_end=period_end,
                        basic_salary=basic,
                        housing_allowance=housing,
                        transport_allowance=transport,
                        other_allowances=other_allow,
                        overtime_amount=Decimal("0"),
                        bonus=bonus,
                        absence_deduction=absence_ded,
                        late_deduction=late_ded,
                        loan_deduction=Decimal("0"),
                        social_insurance=social_ins,
                        tax_deduction=Decimal("0"),
                        other_deductions=Decimal("0"),
                        gross_salary=gross,
                        total_deductions=total_ded,
                        net_salary=net,
                        status=random.choice(["calculated", "approved", "paid"]),
                        currency_id=currency_id,
                    )
                )

        c = _bulk(Payroll, objs)
        self.stdout.write(f"   [OK] {c:>6,}  Payroll Records")

    # -- Journal Entries -------------------------------------------------------

    def _seed_journal_entries(self, company, fiscal_year, account_ids, count):
        """Balanced double-entry journal entries (debit == credit per entry)."""
        entry_objs = []
        line_objs  = []

        # Offset to avoid unique_together (company, entry_number) conflicts
        existing = JournalEntry.objects.filter(company=company).count()
        TYPES    = ["manual", "adjustment", "manual", "manual"]  # weight manual

        for n in range(count):
            entry_date = _rdate(730)
            amount     = _rdecimal(100, 25000)
            desc       = f"JE memo {_uid()}"

            entry = JournalEntry(
                company_id=company.id,
                entry_number=f"JE{existing + n + 1:09d}",
                entry_date=entry_date,
                entry_type=random.choice(TYPES),
                description=desc,
                fiscal_year=fiscal_year,
                total_debit=amount,
                total_credit=amount,
                status=random.choice(["draft", "posted"]),
            )
            entry_objs.append(entry)

        created = JournalEntry.objects.bulk_create(entry_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created):>6,}  Journal Entries")

        # Each entry has exactly 2 balanced lines: one debit, one credit
        for entry in created:
            debit_acc  = random.choice(account_ids)
            credit_acc = random.choice(account_ids)
            amount     = entry.total_debit
            line_objs += [
                JournalEntryLine(
                    journal_entry_id=entry.id,
                    account_id=debit_acc,
                    description=entry.description,
                    debit_amount=amount,
                    credit_amount=Decimal("0"),
                ),
                JournalEntryLine(
                    journal_entry_id=entry.id,
                    account_id=credit_acc,
                    description=entry.description,
                    debit_amount=Decimal("0"),
                    credit_amount=amount,
                ),
            ]

        c = _bulk(JournalEntryLine, line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Journal Entry Lines")
