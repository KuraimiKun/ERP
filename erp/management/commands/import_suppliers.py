"""
Management command: import_suppliers

Imports the synthetic supplier/procurement dataset into the ERP system
for ML model testing (Late-Payment Prediction, Demand Forecasting).

Expected CSV files in datasets/:
  - supplier_procurement_suppliers.csv   (~80 rows)
  - supplier_procurement_orders.csv      (~3,000 rows)

Usage:
    python manage.py import_suppliers
    python manage.py import_suppliers --tenant erp_pg_alkuraimi --company-id 1
    python manage.py import_suppliers --limit 1000
    python manage.py import_suppliers --clear
"""

import random
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Company,
    Currency,
    Employee,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
)

DATASET_DIR = Path(__file__).resolve().parents[3] / "datasets"


class Command(BaseCommand):
    help = "Import synthetic supplier & purchase-order datasets into ERP for ML testing."

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
            help="Max number of purchase orders to import.",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete previously imported supplier/PO data before importing.",
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

        # Reference data
        self.currency = self._ensure_currency()
        self.employees = self._get_employees()

        # Optional clear
        if options["clear"]:
            self._clear_data()

        # ---------- Load CSVs ----------
        sup_csv = DATASET_DIR / "supplier_procurement_suppliers.csv"
        po_csv = DATASET_DIR / "supplier_procurement_orders.csv"
        for p in [sup_csv, po_csv]:
            if not p.exists():
                raise CommandError(f"Dataset not found: {p}\nRun: python datasets/generate_synthetic.py")

        df_sup = pd.read_csv(sup_csv)
        df_po = pd.read_csv(po_csv)
        if options["limit"]:
            df_po = df_po.head(options["limit"])
        self.stdout.write(f"Loaded {len(df_sup)} suppliers, {len(df_po)} purchase orders.")

        # ---------- Import ----------
        self.stdout.write("\n[Phase 1] Importing suppliers …")
        supplier_map = self._import_suppliers(df_sup)

        self.stdout.write("\n[Phase 2] Importing purchase orders …")
        self._import_purchase_orders(df_po, supplier_map)

        self.stdout.write(self.style.SUCCESS("\n✓ Supplier/PO import complete!"))
        self._print_summary()

    # ==================================================================
    def _ensure_currency(self):
        cur, _ = Currency.objects.using(self.db).get_or_create(
            code="USD",
            defaults={"name": "US Dollar", "symbol": "$",
                       "is_base": True, "exchange_rate": 1},
        )
        return cur

    def _get_employees(self):
        emps = list(
            Employee.objects.using(self.db).filter(
                company=self.company, employment_status='active',
            )[:50]
        )
        return emps if emps else None

    def _clear_data(self):
        self.stdout.write(self.style.WARNING("Clearing previously imported supplier/PO data …"))
        # Lines & invoices cascade from POs
        cnt_po = PurchaseOrder.all_objects.using(self.db).filter(
            po_number__startswith="PO-"
        ).delete()[0]
        cnt_sup = Supplier.all_objects.using(self.db).filter(
            supplier_id__startswith="SUP-"
        ).delete()[0]
        self.stdout.write(f"  POs deleted (cascade): {cnt_po}")
        self.stdout.write(f"  Suppliers deleted:     {cnt_sup}")

    # ==================================================================
    def _import_suppliers(self, df):
        """Import suppliers, return {csv_supplier_id: Supplier instance}."""
        existing = set(
            Supplier.objects.using(self.db)
            .filter(supplier_id__startswith="SUP-")
            .values_list("supplier_id", flat=True)
        )
        supplier_map = {}
        created = 0
        skipped = 0

        for _, row in df.iterrows():
            sid = row['supplier_id']
            if sid in existing:
                supplier_map[sid] = Supplier.objects.using(self.db).get(supplier_id=sid)
                skipped += 1
                continue

            sup = Supplier(
                company=self.company,
                supplier_id=sid,
                supplier_type=row['supplier_type'],
                name=row['name'],
                city=row.get('city', ''),
                country='Oman',
                payment_terms=int(row.get('payment_terms', 30)),
                rating=int(row.get('rating', 3)),
                credit_limit=Decimal(str(row.get('avg_amount', 5000))) * 10,
                currency=self.currency,
                is_active=True,
                email=f"{sid.lower().replace('-', '')}@example.com",
                phone=f"+968-{random.randint(90000000, 99999999)}",
            )
            sup.save(using=self.db)
            supplier_map[sid] = sup
            created += 1

        self.stdout.write(f"  Created: {created}, Skipped (existing): {skipped}")
        return supplier_map

    # ==================================================================
    def _import_purchase_orders(self, df, supplier_map):
        existing = set(
            PurchaseOrder.objects.using(self.db)
            .filter(po_number__startswith="PO-")
            .values_list("po_number", flat=True)
        )

        created = 0
        skipped = 0
        lines_created = 0

        for _, row in df.iterrows():
            po_num = row['po_number']
            if po_num in existing:
                skipped += 1
                continue

            supplier = supplier_map.get(row['supplier_id'])
            if not supplier:
                skipped += 1
                continue

            # Map CSV status to model Status choices
            status_map = {
                'draft': 'draft', 'pending': 'pending', 'approved': 'approved',
                'sent': 'sent', 'partial': 'partial', 'received': 'received',
                'cancelled': 'cancelled',
            }
            status = status_map.get(row['status'], 'draft')

            po = PurchaseOrder(
                company=self.company,
                supplier=supplier,
                po_number=po_num,
                po_date=pd.to_datetime(row['order_date']).date(),
                expected_date=pd.to_datetime(row['expected_date']).date() if pd.notna(row.get('expected_date')) else None,
                currency=self.currency,
                subtotal=Decimal(str(row.get('subtotal', 0))),
                tax_amount=Decimal(str(row.get('tax_amount', 0))),
                total_amount=Decimal(str(row.get('total_amount', 0))),
                paid_amount=Decimal(str(row.get('paid_amount', 0))),
                balance_due=Decimal(str(row.get('balance_due', 0))),
                status=status,
                notes=f"Imported from synthetic dataset. Lead time: {row.get('lead_time_days', '')} days",
            )

            # Set approved_by for approved+ orders
            if status in ('approved', 'sent', 'partial', 'received') and self.employees:
                po.approved_by = random.choice(self.employees)
                po.approval_date = timezone.now()

            po.save(using=self.db)
            created += 1

            # Create PO lines
            n_lines = int(row.get('n_lines', 1))
            remaining = Decimal(str(row.get('subtotal', 0)))
            for i in range(n_lines):
                if i == n_lines - 1:
                    line_total = remaining
                else:
                    line_total = (remaining / (n_lines - i)).quantize(Decimal('0.01'))
                remaining -= line_total

                qty = Decimal(str(random.randint(1, 20)))
                unit_price = (line_total / qty).quantize(Decimal('0.01')) if qty else line_total

                pol = PurchaseOrderLine(
                    purchase_order=po,
                    description=f"Line item {i + 1} for {po_num}",
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                    tax_amount=(line_total * Decimal('0.05')).quantize(Decimal('0.01')),
                )
                if status in ('received', 'partial') and i == 0:
                    pol.received_quantity = qty
                pol.save(using=self.db)
                lines_created += 1

            if created % 500 == 0:
                self.stdout.write(f"  … {created} purchase orders imported")

        self.stdout.write(f"  POs created: {created}, Skipped: {skipped}")
        self.stdout.write(f"  PO lines created: {lines_created}")

    # ==================================================================
    def _print_summary(self):
        suppliers = Supplier.objects.using(self.db).filter(
            company=self.company, supplier_id__startswith="SUP-"
        ).count()
        pos = PurchaseOrder.objects.using(self.db).filter(
            company=self.company, po_number__startswith="PO-"
        ).count()
        lines = PurchaseOrderLine.objects.using(self.db).filter(
            purchase_order__po_number__startswith="PO-"
        ).count()

        self.stdout.write("\n  Summary:")
        self.stdout.write(f"    Suppliers:         {suppliers}")
        self.stdout.write(f"    Purchase Orders:   {pos}")
        self.stdout.write(f"    PO Lines:          {lines}")
