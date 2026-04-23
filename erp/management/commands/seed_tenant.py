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
    # Inventory & Warehouse
    UnitOfMeasure,
    UnitOfMeasureConversion,
    Warehouse,
    WarehouseZone,
    WarehouseBin,
    LotBatch,
    SerialNumber,
    StockItem,
    StockMovement,
    GoodsReceiptNote,
    GoodsReceiptLine,
    StockTransfer,
    StockTransferLine,
    StockAdjustment,
    StockAdjustmentLine,
    CycleCount,
    CycleCountLine,
    PickList,
    PickListLine,
    ShipmentNote,
    ShipmentLine,
    ReorderRule,
    InventoryValuationConfig,
    # Fixed Assets
    AssetCategory,
    FixedAsset,
    DepreciationSchedule,
    AssetDisposal,
    AssetTransfer,
    AssetRevaluation,
    AssetMaintenanceLog,
)

# --- Scale Configuration ------------------------------------------------------

# Master-data row counts per scale
MASTER_SCALE = {
    "tiny": dict(
        depts=3, employees=5, customers=10, suppliers=5, products=10, services=5, leads=10, campaigns=2, warehouses=1
    ),
    "small": dict(
        depts=5, employees=20, customers=50, suppliers=20, products=50, services=20, leads=50, campaigns=5, warehouses=2
    ),
    "medium": dict(
        depts=8,
        employees=50,
        customers=200,
        suppliers=50,
        products=200,
        services=50,
        leads=200,
        campaigns=10,
        warehouses=3,
    ),
    "large": dict(
        depts=10,
        employees=100,
        customers=500,
        suppliers=100,
        products=500,
        services=100,
        leads=500,
        campaigns=20,
        warehouses=5,
    ),
    "xl": dict(
        depts=15,
        employees=200,
        customers=1000,
        suppliers=200,
        products=1000,
        services=200,
        leads=1000,
        campaigns=30,
        warehouses=7,
    ),
}

# Transactional row counts per scale
TRANSACTION_SCALE = {
    "tiny": dict(
        invoices=50,
        pos=20,
        quotes=30,
        expenses=30,
        journal_entries=50,
        attendance_days=30,
        payroll_months=2,
        grns=10,
        transfers=5,
        adjustments=3,
        counts=2,
        assets=5,
    ),
    "small": dict(
        invoices=500,
        pos=100,
        quotes=200,
        expenses=150,
        journal_entries=300,
        attendance_days=90,
        payroll_months=3,
        grns=40,
        transfers=15,
        adjustments=8,
        counts=5,
        assets=15,
    ),
    "medium": dict(
        invoices=2000,
        pos=400,
        quotes=800,
        expenses=600,
        journal_entries=1000,
        attendance_days=180,
        payroll_months=6,
        grns=150,
        transfers=50,
        adjustments=20,
        counts=10,
        assets=40,
    ),
    "large": dict(
        invoices=10000,
        pos=2000,
        quotes=4000,
        expenses=2000,
        journal_entries=5000,
        attendance_days=365,
        payroll_months=12,
        grns=600,
        transfers=200,
        adjustments=80,
        counts=30,
        assets=100,
    ),
    "xl": dict(
        invoices=50000,
        pos=10000,
        quotes=20000,
        expenses=8000,
        journal_entries=20000,
        attendance_days=730,
        payroll_months=24,
        grns=3000,
        transfers=800,
        adjustments=300,
        counts=100,
        assets=300,
    ),
}


# --- Inventory / Warehouse / Asset Reference Data ----------------------------

_WAREHOUSE_TEMPLATES = [
    {
        "code": "WH-MAIN",
        "name": "Main Warehouse",
        "name_ar": "المستودع الرئيسي",
        "city": "Riyadh",
        "country": "Saudi Arabia",
    },
    {
        "code": "WH-DIST",
        "name": "Distribution Center",
        "name_ar": "مركز التوزيع",
        "city": "Jeddah",
        "country": "Saudi Arabia",
    },
    {
        "code": "WH-RAW",
        "name": "Raw Materials Store",
        "name_ar": "مستودع المواد الخام",
        "city": "Dammam",
        "country": "Saudi Arabia",
    },
    {
        "code": "WH-FIN",
        "name": "Finished Goods Warehouse",
        "name_ar": "مستودع المنتجات النهائية",
        "city": "Riyadh",
        "country": "Saudi Arabia",
    },
    {
        "code": "WH-QAR",
        "name": "QA & Returns Center",
        "name_ar": "مركز الجودة والمرتجعات",
        "city": "Riyadh",
        "country": "Saudi Arabia",
    },
    {
        "code": "WH-COLD",
        "name": "Cold Storage Facility",
        "name_ar": "مستودع التبريد",
        "city": "Jeddah",
        "country": "Saudi Arabia",
    },
    {
        "code": "WH-TEMP",
        "name": "Temporary Staging Area",
        "name_ar": "منطقة التجميع المؤقتة",
        "city": "Makkah",
        "country": "Saudi Arabia",
    },
]

_ZONE_TEMPLATES = [
    {"code": "RCV", "name": "Receiving Area", "name_ar": "منطقة الاستلام", "zone_type": "receiving"},
    {"code": "BULK", "name": "Bulk Storage", "name_ar": "تخزين بالجملة", "zone_type": "storage"},
    {"code": "PICK", "name": "Pick Face", "name_ar": "منطقة التجميع", "zone_type": "picking"},
    {"code": "PACK", "name": "Packing Area", "name_ar": "منطقة التعبئة", "zone_type": "packing"},
    {"code": "SHIP", "name": "Shipping Dock", "name_ar": "رصيف الشحن", "zone_type": "shipping"},
    {"code": "QRN", "name": "Quarantine", "name_ar": "منطقة الحجر", "zone_type": "quarantine"},
    {"code": "RET", "name": "Returns Processing", "name_ar": "معالجة المرتجعات", "zone_type": "returns"},
]

