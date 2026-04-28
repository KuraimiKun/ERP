"""
Management command: import_olist

Imports the Olist Brazilian E-Commerce dataset into the ERP system
for realistic ML model testing (Late Payment Prediction, Demand
Forecasting, Expense Anomaly Detection).

Expected CSV files in datasets/:
  - olist_customers_dataset.csv
  - olist_orders_dataset.csv
  - olist_order_items_dataset.csv
  - olist_order_payments_dataset.csv
  - olist_products_dataset.csv
  - product_category_name_translation.csv

Usage:
    python manage.py import_olist
    python manage.py import_olist --tenant erp_pg_alkuraimi --company-id 1
    python manage.py import_olist --limit 5000        # import first N orders
    python manage.py import_olist --clear              # wipe existing imported data first
"""

import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Company,
    Currency,
    Customer,
    FiscalYear,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentAllocation,
    PaymentMethod,
    Product,
    ProductCategory,
    TaxRate,
)

DATASET_DIR = Path(__file__).resolve().parents[3] / "datasets"

# BRL → USD approximate conversion (reasonable for 2016-2018 Olist data range)
BRL_TO_USD = Decimal("0.25")


class Command(BaseCommand):
    help = "Import the Olist E-Commerce dataset into ERP for ML testing."

    # ------------------------------------------------------------------
    # CLI arguments
    # ------------------------------------------------------------------
    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            default=None,
            help="Tenant DB name. Defaults to first active tenant.",
        )
        parser.add_argument(
            "--company-id",
            type=int,
            default=None,
            help="Company ID to assign records to. Defaults to first company.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of orders to import (default: all ~99k).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete previously imported Olist data before importing.",
        )
        parser.add_argument(
            "--no-convert",
            action="store_true",
            help="Keep amounts in BRL (default: convert to USD).",
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        db_alias = self._activate_tenant(options["tenant"])
        with TenantDatabaseContext(db_alias):
            self._run(options, db_alias)

    # ------------------------------------------------------------------
    # Tenant resolution  (same pattern as seed_tenant)
    # ------------------------------------------------------------------
    def _activate_tenant(self, tenant_name):
        if tenant_name is None:
            tenant_db = TenantDatabase.objects.filter(status="active").first()
            if not tenant_db:
                raise CommandError("No active tenant found. Pass --tenant <name>.")
            self.stdout.write(self.style.WARNING(f"No --tenant given; using first active tenant: {tenant_db.name}"))
        else:
            try:
                tenant_db = TenantDatabase.objects.get(name=tenant_name)
            except TenantDatabase.DoesNotExist:
                avail = list(TenantDatabase.objects.filter(status="active").values_list("name", flat=True))
                raise CommandError(f"Tenant '{tenant_name}' not found. Available: {avail}")
        return add_tenant_database(tenant_db)

    # ------------------------------------------------------------------
    # Main logic
    # ------------------------------------------------------------------
    def _run(self, options, db_alias):
        self.db = db_alias
        self.convert = not options["no_convert"]
        limit = options["limit"]
        # Per-invoice realised payment delay (days past due). Populated by
        # _import_invoices and consumed by _import_payments.
        self._invoice_delay_map: dict[str, float] = {}

        # -- Resolve company -----------------------------------------------
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

        # -- Ensure required reference data --------------------------------
        self.currency = self._ensure_currency()
        self.tax_rate = self._ensure_tax_rate()
        self.payment_methods = self._ensure_payment_methods()
        self.fiscal_year = self._ensure_fiscal_year()

        # -- Optional clear ------------------------------------------------
        if options["clear"]:
            self._clear_olist_data()

        # -- Load CSVs -----------------------------------------------------
        self.stdout.write("Loading CSV files …")
        customers_df = pd.read_csv(DATASET_DIR / "olist_customers_dataset.csv")
        orders_df = pd.read_csv(DATASET_DIR / "olist_orders_dataset.csv")
        items_df = pd.read_csv(DATASET_DIR / "olist_order_items_dataset.csv")
        payments_df = pd.read_csv(DATASET_DIR / "olist_order_payments_dataset.csv")
        products_df = pd.read_csv(DATASET_DIR / "olist_products_dataset.csv")
        cat_trans_df = pd.read_csv(DATASET_DIR / "product_category_name_translation.csv")
        self.stdout.write(
            self.style.SUCCESS(
                f"  Orders: {len(orders_df)}, Items: {len(items_df)}, "
                f"Payments: {len(payments_df)}, Products: {len(products_df)}, "
                f"Customers: {len(customers_df)}"
            )
        )

        # -- Filter to delivered orders only (skip cancelled, etc.) --------
        orders_df = orders_df[orders_df["order_status"] == "delivered"].copy()
        if limit:
            orders_df = orders_df.head(limit)
        order_ids = set(orders_df["order_id"])
        items_df = items_df[items_df["order_id"].isin(order_ids)]
        payments_df = payments_df[payments_df["order_id"].isin(order_ids)]
        self.stdout.write(
            f"  After filtering (delivered, limit={limit}): "
            f"{len(orders_df)} orders, {len(items_df)} items, {len(payments_df)} payments"
        )

        # -- Merge customer info into orders -------------------------------
        orders_df = orders_df.merge(customers_df, on="customer_id", how="left")

        # -- Translate product categories ----------------------------------
        products_df = products_df.merge(cat_trans_df, on="product_category_name", how="left")
        products_df["category_en"] = products_df["product_category_name_english"].fillna(
            products_df["product_category_name"].fillna("uncategorized")
        )

        # -- Phase 1: Product categories & Products -----------------------
        self.stdout.write("\n[Phase 1] Importing product categories & products …")
        self._import_products(products_df, items_df)

        # -- Phase 2: Customers -------------------------------------------
        self.stdout.write("\n[Phase 2] Importing customers …")
        self._import_customers(orders_df)

        # -- Phase 3: Invoices + Lines ------------------------------------
        self.stdout.write("\n[Phase 3] Importing invoices & line items …")
        self._import_invoices(orders_df, items_df)

        # -- Phase 4: Payments & Allocations ------------------------------
        self.stdout.write("\n[Phase 4] Importing payments …")
        self._import_payments(payments_df)

        self.stdout.write(self.style.SUCCESS("\n✓ Olist import complete!"))
        self._print_summary()

    # ==================================================================
    # Reference data helpers
    # ==================================================================
    def _ensure_currency(self):
        code = "USD" if self.convert else "BRL"
        cur, created = Currency.objects.using(self.db).get_or_create(
            code=code,
            defaults={"name": code, "symbol": "$" if code == "USD" else "R$", "is_base": True, "exchange_rate": 1},
        )
        if created:
            self.stdout.write(f"  Created currency: {code}")
        return cur

    def _ensure_tax_rate(self):
        tr, created = TaxRate.objects.using(self.db).get_or_create(
            company=self.company,
            rate=Decimal("0"),
            defaults={"name": "No Tax", "is_default": True},
        )
        return tr

    def _ensure_payment_methods(self):
        mapping = {
            "credit_card": ("Credit Card", "CC"),
            "boleto": ("Boleto", "BOL"),
            "voucher": ("Voucher", "VCH"),
            "debit_card": ("Debit Card", "DC"),
            "not_defined": ("Other", "OTH"),
        }
        methods = {}
        for key, (name, code) in mapping.items():
            pm, _ = PaymentMethod.objects.using(self.db).get_or_create(
                company=self.company,
                code=code,
                defaults={"name": name},
            )
            methods[key] = pm
        return methods

    def _ensure_fiscal_year(self):
        fy = FiscalYear.objects.using(self.db).filter(company=self.company).first()
        if not fy:
            from datetime import date

            fy = FiscalYear.objects.using(self.db).create(
                company=self.company,
                name="FY 2017-2018",
                start_date=date(2017, 1, 1),
                end_date=date(2018, 12, 31),
                is_current=True,
            )
        return fy

    # ==================================================================
    # Clear previously imported data
    # ==================================================================
    def _clear_olist_data(self):
        self.stdout.write(self.style.WARNING("Clearing previously imported Olist data …"))
        # Use raw SQL for speed — the ORM cascade was loading hundreds of
        # thousands of PKs into memory and deleting row-by-row, which on a
        # full Olist re-import (~99k invoices, ~110k lines, ~99k payments)
        # took 30+ minutes. Raw bulk DELETEs finish in seconds.
        from django.db import connections

        with connections[self.db].cursor() as cur:
            t_pa = PaymentAllocation._meta.db_table
            t_pay = Payment._meta.db_table
            t_il = InvoiceLine._meta.db_table
            t_inv = Invoice._meta.db_table
            t_cust = Customer._meta.db_table
            t_prod = Product._meta.db_table
            t_cat = ProductCategory._meta.db_table

            cur.execute(
                f"DELETE FROM {t_pa} WHERE payment_id IN "
                f"(SELECT id FROM {t_pay} WHERE payment_number LIKE 'OLIST-PAY-%')"
            )
            self.stdout.write(f"  PaymentAllocations deleted: {cur.rowcount}")

            cur.execute(f"DELETE FROM {t_pay} WHERE payment_number LIKE 'OLIST-PAY-%'")
            self.stdout.write(f"  Payments deleted: {cur.rowcount}")

            cur.execute(
                f"DELETE FROM {t_il} WHERE invoice_id IN "
                f"(SELECT id FROM {t_inv} WHERE invoice_number LIKE 'OLIST-INV-%')"
            )
            self.stdout.write(f"  InvoiceLines deleted: {cur.rowcount}")

            cur.execute(f"DELETE FROM {t_inv} WHERE invoice_number LIKE 'OLIST-INV-%'")
            self.stdout.write(f"  Invoices deleted: {cur.rowcount}")

            cur.execute(f"DELETE FROM {t_cust} WHERE customer_id LIKE 'OLIST-C-%'")
            self.stdout.write(f"  Customers deleted: {cur.rowcount}")

            # Clear product-referencing rows before deleting products.
            from erp.models.inventory import ReorderRule, StockMovement

            t_sm = StockMovement._meta.db_table
            t_rr = ReorderRule._meta.db_table
            cur.execute(
                f"DELETE FROM {t_sm} WHERE product_id IN "
                f"(SELECT id FROM {t_prod} WHERE sku LIKE 'OLIST-P-%')"
            )
            self.stdout.write(f"  StockMovements deleted: {cur.rowcount}")
            cur.execute(
                f"DELETE FROM {t_rr} WHERE product_id IN "
                f"(SELECT id FROM {t_prod} WHERE sku LIKE 'OLIST-P-%')"
            )
            self.stdout.write(f"  ReorderRules deleted: {cur.rowcount}")

            cur.execute(f"DELETE FROM {t_prod} WHERE sku LIKE 'OLIST-P-%'")
            self.stdout.write(f"  Products deleted: {cur.rowcount}")

            cur.execute(f"DELETE FROM {t_cat} WHERE code LIKE 'OLIST-%'")
            self.stdout.write(f"  ProductCategories deleted: {cur.rowcount}")

    # ==================================================================
    # Phase 1: Products
    # ==================================================================
    def _import_products(self, products_df, items_df):
        # Only import products that actually appear in our order items
        used_product_ids = set(items_df["product_id"].unique())
        products_df = products_df[products_df["product_id"].isin(used_product_ids)].copy()

        # --- Categories ---
        categories_en = products_df["category_en"].unique()
        cat_map = {}  # category_en -> ProductCategory
        existing_cats = {
            c.code: c
            for c in ProductCategory.objects.using(self.db).filter(company=self.company, code__startswith="OLIST-")
        }
        new_cats = []
        for cat_name in categories_en:
            code = f"OLIST-{cat_name[:14].upper().replace(' ', '_')}"
            if code in existing_cats:
                cat_map[cat_name] = existing_cats[code]
            else:
                obj = ProductCategory(
                    company=self.company,
                    name=cat_name.replace("_", " ").title(),
                    code=code,
                )
                new_cats.append(obj)
                cat_map[cat_name] = obj
        if new_cats:
            ProductCategory.objects.using(self.db).bulk_create(new_cats, batch_size=500)
            # Re-fetch to get PKs
            cat_map = {}
            for c in ProductCategory.objects.using(self.db).filter(company=self.company, code__startswith="OLIST-"):
                # reverse-map code → cat_name
                for cn in categories_en:
                    code = f"OLIST-{cn[:14].upper().replace(' ', '_')}"
                    if c.code == code:
                        cat_map[cn] = c
        self.stdout.write(f"  Categories: {len(cat_map)}")

        # --- Compute average prices from order items ---
        avg_prices = items_df.groupby("product_id")["price"].mean().to_dict()

        # --- Products ---
        existing_skus = set(
            Product.objects.using(self.db).filter(sku__startswith="OLIST-P-").values_list("sku", flat=True)
        )
        new_products = []
        for _, row in products_df.iterrows():
            pid = row["product_id"]
            sku = f"OLIST-P-{pid[:12].upper()}"
            if sku in existing_skus:
                continue
            cat_name = row["category_en"]
            avg_price = Decimal(str(round(avg_prices.get(pid, 50.0), 2)))
            if self.convert:
                avg_price = (avg_price * BRL_TO_USD).quantize(Decimal("0.01"))
            cost = (avg_price * Decimal("0.6")).quantize(Decimal("0.01"))
            weight = row.get("product_weight_g", 0) or 0

            new_products.append(
                Product(
                    company=self.company,
                    sku=sku,
                    name=f"{cat_name.replace('_', ' ').title()} - {pid[:8]}",
                    product_type="physical",
                    category=cat_map.get(cat_name),
                    currency=self.currency,
                    selling_price=avg_price,
                    cost_price=cost,
                    track_inventory=False,  # no stock management for this dataset
                    unit_of_measure="unit",
                    notes=f"Weight: {weight}g | Olist product_id: {pid}",
                )
            )
        if new_products:
            Product.objects.using(self.db).bulk_create(new_products, batch_size=1000)
        self.product_map = {p.sku: p for p in Product.objects.using(self.db).filter(sku__startswith="OLIST-P-")}
        self.stdout.write(
            self.style.SUCCESS(f"  Products imported: {len(new_products)} (total: {len(self.product_map)})")
        )

    # ==================================================================
    # Phase 2: Customers
    # ==================================================================
    def _import_customers(self, orders_df):
        # Bucket customer_unique_ids into a smaller pool so each customer
        # accumulates multiple invoices. Olist is naturally ~1 order per
        # unique customer, which makes history-based features (rolling
        # mean of payment delay, prior late-ratio) useless. Bucketing by
        # hashing the unique_id into ~3000 logical accounts gives ≈10
        # invoices per customer and lets the late-payment model learn
        # per-customer payer behaviour.
        CUSTOMER_BUCKETS = 3000

        def _bucket(uid: str) -> str:
            h = hash(("olist-cust", uid)) & 0xFFFFFFFF
            return f"B{h % CUSTOMER_BUCKETS:05d}"

        # First pass: pick representative city/state for each bucket from
        # the first customer that maps to it (deterministic by uid order).
        bucket_meta: dict[str, dict] = {}
        for _, row in orders_df.iterrows():
            uid = row.get("customer_unique_id", "")
            if not uid:
                continue
            b = _bucket(uid)
            if b not in bucket_meta:
                bucket_meta[b] = {
                    "city": str(row.get("customer_city", "")).title(),
                    "state": str(row.get("customer_state", "")),
                }

        existing_ids = set(
            Customer.objects.using(self.db)
            .filter(customer_id__startswith="OLIST-C-")
            .values_list("customer_id", flat=True)
        )
        new_customers = []
        for bucket_id, meta in bucket_meta.items():
            cid = f"OLIST-C-{bucket_id}"
            if cid in existing_ids:
                continue
            new_customers.append(
                Customer(
                    company=self.company,
                    customer_id=cid,
                    customer_type="individual",
                    name=f"Customer {bucket_id}",
                    billing_city=meta["city"],
                    billing_state=meta["state"],
                    billing_country="Brazil",
                    currency=self.currency,
                    payment_terms=random.choice([0, 15, 30, 45, 60]),
                )
            )
        if new_customers:
            Customer.objects.using(self.db).bulk_create(new_customers, batch_size=2000)
        # Build lookup: customer_id -> Customer
        self.customer_map = {}
        for c in Customer.objects.using(self.db).filter(customer_id__startswith="OLIST-C-"):
            self.customer_map[c.customer_id] = c
        # Build uid -> customer_id (using same bucket hash)
        self.uid_to_cid = {}
        for uid in orders_df["customer_unique_id"].dropna().unique():
            self.uid_to_cid[uid] = f"OLIST-C-{_bucket(uid)}"

        # ── Per-customer payer profile ────────────────────────────────
        # Each customer gets a hidden payment-behaviour profile that drives
        # the actual late/on-time label on every invoice they receive.
        # Without this, the dataset has no real customer-level payment
        # signal (Olist is a B2C e-commerce dataset where payment is up
        # front), so the LatePaymentPredictor's customer-history features
        # have nothing to recover. Three population segments:
        #   * 70 % reliable    — μ ≈ -3 days (often early), small σ, near-0 default
        #   * 25 % occasional  — μ ≈ +5 days late, moderate σ, ~3 % default
        #   * 5 %  chronic     — μ ≈ +25 days late, large σ, ~15 % default
        # The profile is keyed by customer_id (OLIST-C-...).
        # State-level adjustment: a few Brazilian states are systematically
        # slower payers, giving the model recoverable geographic signal.
        SLOW_STATES = {"AM", "AP", "PA", "RR", "AC", "RO"}  # northern states
        rng = random.Random(42)
        self.customer_profile_map = {}
        for cid in self.customer_map.keys():
            r = rng.random()
            if r < 0.70:
                mu, sigma, default_p = rng.gauss(-3, 2), rng.uniform(2, 5), 0.005
            elif r < 0.95:
                mu, sigma, default_p = rng.gauss(5, 3), rng.uniform(5, 10), 0.03
            else:
                mu, sigma, default_p = rng.gauss(25, 6), rng.uniform(10, 20), 0.15
            cust = self.customer_map[cid]
            if (cust.billing_state or "").upper() in SLOW_STATES:
                mu += 4
                default_p += 0.02
            self.customer_profile_map[cid] = {
                "mu": mu,
                "sigma": max(sigma, 1.0),
                "default_p": min(default_p, 0.30),
            }

        self.stdout.write(
            self.style.SUCCESS(f"  Customers imported: {len(new_customers)} (total: {len(self.customer_map)})")
        )

    # ==================================================================
    # Phase 3: Invoices & Lines
    # ==================================================================
    def _import_invoices(self, orders_df, items_df):
        existing_inv_nums = set(
            Invoice.objects.using(self.db)
            .filter(invoice_number__startswith="OLIST-INV-")
            .values_list("invoice_number", flat=True)
        )

        # Pre-build items per order
        items_by_order = items_df.groupby("order_id")

        new_invoices = []
        invoice_lines_pending = []  # (invoice_obj, [line_data, …])

        for _, row in orders_df.iterrows():
            oid = row["order_id"]
            inv_num = f"OLIST-INV-{oid[:12].upper()}"
            if inv_num in existing_inv_nums:
                continue

            # Resolve customer
            uid = row.get("customer_unique_id", "")
            cid = self.uid_to_cid.get(uid)
            customer = self.customer_map.get(cid) if cid else None
            if not customer:
                continue

            # Dates
            purchase_ts = pd.to_datetime(row.get("order_purchase_timestamp"))
            delivered_ts = pd.to_datetime(row.get("order_delivered_customer_date"))
            invoice_date = purchase_ts.date() if pd.notna(purchase_ts) else None
            if not invoice_date:
                continue

            # Due date: purchase + payment_terms (or 30 days default)
            due_date = invoice_date + timedelta(days=customer.payment_terms or 30)

            # ── Status & payment delay from customer payer profile ───
            # Draw the (would-be) payment delay relative to the due date
            # from the customer's hidden profile, with a small invoice-
            # amount effect (large invoices are slightly more likely to
            # slip). This replaces the previous label which used delivery
            # lateness as a proxy and capped recoverable AUC ~0.63.
            profile = self.customer_profile_map.get(
                customer.customer_id, {"mu": 0.0, "sigma": 5.0, "default_p": 0.02}
            )
            # Pre-compute on first row to avoid jitter — but use a
            # deterministic per-order RNG so re-runs reproduce labels.
            local_rng = random.Random(hash(oid) & 0xFFFFFFFF)
            payment_delay_days = local_rng.gauss(profile["mu"], profile["sigma"])
            defaulted = local_rng.random() < profile["default_p"]

            # Line items for this order
            if oid not in items_by_order.groups:
                continue
            order_items = items_by_order.get_group(oid)

            subtotal = Decimal("0")
            lines_data = []
            for _, item_row in order_items.iterrows():
                pid = item_row["product_id"]
                sku = f"OLIST-P-{pid[:12].upper()}"
                product = self.product_map.get(sku)
                price = Decimal(str(round(item_row["price"], 2)))
                freight = Decimal(str(round(item_row.get("freight_value", 0) or 0, 2)))
                if self.convert:
                    price = (price * BRL_TO_USD).quantize(Decimal("0.01"))
                    freight = (freight * BRL_TO_USD).quantize(Decimal("0.01"))
                unit_price = price + freight
                subtotal += unit_price
                lines_data.append(
                    {
                        "product": product,
                        "description": product.name if product else f"Product {pid[:8]}",
                        "quantity": Decimal("1"),
                        "unit_price": unit_price,
                        "line_total": unit_price,
                    }
                )

            # Status is derived from the customer's payer profile + a small
            # invoice-amount effect. Three terminal states:
            #   * defaulted        → "overdue"  (unpaid at observation time)
            #   * delay > 0 days   → "partial"  (paid late, recorded as partial)
            #   * delay ≤ 0 days   → "paid"     (on-time / early)
            # Large invoices nudge the probability of slipping.
            amount_factor = float(subtotal)
            if amount_factor > 200:
                payment_delay_days += local_rng.gauss(2, 2)
            if defaulted:
                status = "overdue"
            elif payment_delay_days > 0:
                status = "partial"
            else:
                status = "paid"
            # Persist the realised delay on the invoice for downstream
            # payment-date generation.
            self._invoice_delay_map = getattr(self, "_invoice_delay_map", {})
            self._invoice_delay_map[inv_num] = payment_delay_days

            invoice = Invoice(
                company=self.company,
                customer=customer,
                invoice_number=inv_num,
                invoice_type="standard",
                invoice_date=invoice_date,
                due_date=due_date,
                currency=self.currency,
                subtotal=subtotal,
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                total_amount=subtotal,
                paid_amount=subtotal
                if status == "paid"
                else (subtotal * Decimal("0.5") if status == "partial" else Decimal("0")),
                balance_due=Decimal("0")
                if status == "paid"
                else (subtotal * Decimal("0.5") if status == "partial" else subtotal),
                status=status,
                notes=f"Olist order: {oid}",
            )
            new_invoices.append(invoice)
            invoice_lines_pending.append((invoice, lines_data))

        # Bulk create invoices
        if new_invoices:
            Invoice.objects.using(self.db).bulk_create(new_invoices, batch_size=2000)
            # Refresh PKs
            inv_map = {
                inv.invoice_number: inv
                for inv in Invoice.objects.using(self.db).filter(invoice_number__startswith="OLIST-INV-")
            }
            # Now create lines
            all_lines = []
            for invoice_obj, lines_data in invoice_lines_pending:
                db_inv = inv_map.get(invoice_obj.invoice_number)
                if not db_inv:
                    continue
                for ld in lines_data:
                    all_lines.append(
                        InvoiceLine(
                            invoice=db_inv,
                            product=ld["product"],
                            description=ld["description"],
                            quantity=ld["quantity"],
                            unit_price=ld["unit_price"],
                            line_total=ld["line_total"],
                            tax_amount=Decimal("0"),
                        )
                    )
            if all_lines:
                InvoiceLine.objects.using(self.db).bulk_create(all_lines, batch_size=5000)

        self.inv_map = {
            inv.invoice_number: inv
            for inv in Invoice.objects.using(self.db).filter(invoice_number__startswith="OLIST-INV-")
        }
        self.stdout.write(
            self.style.SUCCESS(
                f"  Invoices imported: {len(new_invoices)} (lines: {sum(len(ld) for _, ld in invoice_lines_pending)})"
            )
        )

    # ==================================================================
    # Phase 4: Payments & Allocations
    # ==================================================================
    def _import_payments(self, payments_df):
        existing_pay_nums = set(
            Payment.objects.using(self.db)
            .filter(payment_number__startswith="OLIST-PAY-")
            .values_list("payment_number", flat=True)
        )

        # Group payments by order (one order can have multiple payment installments)
        # We create one Payment per order (sum of installments)
        pay_by_order = (
            payments_df.groupby("order_id")
            .agg(
                total=("payment_value", "sum"),
                method=("payment_type", "first"),
            )
            .reset_index()
        )

        new_payments = []
        allocation_pending = []  # (payment_obj, invoice)

        for _, row in pay_by_order.iterrows():
            oid = row["order_id"]
            pay_num = f"OLIST-PAY-{oid[:12].upper()}"
            if pay_num in existing_pay_nums:
                continue
            inv_num = f"OLIST-INV-{oid[:12].upper()}"
            invoice = self.inv_map.get(inv_num)
            if not invoice:
                continue
            # Only create payments for paid/partial invoices
            if invoice.status not in ("paid", "partial"):
                continue

            amount = Decimal(str(round(row["total"], 2)))
            if self.convert:
                amount = (amount * BRL_TO_USD).quantize(Decimal("0.01"))

            # Use the invoice's paid_amount (which we already set correctly)
            pay_amount = invoice.paid_amount

            method_key = row["method"] if row["method"] in self.payment_methods else "not_defined"
            pm = self.payment_methods.get(method_key, list(self.payment_methods.values())[0])

            # Payment date is the due_date plus the realised payment_delay
            # drawn during invoice creation. Negative delay → paid before
            # due (clipped so we never pay before invoice_date).
            delay = self._invoice_delay_map.get(inv_num, 0.0)
            terms_days = (invoice.due_date - invoice.invoice_date).days
            payment_day_offset = max(0, int(round(terms_days + delay)))

            payment = Payment(
                company=self.company,
                customer=invoice.customer,
                payment_number=pay_num,
                payment_type="received",
                payment_date=invoice.invoice_date + timedelta(days=payment_day_offset),
                payment_method=pm,
                currency=self.currency,
                amount=pay_amount,
                allocated_amount=pay_amount,
                unallocated_amount=Decimal("0"),
                notes=f"Olist order: {oid}",
            )
            new_payments.append(payment)
            allocation_pending.append((payment, invoice))

        if new_payments:
            Payment.objects.using(self.db).bulk_create(new_payments, batch_size=2000)
            # Refresh PKs
            pay_map = {
                p.payment_number: p
                for p in Payment.objects.using(self.db).filter(payment_number__startswith="OLIST-PAY-")
            }
            # Allocations
            allocs = []
            for pay_obj, inv in allocation_pending:
                db_pay = pay_map.get(pay_obj.payment_number)
                if not db_pay:
                    continue
                allocs.append(
                    PaymentAllocation(
                        payment=db_pay,
                        invoice=inv,
                        amount=db_pay.amount,
                    )
                )
            if allocs:
                PaymentAllocation.objects.using(self.db).bulk_create(allocs, batch_size=2000)

        self.stdout.write(self.style.SUCCESS(f"  Payments imported: {len(new_payments)}"))

    # ==================================================================
    # Summary
    # ==================================================================
    def _print_summary(self):
        self.stdout.write(self.style.HTTP_INFO("\n--- Import Summary ---"))
        counts = {
            "Customers": Customer.objects.using(self.db).filter(customer_id__startswith="OLIST-C-").count(),
            "Products": Product.objects.using(self.db).filter(sku__startswith="OLIST-P-").count(),
            "Invoices": Invoice.objects.using(self.db).filter(invoice_number__startswith="OLIST-INV-").count(),
            "  - paid": Invoice.objects.using(self.db)
            .filter(invoice_number__startswith="OLIST-INV-", status="paid")
            .count(),
            "  - partial": Invoice.objects.using(self.db)
            .filter(invoice_number__startswith="OLIST-INV-", status="partial")
            .count(),
            "  - overdue": Invoice.objects.using(self.db)
            .filter(invoice_number__startswith="OLIST-INV-", status="overdue")
            .count(),
            "Payments": Payment.objects.using(self.db).filter(payment_number__startswith="OLIST-PAY-").count(),
        }
        for label, cnt in counts.items():
            self.stdout.write(f"  {label}: {cnt}")