_UOM_DATA = [
    {"name": "Piece", "name_ar": "قطعة", "abbr": "pc", "category": "unit", "is_base": True},
    {"name": "Dozen", "name_ar": "درزن", "abbr": "dz", "category": "unit", "is_base": False},
    {"name": "Box", "name_ar": "صندوق", "abbr": "box", "category": "unit", "is_base": False},
    {"name": "Carton", "name_ar": "كرتون", "abbr": "ctn", "category": "unit", "is_base": False},
    {"name": "Pallet", "name_ar": "طبلية", "abbr": "plt", "category": "unit", "is_base": False},
    {"name": "Kilogram", "name_ar": "كيلوغرام", "abbr": "kg", "category": "weight", "is_base": True},
    {"name": "Gram", "name_ar": "غرام", "abbr": "g", "category": "weight", "is_base": False},
    {"name": "Metric Ton", "name_ar": "طن", "abbr": "ton", "category": "weight", "is_base": False},
    {"name": "Liter", "name_ar": "لتر", "abbr": "L", "category": "volume", "is_base": True},
    {"name": "Milliliter", "name_ar": "مليلتر", "abbr": "mL", "category": "volume", "is_base": False},
    {"name": "Meter", "name_ar": "متر", "abbr": "m", "category": "length", "is_base": True},
    {"name": "Centimeter", "name_ar": "سنتيمتر", "abbr": "cm", "category": "length", "is_base": False},
    {"name": "Square Meter", "name_ar": "متر مربع", "abbr": "sqm", "category": "area", "is_base": True},
    {"name": "Hour", "name_ar": "ساعة", "abbr": "hr", "category": "time", "is_base": True},
]

_UOM_CONVERSIONS = [
    ("dz", "pc", 12),
    ("box", "pc", 24),
    ("ctn", "box", 10),
    ("plt", "ctn", 40),
    ("kg", "g", 1000),
    ("ton", "kg", 1000),
    ("L", "mL", 1000),
    ("m", "cm", 100),
]

_ASSET_TEMPLATES = [
    # (name, name_ar, category_code, cost_lo, cost_hi)
    ("Head Office Building", "مبنى المكتب الرئيسي", "FA-BLD", 500_000, 3_000_000),
    ("Warehouse Building", "مبنى المستودع", "FA-BLD", 300_000, 1_500_000),
    ("Executive Desk Set", "طقم مكتب تنفيذي", "FA-FRN", 3_000, 12_000),
    ("Conference Room Furniture", "أثاث غرفة الاجتماعات", "FA-FRN", 8_000, 35_000),
    ("Office Chairs (10 pcs)", "كراسي مكتب (١٠ قطع)", "FA-FRN", 5_000, 20_000),
    ("Storage Shelving Units", "وحدات أرفف تخزين", "FA-FRN", 4_000, 15_000),
    ("Delivery Van", "شاحنة توصيل", "FA-VEH", 60_000, 180_000),
    ("Company Sedan", "سيارة الشركة", "FA-VEH", 80_000, 250_000),
    ("Forklift", "رافعة شوكية", "FA-VEH", 40_000, 120_000),
    ("Dell PowerEdge Server", "خادم Dell PowerEdge", "FA-IT", 25_000, 100_000),
    ("Laptop Fleet (10 units)", "أسطول حواسيب محمولة (١٠)", "FA-IT", 15_000, 50_000),
    ("Network Switch & Cabling", "مفتاح شبكة وتوصيلات", "FA-IT", 10_000, 40_000),
    ("CCTV Security System", "نظام كاميرات مراقبة", "FA-IT", 8_000, 30_000),
    ("ERP Software License", "ترخيص نظام ERP", "FA-IT", 20_000, 80_000),
    ("Office Interior Renovation", "تجديد ديكور المكتب", "FA-LHI", 50_000, 250_000),
    ("Warehouse Fit-Out", "تجهيز المستودع", "FA-LHI", 40_000, 200_000),
]

_CARRIER_NAMES = [
    "DHL Express",
    "FedEx",
    "Aramex",
    "SMSA Express",
    "UPS",
    "Naqel Express",
    "Saudi Post",
    "Zajil Express",
    "J&T Express",
]


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
                    "No active tenant database found. Run 'migrate_tenants' first or pass --tenant <name>."
                )
            self.stdout.write(self.style.WARNING(f"No --tenant specified; using first active tenant: {tenant_db.name}"))
        else:
            try:
                tenant_db = TenantDatabase.objects.get(name=tenant_name)
            except TenantDatabase.DoesNotExist:
                available = list(TenantDatabase.objects.filter(status="active").values_list("name", flat=True))
                raise CommandError(f"Tenant '{tenant_name}' not found. Available: {available or 'none'}")
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
            # --- Fixed Assets (delete before employees/suppliers/departments) ---
            AssetMaintenanceLog.all_objects.filter(asset__company=company).delete()
            AssetDisposal.all_objects.filter(asset__company=company).delete()
            AssetTransfer.all_objects.filter(asset__company=company).delete()
            AssetRevaluation.all_objects.filter(asset__company=company).delete()
            DepreciationSchedule.objects.filter(asset__company=company).delete()
            FixedAsset.all_objects.filter(company=company).delete()
            # --- Inventory Transactions (before PO/Supplier/Product deletion) ---
            StockMovement.objects.filter(company=company).delete()
            ShipmentLine.objects.filter(shipment__company=company).delete()
            ShipmentNote.all_objects.filter(company=company).delete()
            PickListLine.objects.filter(pick_list__company=company).delete()
            PickList.all_objects.filter(company=company).delete()
            CycleCountLine.objects.filter(cycle_count__company=company).delete()
            CycleCount.all_objects.filter(company=company).delete()
            StockAdjustmentLine.objects.filter(adjustment__company=company).delete()
            StockAdjustment.all_objects.filter(company=company).delete()
            StockTransferLine.objects.filter(transfer__company=company).delete()
            StockTransfer.all_objects.filter(company=company).delete()
            GoodsReceiptLine.objects.filter(grn__company=company).delete()
            GoodsReceiptNote.all_objects.filter(company=company).delete()
            ReorderRule.objects.filter(company=company).delete()
            SerialNumber.objects.filter(company=company).delete()
            StockItem.objects.filter(company=company).delete()
            LotBatch.all_objects.filter(company=company).delete()
            # --- Existing transactional data ---
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
            # --- Inventory Master Data ---
            WarehouseBin.objects.filter(zone__warehouse__company=company).delete()
            WarehouseZone.objects.filter(warehouse__company=company).delete()
            Warehouse.all_objects.filter(company=company).delete()
            UnitOfMeasureConversion.objects.filter(company=company).delete()
            UnitOfMeasure.objects.filter(company=company).delete()
            InventoryValuationConfig.objects.filter(company=company).delete()
        self.stdout.write(self.style.SUCCESS("   Done."))

    def _load_existing_ids(self, company, currency) -> dict:
        """Load existing master-data IDs when --no-master is set."""
        return {
            "customer_ids": list(Customer.objects.filter(company=company).values_list("id", flat=True)),
            "supplier_ids": list(Supplier.objects.filter(company=company).values_list("id", flat=True)),
            "employee_ids": list(Employee.objects.filter(company=company).values_list("id", flat=True)),
            "product_ids": list(Product.objects.filter(company=company).values_list("id", flat=True)),
            "service_ids": list(ServicePricing.objects.filter(company=company).values_list("id", flat=True)),
            "exp_cat_ids": list(ExpenseCategory.objects.filter(company=company).values_list("id", flat=True)),
            "currency_id": currency.id,
            "warehouse_ids": list(Warehouse.objects.filter(company=company).values_list("id", flat=True)),
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
        )

        tax_rate = tax_rates[0]

        # Departments
        depts = DepartmentFactory.create_batch(cfg["depts"], company=company)
        self.stdout.write(f"   [OK] {len(depts):>6,}  Departments")

        # Expense categories
        exp_cats = ExpenseCategoryFactory.create_batch(min(cfg["depts"] + 4, 10), company=company)
        exp_cat_ids = [e.id for e in exp_cats]
        self.stdout.write(f"   [OK] {len(exp_cats):>6,}  Expense Categories")

        # Service categories
        svc_cats = ServiceCategoryFactory.create_batch(min(cfg["depts"], 8), company=company)
        self.stdout.write(f"   [OK] {len(svc_cats):>6,}  Service Categories")

        # Product categories
        prod_cats = ProductCategoryFactory.create_batch(min(cfg["depts"], 8), company=company)
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

        # Inventory master data (warehouses, zones, bins, UoMs)
        inv_ctx = self._seed_inventory_master(company, employee_ids, cfg)

        return {
            "customer_ids": customer_ids,
            "supplier_ids": supplier_ids,
            "employee_ids": employee_ids,
            "product_ids": product_ids,
            "service_ids": service_ids,
            "exp_cat_ids": exp_cat_ids,
            "currency_id": currency.id,
            **inv_ctx,
        }

    # --- Phase 2: Transactions via bulk_create -------------------------------

    def _seed_transactions(self, company, currency, fiscal_year, tax_rates, payment_methods, accounts, ctx, cfg):
        customer_ids = ctx["customer_ids"]
        supplier_ids = ctx["supplier_ids"]
        employee_ids = ctx["employee_ids"]
        product_ids = ctx["product_ids"]
        service_ids = ctx["service_ids"]
        exp_cat_ids = ctx["exp_cat_ids"]
        currency_id = ctx["currency_id"]
        tax_rate_ids = [t.id for t in tax_rates]
        pm_ids = [p.id for p in payment_methods]

        if not customer_ids or not supplier_ids or not product_ids:
            self.stdout.write(self.style.WARNING("   [WARN] Not enough master data; skipping transactions."))
            return

        # Income/expense account IDs (fallback to any account if type missing)
        income_acc_ids = accounts.get("income") or accounts.get("asset") or []
        expense_acc_ids = accounts.get("expense") or accounts.get("asset") or []
        asset_acc_ids = accounts.get("asset") or []
        all_acc_ids = income_acc_ids + expense_acc_ids + asset_acc_ids

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

        # -- Inventory Transactions (GRNs, transfers, adjustments, etc.) -------
        self._seed_inventory_transactions(company, currency, fiscal_year, ctx, cfg)

        # -- Fixed Assets (register, depreciation, maintenance) ----------------
        self._seed_fixed_assets_data(company, currency, fiscal_year, ctx, cfg)

    # -- Invoices --------------------------------------------------------------

    def _seed_invoices(self, company, customer_ids, currency_id, tax_rate_ids, count):
        STATUSES = ["draft", "sent", "partial", "paid", "overdue"]
        TYPES = ["standard", "standard", "standard", "credit", "debit"]  # weight standard

        # Global offset to avoid unique constraint collisions
        offset = Invoice.objects.count()

        invoice_objs = []
        line_objs = []

        for n in range(count):
            inv_date = _rdate(730)
            due_date = inv_date + timedelta(days=random.choice([15, 30, 45, 60]))
            subtotal = _rdecimal(100, 50000)
            tax_pct = Decimal(random.choice(["0", "5", "15"]))
            tax_amt = round(subtotal * tax_pct / 100, 2)
            total = subtotal + tax_amt
            status = random.choice(STATUSES)
            paid = total if status == "paid" else (subtotal / 2 if status in ("partial",) else Decimal("0"))
            balance = total - paid

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
            line_total = round(inv.subtotal / lines_per_inv, 2)
            for _ in range(lines_per_inv):
                qty = Decimal(str(random.randint(1, 10)))
                unit_price = round(line_total / qty, 2)
                tax_r_id = random.choice(tax_rate_ids) if tax_rate_ids else None
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

        _bulk(InvoiceLine, line_objs)
        self.stdout.write(f"   [OK] {len(line_objs):>6,}  Invoice Lines")

    # -- Payments --------------------------------------------------------------

    def _seed_payments(self, company, customer_ids, currency_id, pm_ids, count):
        offset = Payment.objects.count()
        PTYPES = ["received", "received", "refund"]
        objs = []
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
        po_objs = []
        line_objs = []

        for n in range(count):
            po_date = _rdate(730)
            exp_date = po_date + timedelta(days=random.randint(7, 60))
            subtotal = _rdecimal(500, 100000)
            tax_amt = round(subtotal * Decimal("0.15"), 2)
            total = subtotal + tax_amt

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
            n_lines = random.randint(1, 6)
            line_total = round(po.subtotal / n_lines, 2)
            for _ in range(n_lines):
                qty = Decimal(str(random.randint(1, 20)))
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
        line_objs = []

        for n in range(count):
            q_date = _rdate(730)
            valid_until = q_date + timedelta(days=random.randint(7, 30))
            subtotal = _rdecimal(200, 50000)
            tax_amt = round(subtotal * Decimal("0.15"), 2)
            total = subtotal + tax_amt

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

        for quote in created_quotes:
            n_lines = random.randint(1, 4)
            line_total = round(quote.subtotal / n_lines, 2)
            for _ in range(n_lines):
                qty = Decimal(str(random.randint(1, 10)))
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
        offset = Expense.objects.count()
        STATUSES = ["draft", "submitted", "approved", "paid"]
        objs = []
        for n in range(count):
            amt = _rdecimal(50, 5000)
            tax = round(amt * Decimal("0.15"), 2)
            total = amt + tax
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

        today = date_cls.today()
        objs = []
        seen = set()  # (employee_id, date) -- unique_together constraint

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
                is_present = random.random() > 0.05  # 95% attendance rate
                is_late = is_present and random.random() < 0.10
                late_mins = random.randint(5, 60) if is_late else 0
                hours = Decimal(str(round(random.uniform(6.5, 9.0), 2))) if is_present else Decimal("0")
                overtime = max(Decimal("0"), hours - Decimal("8"))
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

        today = date_cls.today()
        objs = []
        seen = set()  # (employee_id, period_start, period_end)

        # Fetch basic salaries once
        sal_map = dict(Employee.objects.filter(id__in=employee_ids).values_list("id", "basic_salary"))

        for month_offset in range(months):
            # Go back month_offset months
            year = today.year
            month = today.month - month_offset
            while month <= 0:
                month += 12
                year -= 1
            from calendar import monthrange

            period_start = date_cls(year, month, 1)
            period_end = date_cls(year, month, monthrange(year, month)[1])

            for emp_id in employee_ids:
                key = (emp_id, period_start, period_end)
                if key in seen:
                    continue
                seen.add(key)

                basic = Decimal(str(sal_map.get(emp_id, 5000)))
                housing = round(basic * Decimal("0.25"), 2)
                transport = round(basic * Decimal("0.10"), 2)
                other_allow = _rdecimal(0, int(basic * Decimal("0.05")))
                bonus = _rdecimal(0, int(basic * Decimal("0.20")))
                absence_ded = _rdecimal(0, 200)
                late_ded = _rdecimal(0, 100)
                social_ins = round(basic * Decimal("0.09"), 2)
                gross = basic + housing + transport + other_allow + bonus
                total_ded = absence_ded + late_ded + social_ins
                net = gross - total_ded

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
        line_objs = []

        # Offset to avoid unique_together (company, entry_number) conflicts
        existing = JournalEntry.objects.filter(company=company).count()
        TYPES = ["manual", "adjustment", "manual", "manual"]  # weight manual

        for n in range(count):
            entry_date = _rdate(730)
            amount = _rdecimal(100, 25000)
            desc = f"JE memo {_uid()}"

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
            debit_acc = random.choice(account_ids)
            credit_acc = random.choice(account_ids)
            amount = entry.total_debit
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

    # =========================================================================
    # INVENTORY & WAREHOUSE  (master + transactions)
    # =========================================================================

    def _seed_inventory_master(self, company, employee_ids, cfg):
        """Create warehouses, zones, bins, UoMs, conversions, valuation config."""
        n_warehouses = cfg.get("warehouses", 2)

        # -- Units of Measure --
        uom_map = {}
        for item in _UOM_DATA:
            uom, _ = UnitOfMeasure.objects.get_or_create(
                company=company,
                abbreviation=item["abbr"],
                defaults={
                    "name": item["name"],
                    "name_ar": item["name_ar"],
                    "category": item["category"],
                    "is_base": item.get("is_base", False),
                },
            )
            uom_map[item["abbr"]] = uom
        self.stdout.write(f"   [OK] {len(uom_map):>6,}  Units of Measure")

        conv_count = 0
        for from_a, to_a, factor in _UOM_CONVERSIONS:
            if from_a in uom_map and to_a in uom_map:
                UnitOfMeasureConversion.objects.get_or_create(
                    company=company,
                    from_uom=uom_map[from_a],
                    to_uom=uom_map[to_a],
                    defaults={"factor": Decimal(str(factor))},
                )
                conv_count += 1
        self.stdout.write(f"   [OK] {conv_count:>6,}  UoM Conversions")

        # -- Warehouses + Zones + Bins --
        warehouses, all_zones, all_bins = [], [], []
        for wh_data in _WAREHOUSE_TEMPLATES[:n_warehouses]:
            wh, _ = Warehouse.objects.get_or_create(
                company=company,
                code=wh_data["code"],
                defaults={
                    "name": wh_data["name"],
                    "name_ar": wh_data["name_ar"],
                    "city": wh_data.get("city", ""),
                    "country": wh_data.get("country", ""),
                    "manager_id": random.choice(employee_ids) if employee_ids else None,
                    "is_active": True,
                },
            )
            warehouses.append(wh)
            for z_data in _ZONE_TEMPLATES:
                zone, _ = WarehouseZone.objects.get_or_create(
                    warehouse=wh,
                    code=z_data["code"],
                    defaults={
                        "name": z_data["name"],
                        "name_ar": z_data["name_ar"],
                        "zone_type": z_data["zone_type"],
                        "is_active": True,
                    },
                )
                all_zones.append(zone)
                for b in range(1, random.randint(3, 6) + 1):
                    bc = f"{z_data['code']}-{b:02d}"
                    bin_obj, _ = WarehouseBin.objects.get_or_create(
                        zone=zone,
                        code=bc,
                        defaults={
                            "name": f"Bin {bc}",
                            "max_capacity": Decimal(str(random.randint(100, 1000))),
                            "is_active": True,
                        },
                    )
                    all_bins.append(bin_obj)

        self.stdout.write(f"   [OK] {len(warehouses):>6,}  Warehouses")
        self.stdout.write(f"   [OK] {len(all_zones):>6,}  Warehouse Zones")
        self.stdout.write(f"   [OK] {len(all_bins):>6,}  Warehouse Bins")

        # -- Inventory Valuation Config --
        acct_map = {a.code: a for a in Account.objects.filter(company=company, is_active=True)}
        InventoryValuationConfig.objects.get_or_create(
            company=company,
            defaults={
                "valuation_method": InventoryValuationConfig.ValuationMethod.WEIGHTED_AVG,
                "inventory_account": acct_map.get("1200"),
                "cogs_account": acct_map.get("5100"),
                "grni_account": acct_map.get("1400"),
                "adjustment_account": acct_map.get("6200"),
                "write_off_account": acct_map.get("6300"),
            },
        )
        self.stdout.write("   [OK]      1  Inventory Valuation Config")

        return {
            "warehouse_ids": [w.id for w in warehouses],
        }

    # -- Inventory Transactions ------------------------------------------------

    def _seed_inventory_transactions(self, company, currency, fiscal_year, ctx, cfg):
        """Seed stock items, lots, GRNs, transfers, adjustments, cycle counts, pick/ship."""
        wh_ids = ctx.get("warehouse_ids", [])
        prod_ids = ctx.get("product_ids", [])
        sup_ids = ctx.get("supplier_ids", [])
        cust_ids = ctx.get("customer_ids", [])

        if not wh_ids or not prod_ids:
            self.stdout.write(self.style.WARNING("   [!] No warehouses/products; skipping inventory txns."))
            return

        # Stock Items (product x warehouse snapshots)
        prod_sample = prod_ids[: min(len(prod_ids), 100)]
        stock_objs = []
        for wh_id in wh_ids:
            for pid in prod_sample:
                oh = _rdecimal(10, 500)
                stock_objs.append(
                    StockItem(
                        company=company,
                        product_id=pid,
                        warehouse_id=wh_id,
                        on_hand=oh,
                        allocated=_rdecimal(0, max(1, int(oh / 4))),
                        unit_cost=_rdecimal(5, 200),
                    )
                )
        c = _bulk(StockItem, stock_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Stock Items")

        # Lot Batches
        n_lots = min(len(prod_ids) * 2, 200)
        lot_objs = []
        for _ in range(n_lots):
            mfg = _rdate(365, 30)
            lot_objs.append(
                LotBatch(
                    company=company,
                    product_id=random.choice(prod_ids),
                    lot_number=f"LOT-{_uid()}",
                    manufacture_date=mfg,
                    expiry_date=mfg + timedelta(days=random.randint(180, 730)),
                    supplier_id=random.choice(sup_ids) if sup_ids else None,
                )
            )
        c = _bulk(LotBatch, lot_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Lot Batches")

        # Goods Receipt Notes (linked to existing POs)
        po_list = list(
            PurchaseOrder.objects.filter(company=company).values_list("id", "supplier_id")[: cfg.get("grns", 10) * 2]
        )
        if po_list:
            self._seed_grns(company, wh_ids, prod_ids, po_list, cfg.get("grns", 10))

        # Stock Transfers
        if len(wh_ids) >= 2:
            self._seed_stock_transfers(company, wh_ids, prod_ids, cfg.get("transfers", 5))

        # Stock Adjustments
        self._seed_stock_adjustments(company, wh_ids, prod_ids, cfg.get("adjustments", 3))

        # Cycle Counts
        self._seed_cycle_counts(company, wh_ids, prod_ids, cfg.get("counts", 2))

        # Pick Lists & Shipments
        inv_ids = list(Invoice.objects.filter(company=company).values_list("id", flat=True)[:500])
        self._seed_pick_lists_and_shipments(
            company,
            wh_ids,
            prod_ids,
            cust_ids,
            inv_ids,
            cfg,
        )

        # Reorder Rules
        rr_objs = []
        for wh_id in wh_ids[:2]:
            for pid in prod_ids[: min(len(prod_ids), 50)]:
                rr_objs.append(
                    ReorderRule(
                        company=company,
                        product_id=pid,
                        warehouse_id=wh_id,
                        reorder_point=_rdecimal(10, 50),
                        safety_stock=_rdecimal(5, 20),
                        min_order_qty=Decimal(str(random.randint(1, 10))),
                        max_order_qty=Decimal(str(random.randint(50, 500))),
                        lead_time_days=random.randint(3, 30),
                        preferred_supplier_id=random.choice(sup_ids) if sup_ids else None,
                    )
                )
        c = _bulk(ReorderRule, rr_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Reorder Rules")

        # Stock Movements (append-only ledger)
        self._seed_stock_movements(
            company,
            wh_ids,
            prod_ids,
            min(cfg.get("grns", 10) * 3, 500),
        )

    # -- GRNs -----------------------------------------------------------------

    def _seed_grns(self, company, wh_ids, prod_ids, po_list, count):
        offset = GoodsReceiptNote.objects.count()
        grn_objs = []
        for n in range(count):
            po_id, sup_id = random.choice(po_list)
            grn_objs.append(
                GoodsReceiptNote(
                    company=company,
                    grn_number=f"GRN{offset + n + 1:09d}",
                    receipt_date=_rdate(365),
                    purchase_order_id=po_id,
                    supplier_id=sup_id,
                    warehouse_id=random.choice(wh_ids),
                    status=random.choice(["draft", "confirmed", "confirmed"]),
                )
            )
        created = GoodsReceiptNote.objects.bulk_create(grn_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created):>6,}  Goods Receipt Notes")

        line_objs = []
        for grn in created:
            for _ in range(random.randint(1, 5)):
                qty = Decimal(str(random.randint(5, 100)))
                uc = _rdecimal(5, 200)
                line_objs.append(
                    GoodsReceiptLine(
                        grn=grn,
                        product_id=random.choice(prod_ids),
                        quantity_ordered=qty,
                        quantity_received=qty,
                        quantity_accepted=qty,
                        quantity_rejected=Decimal("0"),
                        unit_cost=uc,
                    )
                )
        c = _bulk(GoodsReceiptLine, line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  GRN Lines")

    # -- Stock Transfers -------------------------------------------------------

    def _seed_stock_transfers(self, company, wh_ids, prod_ids, count):
        offset = StockTransfer.objects.count()
        tr_objs = []
        for n in range(count):
            from_wh, to_wh = random.sample(wh_ids, 2)
            dt = _rdate(365)
            status = random.choice(["draft", "in_transit", "received", "received"])
            tr_objs.append(
                StockTransfer(
                    company=company,
                    transfer_number=f"STX{offset + n + 1:09d}",
                    transfer_date=dt,
                    from_warehouse_id=from_wh,
                    to_warehouse_id=to_wh,
                    status=status,
                    shipped_date=dt if status != "draft" else None,
                    received_date=(dt + timedelta(days=random.randint(1, 5))) if status == "received" else None,
                )
            )
        created = StockTransfer.objects.bulk_create(tr_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created):>6,}  Stock Transfers")

        line_objs = []
        for tr in created:
            for _ in range(random.randint(1, 4)):
                line_objs.append(
                    StockTransferLine(
                        transfer=tr,
                        product_id=random.choice(prod_ids),
                        quantity=Decimal(str(random.randint(1, 50))),
                        unit_cost=_rdecimal(5, 200),
                    )
                )
        c = _bulk(StockTransferLine, line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Transfer Lines")

    # -- Stock Adjustments -----------------------------------------------------

    def _seed_stock_adjustments(self, company, wh_ids, prod_ids, count):
        offset = StockAdjustment.objects.count()
        adj_types = ["gain", "loss", "write_off", "loss", "gain"]
        reasons = [
            "Physical count discrepancy",
            "Damaged goods",
            "Expired stock write-off",
            "Discovered during reorganisation",
            "Packaging error correction",
            "Quality inspection rejection",
            "Supplier over-shipment",
        ]
        adj_objs = []
        for n in range(count):
            adj_objs.append(
                StockAdjustment(
                    company=company,
                    adjustment_number=f"ADJ{offset + n + 1:09d}",
                    adjustment_date=_rdate(365),
                    adjustment_type=random.choice(adj_types),
                    warehouse_id=random.choice(wh_ids),
                    reason=random.choice(reasons),
                    status=random.choice(["draft", "pending", "approved", "approved"]),
                )
            )
        created = StockAdjustment.objects.bulk_create(adj_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created):>6,}  Stock Adjustments")

        line_objs = []
        for adj in created:
            for _ in range(random.randint(1, 3)):
                line_objs.append(
                    StockAdjustmentLine(
                        adjustment=adj,
                        product_id=random.choice(prod_ids),
                        quantity=Decimal(str(random.randint(1, 20))),
                        unit_cost=_rdecimal(5, 200),
                    )
                )
        c = _bulk(StockAdjustmentLine, line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Adjustment Lines")

    # -- Cycle Counts ----------------------------------------------------------

    def _seed_cycle_counts(self, company, wh_ids, prod_ids, count):
        offset = CycleCount.objects.count()
        cc_objs = []
        for n in range(count):
            cc_objs.append(
                CycleCount(
                    company=company,
                    count_number=f"CC{offset + n + 1:09d}",
                    count_date=_rdate(365),
                    warehouse_id=random.choice(wh_ids),
                    status=random.choice(["planned", "in_progress", "completed", "completed"]),
                )
            )
        created = CycleCount.objects.bulk_create(cc_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created):>6,}  Cycle Counts")

        line_objs = []
        for cc in created:
            for _ in range(random.randint(3, 10)):
                sys_qty = _rdecimal(10, 200)
                counted = sys_qty + Decimal(str(random.randint(-5, 5)))
                line_objs.append(
                    CycleCountLine(
                        cycle_count=cc,
                        product_id=random.choice(prod_ids),
                        system_quantity=sys_qty,
                        counted_quantity=max(Decimal("0"), counted),
                    )
                )
        c = _bulk(CycleCountLine, line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Cycle Count Lines")

    # -- Pick Lists & Shipments ------------------------------------------------

    def _seed_pick_lists_and_shipments(self, company, wh_ids, prod_ids, cust_ids, inv_ids, cfg):
        # --- Pick Lists ---
        n_picks = cfg.get("grns", 10)
        offset_pk = PickList.objects.count()
        pk_objs = []
        for n in range(n_picks):
            pk_objs.append(
                PickList(
                    company=company,
                    pick_number=f"PK{offset_pk + n + 1:09d}",
                    pick_date=_rdate(365),
                    warehouse_id=random.choice(wh_ids),
                    invoice_id=random.choice(inv_ids) if inv_ids else None,
                    status=random.choice(["draft", "in_progress", "picked", "picked"]),
                )
            )
        created_pks = PickList.objects.bulk_create(pk_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created_pks):>6,}  Pick Lists")

        pk_line_objs = []
        for pk in created_pks:
            for _ in range(random.randint(1, 5)):
                rq = Decimal(str(random.randint(1, 20)))
                pk_line_objs.append(
                    PickListLine(
                        pick_list=pk,
                        product_id=random.choice(prod_ids),
                        quantity_requested=rq,
                        quantity_picked=rq if pk.status == "picked" else _rdecimal(0, max(1, int(rq))),
                    )
                )
        c = _bulk(PickListLine, pk_line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Pick List Lines")

        # --- Shipment Notes ---
        n_ships = max(1, n_picks * 2 // 3)
        offset_sh = ShipmentNote.objects.count()
        sh_objs = []
        for n in range(n_ships):
            sh_objs.append(
                ShipmentNote(
                    company=company,
                    shipment_number=f"SHP{offset_sh + n + 1:09d}",
                    shipment_date=_rdate(365),
                    warehouse_id=random.choice(wh_ids),
                    customer_id=random.choice(cust_ids) if cust_ids else None,
                    carrier_name=random.choice(_CARRIER_NAMES),
                    tracking_number=f"TRK-{_uid('', 12)}",
                    status=random.choice(["draft", "shipped", "delivered", "delivered"]),
                )
            )
        created_shs = ShipmentNote.objects.bulk_create(sh_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created_shs):>6,}  Shipment Notes")

        sh_line_objs = []
        for sh in created_shs:
            for _ in range(random.randint(1, 4)):
                sh_line_objs.append(
                    ShipmentLine(
                        shipment=sh,
                        product_id=random.choice(prod_ids),
                        quantity=Decimal(str(random.randint(1, 30))),
                    )
                )
        c = _bulk(ShipmentLine, sh_line_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Shipment Lines")

    # -- Stock Movements -------------------------------------------------------

    def _seed_stock_movements(self, company, wh_ids, prod_ids, count):
        """Append-only stock movement ledger entries."""
        mvmt_types = [
            "opening",
            "purchase_receipt",
            "return_in",
            "transfer_in",
            "adjustment_gain",
            "sales_issue",
            "transfer_out",
            "adjustment_loss",
            "write_off",
        ]
        objs = []
        for _ in range(count):
            qty = _rdecimal(1, 100)
            uc = _rdecimal(5, 200)
            objs.append(
                StockMovement(
                    company=company,
                    movement_date=timezone.now() - timedelta(days=random.randint(1, 365)),
                    movement_type=random.choice(mvmt_types),
                    product_id=random.choice(prod_ids),
                    warehouse_id=random.choice(wh_ids),
                    quantity=qty,
                    unit_cost=uc,
                    total_cost=round(qty * uc, 4),
                    description=f"Auto-seeded movement {_uid()}",
                )
            )
        c = _bulk(StockMovement, objs)
        self.stdout.write(f"   [OK] {c:>6,}  Stock Movements")

    # =========================================================================
    # FIXED ASSETS  (categories, register, depreciation, maintenance, JEs)
    # =========================================================================

    def _seed_fixed_assets_data(self, company, currency, fiscal_year, ctx, cfg):
        """Seed fixed assets with depreciation schedules and journal entries."""
        from erp.setup_defaults import ASSET_CATEGORIES

        dept_ids = list(Department.objects.filter(company=company).values_list("id", flat=True))
        emp_ids = ctx.get("employee_ids", [])
        sup_ids = ctx.get("supplier_ids", [])
        n_assets = cfg.get("assets", 5)

        # -- Ensure AssetCategories (mirrors erp_first_setup) --
        acct_map = {a.code: a for a in Account.objects.filter(company=company, is_active=True)}
        method_map = {
            "STRAIGHT_LINE": AssetCategory.DepreciationMethod.STRAIGHT_LINE,
            "DECLINING_BALANCE": AssetCategory.DepreciationMethod.DECLINING_BALANCE,
        }
        cat_by_code = {}
        for item in ASSET_CATEGORIES:
            cat, _ = AssetCategory.objects.get_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": item["name"].get("en", ""),
                    "name_ar": item["name"].get("ar", ""),
                    "depreciation_method": method_map.get(
                        item["method"],
                        AssetCategory.DepreciationMethod.STRAIGHT_LINE,
                    ),
                    "useful_life_months": item["useful_life"],
                    "salvage_value_percent": item["salvage_pct"],
                    "asset_account": acct_map.get(item["asset_acct"]),
                    "depreciation_expense_account": acct_map.get(item["depr_exp_acct"]),
                    "accumulated_depreciation_account": acct_map.get(item["accum_depr_acct"]),
                    "disposal_gain_account": acct_map.get(item["disposal_gain_acct"]),
                    "disposal_loss_account": acct_map.get(item["disposal_loss_acct"]),
                    "acquisition_source_account": acct_map.get(item["acq_source_acct"]),
                    "disposal_proceeds_account": acct_map.get(item["disposal_proceeds_acct"]),
                    "revaluation_surplus_account": acct_map.get(item["reval_surplus_acct"]),
                },
            )
            cat_by_code[item["code"]] = cat
        self.stdout.write(f"   [OK] {len(cat_by_code):>6,}  Asset Categories")

        if not cat_by_code:
            self.stdout.write("   [!] No asset categories; skipping fixed assets.")
            return

        # -- Fixed Asset Register --
        offset = FixedAsset.objects.count()
        asset_objs = []
        templates = _ASSET_TEMPLATES * ((n_assets // len(_ASSET_TEMPLATES)) + 1)
        templates = templates[:n_assets]

        locations = ["Head Office", "Warehouse", "Branch Office", "Factory Floor", "Data Center"]

        for n, (name, name_ar, cat_code, lo, hi) in enumerate(templates):
            cat = cat_by_code.get(cat_code)
            if not cat:
                continue
            acq_cost = _rdecimal(lo, hi)
            salvage = round(acq_cost * cat.salvage_value_percent / Decimal("100"), 2)
            acq_date = _rdate(730, 60)
            status = random.choice(["active", "active", "active", "draft"])
            months_held = max(1, (date.today() - acq_date).days // 30)

            if status == "active" and cat.useful_life_months > 0:
                monthly_depr = round(
                    (acq_cost - salvage) / cat.useful_life_months,
                    2,
                )
                accum_depr = min(
                    round(monthly_depr * months_held, 2),
                    acq_cost - salvage,
                )
            else:
                accum_depr = Decimal("0")

            book_val = acq_cost - accum_depr

            asset_objs.append(
                FixedAsset(
                    company=company,
                    asset_number=f"FA{offset + n + 1:09d}",
                    name=name,
                    name_ar=name_ar,
                    description=f"Auto-seeded fixed asset: {name}",
                    category=cat,
                    acquisition_date=acq_date,
                    acquisition_cost=acq_cost,
                    currency=currency,
                    supplier_id=random.choice(sup_ids) if sup_ids else None,
                    department_id=random.choice(dept_ids) if dept_ids else None,
                    location=random.choice(locations),
                    custodian_id=random.choice(emp_ids) if emp_ids else None,
                    serial_number=f"SN-{_uid('', 10)}",
                    depreciation_method=cat.depreciation_method,
                    useful_life_months=cat.useful_life_months,
                    salvage_value=salvage,
                    depreciation_start_date=acq_date,
                    accumulated_depreciation=accum_depr,
                    current_book_value=book_val,
                    status=status,
                )
            )

        created_assets = FixedAsset.objects.bulk_create(asset_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created_assets):>6,}  Fixed Assets")

        # -- Depreciation Schedules (monthly rows for active assets) --
        depr_objs = []
        for asset in created_assets:
            if asset.status != "active" or asset.useful_life_months == 0:
                continue
            months_held = max(1, (date.today() - asset.acquisition_date).days // 30)
            monthly = round(
                (asset.acquisition_cost - asset.salvage_value) / asset.useful_life_months,
                2,
            )
            if monthly <= 0:
                continue
            running_accum = Decimal("0")
            for m in range(min(months_held, asset.useful_life_months)):
                dep_amt = min(
                    monthly,
                    asset.acquisition_cost - asset.salvage_value - running_accum,
                )
                if dep_amt <= 0:
                    break
                running_accum += dep_amt
                # Approximate period end-date
                pdate = asset.depreciation_start_date + timedelta(days=30 * (m + 1))
                depr_objs.append(
                    DepreciationSchedule(
                        asset=asset,
                        period_date=pdate,
                        depreciation_amount=dep_amt,
                        accumulated_total=running_accum,
                        book_value_after=asset.acquisition_cost - running_accum,
                        status="posted" if m < months_held - 1 else "scheduled",
                    )
                )
        c = _bulk(DepreciationSchedule, depr_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Depreciation Schedules")

        # -- Maintenance Logs --
        maint_types = ["preventive", "corrective", "inspection", "upgrade", "calibration"]
        vendors = [
            "Al-Faris Maintenance",
            "TechCare Services",
            "Gulf Facility Management",
            "ProFix Solutions",
            "National Maintenance Co.",
        ]
        maint_objs = []
        for asset in created_assets:
            if asset.status != "active":
                continue
            for _ in range(random.randint(0, 3)):
                sched = _rdate(365, 0)
                completed = random.random() > 0.3
                maint_objs.append(
                    AssetMaintenanceLog(
                        asset=asset,
                        maintenance_type=random.choice(maint_types),
                        description=f"Routine maintenance for {asset.name}",
                        scheduled_date=sched,
                        completion_date=(sched + timedelta(days=random.randint(0, 7))) if completed else None,
                        cost=_rdecimal(100, 5000),
                        vendor=random.choice(vendors),
                        performed_by_id=random.choice(emp_ids) if emp_ids else None,
                        status="completed" if completed else random.choice(["scheduled", "in_progress"]),
                    )
                )
        c = _bulk(AssetMaintenanceLog, maint_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Maintenance Logs")

        # -- Asset Transfers (departmental reassignments) --
        active_assets = [a for a in created_assets if a.status == "active"]
        transfer_objs = []
        if len(dept_ids) >= 2:
            for asset in active_assets[: max(1, len(active_assets) // 5)]:
                from_dept, to_dept = random.sample(dept_ids, 2)
                transfer_objs.append(
                    AssetTransfer(
                        asset=asset,
                        transfer_date=_rdate(180, 0),
                        from_department_id=from_dept,
                        to_department_id=to_dept,
                        from_location=random.choice(locations),
                        to_location=random.choice(locations),
                        from_custodian_id=random.choice(emp_ids) if emp_ids else None,
                        to_custodian_id=random.choice(emp_ids) if emp_ids else None,
                        reason="Departmental reorganisation",
                    )
                )
        c = _bulk(AssetTransfer, transfer_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Asset Transfers")

        # -- Journal Entries for asset acquisitions & depreciation --
        self._seed_asset_journal_entries(
            company,
            fiscal_year,
            created_assets,
            cat_by_code,
            acct_map,
        )

    # -- Asset Journal Entries -------------------------------------------------

    def _seed_asset_journal_entries(self, company, fiscal_year, assets, cat_by_code, acct_map):
        """Create balanced JEs for asset acquisitions and accumulated depreciation."""
        je_objs = []
        je_offset = JournalEntry.objects.filter(company=company).count()
        idx = 0

        # Track which assets produce which JE types for line creation
        acq_assets = []  # assets with acquisition JEs
        dep_assets = []  # assets with depreciation JEs

        for asset in assets:
            cat = cat_by_code.get(asset.category.code, asset.category)
            asset_acct = cat.asset_account
            source_acct = cat.acquisition_source_account
            depr_exp_acct = cat.depreciation_expense_account
            accum_depr_acct = cat.accumulated_depreciation_account

            if not asset_acct or not source_acct:
                continue

            # Acquisition JE
            je_objs.append(
                JournalEntry(
                    company=company,
                    entry_number=f"FAACQ{je_offset + idx + 1:09d}",
                    entry_date=asset.acquisition_date,
                    entry_type="manual",
                    description=f"Acquisition of fixed asset: {asset.name}",
                    reference=asset.asset_number,
                    fiscal_year=fiscal_year,
                    total_debit=asset.acquisition_cost,
                    total_credit=asset.acquisition_cost,
                    status="posted",
                )
            )
            acq_assets.append(asset)
            idx += 1

            # Aggregated depreciation JE
            if asset.status == "active" and asset.accumulated_depreciation > 0 and depr_exp_acct and accum_depr_acct:
                je_objs.append(
                    JournalEntry(
                        company=company,
                        entry_number=f"FADEP{je_offset + idx + 1:09d}",
                        entry_date=date.today(),
                        entry_type="adjustment",
                        description=f"Accumulated depreciation \u2013 {asset.name}",
                        reference=asset.asset_number,
                        fiscal_year=fiscal_year,
                        total_debit=asset.accumulated_depreciation,
                        total_credit=asset.accumulated_depreciation,
                        status="posted",
                    )
                )
                dep_assets.append(asset)
                idx += 1

        if not je_objs:
            self.stdout.write("   [OK]      0  Asset Journal Entries")
            return

        created_jes = JournalEntry.objects.bulk_create(je_objs, batch_size=2000)
        self.stdout.write(f"   [OK] {len(created_jes):>6,}  Asset Journal Entries")

        # Build JE lines by consuming created JEs in order
        jel_objs = []
        je_iter = iter(created_jes)

        for asset in acq_assets:
            cat = cat_by_code.get(asset.category.code, asset.category)
            je_acq = next(je_iter)
            jel_objs.extend(
                [
                    JournalEntryLine(
                        journal_entry=je_acq,
                        account=cat.asset_account,
                        description=f"Fixed asset \u2013 {asset.name}",
                        debit_amount=asset.acquisition_cost,
                        credit_amount=Decimal("0"),
                        reference_type="FixedAsset",
                        reference_id=asset.pk,
                    ),
                    JournalEntryLine(
                        journal_entry=je_acq,
                        account=cat.acquisition_source_account,
                        description=f"Acquisition source \u2013 {asset.name}",
                        debit_amount=Decimal("0"),
                        credit_amount=asset.acquisition_cost,
                        reference_type="FixedAsset",
                        reference_id=asset.pk,
                    ),
                ]
            )

            # Consume depreciation JE if this asset has one
            if asset in dep_assets:
                je_dep = next(je_iter)
                jel_objs.extend(
                    [
                        JournalEntryLine(
                            journal_entry=je_dep,
                            account=cat.depreciation_expense_account,
                            description=f"Depreciation expense \u2013 {asset.name}",
                            debit_amount=asset.accumulated_depreciation,
                            credit_amount=Decimal("0"),
                            reference_type="FixedAsset",
                            reference_id=asset.pk,
                        ),
                        JournalEntryLine(
                            journal_entry=je_dep,
                            account=cat.accumulated_depreciation_account,
                            description=f"Accumulated depreciation \u2013 {asset.name}",
                            debit_amount=Decimal("0"),
                            credit_amount=asset.accumulated_depreciation,
                            reference_type="FixedAsset",
                            reference_id=asset.pk,
                        ),
                    ]
                )

        c = _bulk(JournalEntryLine, jel_objs)
        self.stdout.write(f"   [OK] {c:>6,}  Asset JE Lines")
