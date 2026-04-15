"""
Seed operational inventory + payable data to improve ML model coverage.

Creates synthetic, realistic data for:
- Demand forecasting (StockMovement history + ReorderRule)
- KPI anomaly checks (includes optional yesterday movement spike)
- Cash-flow forecast (near-term pending supplier invoices)

Usage:
    python manage.py seed_ml_operational_data --tenant kuraimitttt
    python manage.py seed_ml_operational_data --tenant kuraimitttt --days 240 --products 80 --inject-kpi-spike
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Company,
    Product,
    Warehouse,
    ReorderRule,
    StockMovement,
    Supplier,
    SupplierInvoice,
    Currency,
)

SEED_REF_PREFIX = 'MLSEED'


class Command(BaseCommand):
    help = 'Seed operational data for demand forecast, KPI checks, and cash-flow projections.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Tenant DB name')
        parser.add_argument('--company-id', type=int, default=None, help='Company ID (defaults to first)')
        parser.add_argument('--days', type=int, default=365, help='History days for stock movements')
        parser.add_argument('--products', type=int, default=60, help='Number of products to seed movements for')
        parser.add_argument('--supplier-invoices', type=int, default=220, help='Pending supplier invoices to create')
        parser.add_argument('--inject-kpi-spike', action='store_true', help='Inject large yesterday movement spike for KPI anomaly alert')
        parser.add_argument('--reset-ml-seed', action='store_true', help='Delete existing MLSEED stock/invoice rows before reseeding')

    def handle(self, *args, **options):
        db_alias = self._activate_tenant(options['tenant'])
        with TenantDatabaseContext(db_alias):
            self.db = db_alias
            self.company = self._resolve_company(options['company_id'])

            self.stdout.write(self.style.HTTP_INFO(f'Company: {self.company.name} (id={self.company.id})'))

            days = max(45, int(options['days']))
            n_products = max(10, int(options['products']))
            n_supplier_invoices = max(20, int(options['supplier_invoices']))
            inject_kpi_spike = options['inject_kpi_spike']
            reset_seed = options['reset_ml_seed']

            warehouse = Warehouse.objects.using(self.db).filter(company=self.company, is_active=True).order_by('id').first()
            if not warehouse:
                raise CommandError('No active warehouse found for this company. Demand seed requires at least one warehouse.')

            products = list(
                Product.objects.using(self.db)
                .filter(company=self.company, is_active=True)
                .order_by('id')[:n_products]
            )
            if not products:
                raise CommandError('No active products found for this company.')

            # Ensure seeded products are inventory-tracked for downstream services
            Product.objects.using(self.db).filter(id__in=[p.id for p in products]).update(track_inventory=True)

            suppliers = list(
                Supplier.objects.using(self.db)
                .filter(company=self.company, is_active=True)
                .order_by('id')
            )
            if not suppliers:
                raise CommandError('No suppliers found. Run supplier import first.')

            currency = self._resolve_currency()

            if reset_seed:
                self._cleanup_existing_seed_rows()

            seeded_moves = self._seed_stock_movements(products, warehouse, days, inject_kpi_spike)
            seeded_rules = self._ensure_reorder_rules(products, warehouse, suppliers)
            seeded_supplier_invoices = self._seed_supplier_invoices(suppliers, currency, n_supplier_invoices)

            self.stdout.write(self.style.SUCCESS('\nSeeding complete:'))
            self.stdout.write(f'  Stock movements created: {seeded_moves}')
            self.stdout.write(f'  Reorder rules created/updated: {seeded_rules}')
            self.stdout.write(f'  Pending supplier invoices created: {seeded_supplier_invoices}')

    def _activate_tenant(self, tenant_name: str) -> str:
        try:
            tenant_db = TenantDatabase.objects.get(name=tenant_name)
        except TenantDatabase.DoesNotExist:
            available = list(TenantDatabase.objects.filter(status='active').values_list('name', flat=True))
            raise CommandError(f"Tenant '{tenant_name}' not found. Available: {available}")
        return add_tenant_database(tenant_db)

    def _resolve_company(self, company_id: int | None) -> Company:
        if company_id:
            company = Company.objects.using(self.db).filter(id=company_id).first()
        else:
            company = Company.objects.using(self.db).first()
        if not company:
            raise CommandError('No company found in this tenant DB.')
        return company

    def _resolve_currency(self) -> Currency:
        currency = Currency.objects.using(self.db).filter(code='USD').first()
        if currency:
            return currency
        currency = Currency.objects.using(self.db).first()
        if not currency:
            raise CommandError('No currency found for company; cannot seed supplier invoices.')
        return currency

    def _cleanup_existing_seed_rows(self) -> None:
        deleted_moves = StockMovement.objects.using(self.db).filter(
            company=self.company,
            reference_number__startswith=f'{SEED_REF_PREFIX}-',
        ).delete()[0]
        deleted_si = SupplierInvoice.objects.using(self.db).filter(
            company=self.company,
            invoice_number__startswith=f'{SEED_REF_PREFIX}-SINV-',
        ).delete()[0]
        self.stdout.write(self.style.WARNING(
            f'Reset existing seed rows: stock_movements={deleted_moves}, supplier_invoices={deleted_si}'
        ))

    def _seed_stock_movements(self, products: list[Product], warehouse: Warehouse,
                              days: int, inject_kpi_spike: bool) -> int:
        now_dt = timezone.now()
        start_dt = now_dt - timedelta(days=days)

        created = 0
        movement_types = [
            StockMovement.MovementType.SALES_ISSUE,
            StockMovement.MovementType.TRANSFER_OUT,
            StockMovement.MovementType.RETURN_OUT,
            StockMovement.MovementType.WRITE_OFF,
        ]
        movement_weights = [0.72, 0.18, 0.06, 0.04]

        import math

        for idx, product in enumerate(products):
            # Product diversity: fast movers (60%), moderate (25%), slow (15%)
            profile = random.random()
            if profile < 0.60:
                base_daily = random.uniform(5.0, 18.0)   # fast mover
            elif profile < 0.85:
                base_daily = random.uniform(2.0, 6.0)    # moderate
            else:
                base_daily = random.uniform(0.5, 2.5)    # slow mover

            weekly_amp = random.uniform(0.08, 0.30)
            monthly_amp = random.uniform(0.05, 0.20)
            trend = random.uniform(-0.0003, 0.0008)
            # Weekend dip: some products sell less on weekends
            weekend_dip = random.uniform(0.3, 0.8) if random.random() < 0.6 else 1.0
            # Random phase offset for monthly seasonality
            month_phase = random.uniform(0, 2 * math.pi)

            for d in range(days):
                movement_dt = start_dt + timedelta(days=d)
                day_date = movement_dt.date()

                # Weekly seasonality (smooth sinusoidal)
                week_pos = day_date.weekday() / 6.0
                weekly_effect = 1.0 + weekly_amp * math.sin(2 * math.pi * week_pos)
                # Weekend adjustment
                if day_date.weekday() >= 5:
                    weekly_effect *= weekend_dip
                # Monthly seasonality
                day_of_year = day_date.timetuple().tm_yday
                monthly_effect = 1.0 + monthly_amp * math.sin(2 * math.pi * day_of_year / 30.4 + month_phase)
                # Growth trend
                growth = max(0.6, 1.0 + trend * d)
                expected = max(0.1, base_daily * weekly_effect * monthly_effect * growth)

                qty = max(0.05, random.gauss(expected, expected * 0.25))
                # Occasional spikes (5%) and dips/zeros (3%)
                if random.random() < 0.05:
                    qty *= random.uniform(1.6, 2.8)
                elif random.random() < 0.03:
                    qty *= random.uniform(0.05, 0.3)

                unit_cost = float(product.cost_price or Decimal('1.00'))
                movement_type = random.choices(movement_types, movement_weights, k=1)[0]

                StockMovement.objects.using(self.db).create(
                    company=self.company,
                    movement_date=movement_dt,
                    movement_type=movement_type,
                    product=product,
                    warehouse=warehouse,
                    quantity=round(Decimal(str(qty)), 4),
                    unit_cost=round(Decimal(str(unit_cost)), 4),
                    total_cost=round(Decimal(str(qty * unit_cost)), 4),
                    reference_type='ml_seed',
                    reference_number=f'{SEED_REF_PREFIX}-SM-{product.id}-{d}',  # type: ignore[attr-defined]
                    description='Synthetic demand movement for ML training',
                )
                created += 1

            # Opening movement for stable inventory baseline
            opening_qty = Decimal(str(max(20.0, base_daily * 10.0))).quantize(Decimal('0.0001'))
            opening_unit_cost = Decimal(str(float(product.cost_price or Decimal('1.00')))).quantize(Decimal('0.0001'))
            StockMovement.objects.using(self.db).create(
                company=self.company,
                movement_date=start_dt - timedelta(days=1),
                movement_type=StockMovement.MovementType.OPENING,
                product=product,
                warehouse=warehouse,
                quantity=opening_qty,
                unit_cost=opening_unit_cost,
                total_cost=(opening_qty * opening_unit_cost).quantize(Decimal('0.0001')),
                reference_type='ml_seed',
                reference_number=f'{SEED_REF_PREFIX}-OPEN-{product.id}',  # type: ignore[attr-defined]
                description='Synthetic opening balance for ML demand baseline',
            )
            created += 1

            if idx % 15 == 0:
                self.stdout.write(f'  … seeded demand history for {idx + 1}/{len(products)} products')

        if inject_kpi_spike:
            # Calculate spike size adaptively: target z ≈ 3.5-4.5σ
            # First compute baseline daily movement counts
            from django.db.models import Count
            from django.db.models.functions import TruncDate
            yesterday = now_dt - timedelta(days=1)
            baseline_qs = (
                StockMovement.objects.using(self.db)
                .filter(
                    company=self.company,
                    movement_date__date__gte=(yesterday - timedelta(days=90)).date(),
                    movement_date__date__lt=yesterday.date(),
                )
                .annotate(day=TruncDate('movement_date'))
                .values('day')
                .annotate(cnt=Count('id'))
                .values_list('cnt', flat=True)
            )
            daily_counts = list(baseline_qs)
            if daily_counts:
                import numpy as np_seed
                mean_daily = np_seed.mean(daily_counts)
                std_daily = max(np_seed.std(daily_counts), 1.0)
                target_z = random.uniform(3.5, 4.5)
                spike_total = int(mean_daily + target_z * std_daily)
            else:
                # Fallback: moderate spike
                spike_total = int(len(products) * 3.5)

            # Subtract any already-existing yesterday movements
            existing_yesterday = StockMovement.objects.using(self.db).filter(
                company=self.company,
                movement_date__date=yesterday.date(),
            ).exclude(reference_number__startswith=f'{SEED_REF_PREFIX}-KPI-').count()
            spike_extra = max(0, spike_total - existing_yesterday)

            spike_products = products[:min(20, len(products))]
            for i in range(spike_extra):
                product = random.choice(spike_products)
                spike_qty: Decimal = Decimal(str(random.uniform(0.4, 4.0))).quantize(Decimal('0.0001'))
                spike_unit_cost: Decimal = Decimal(str(float(product.cost_price or Decimal('1.00')))).quantize(Decimal('0.0001'))
                StockMovement.objects.using(self.db).create(
                    company=self.company,
                    movement_date=yesterday,
                    movement_type=StockMovement.MovementType.TRANSFER_OUT,
                    product=product,
                    warehouse=warehouse,
                    quantity=spike_qty,
                    unit_cost=spike_unit_cost,
                    total_cost=(spike_qty * spike_unit_cost).quantize(Decimal('0.0001')),  # type: ignore[assignment]
                    reference_type='ml_seed',
                    reference_number=f'{SEED_REF_PREFIX}-KPI-{i}',
                    description='Synthetic KPI stress spike',
                )
                created += 1
            self.stdout.write(f'  KPI spike: target_z~{target_z if daily_counts else "N/A"}, '
                              f'extra_movements={spike_extra}, '
                              f'existing_yesterday={existing_yesterday}')

        return created

    def _ensure_reorder_rules(self, products: list[Product], warehouse: Warehouse,
                              suppliers: list[Supplier]) -> int:
        affected = 0
        for product in products:
            default_supplier = product.supplier or random.choice(suppliers)
            lead_time = random.randint(5, 21)
            rop = Decimal(str(random.uniform(18, 95))).quantize(Decimal('0.01'))
            safety_stock = Decimal(str(random.uniform(6, 30))).quantize(Decimal('0.01'))
            min_order = Decimal(str(random.uniform(5, 40))).quantize(Decimal('0.01'))

            ReorderRule.objects.using(self.db).update_or_create(
                company=self.company,
                product=product,
                warehouse=warehouse,
                defaults={
                    'reorder_point': rop,
                    'safety_stock': safety_stock,
                    'min_order_qty': min_order,
                    'max_order_qty': Decimal('0.00'),
                    'lead_time_days': lead_time,
                    'preferred_supplier': default_supplier,
                    'is_active': True,
                },
            )
            affected += 1
        return affected

    def _seed_supplier_invoices(self, suppliers: list[Supplier], currency: Currency,
                                count: int) -> int:
        today = timezone.now().date()
        created = 0

        for i in range(count):
            supplier = random.choice(suppliers)
            invoice_date = today - timedelta(days=random.randint(3, 45))
            due_date = today + timedelta(days=random.randint(3, 90))

            subtotal = Decimal(str(random.uniform(600, 12000))).quantize(Decimal('0.01'))
            tax_amount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
            total_amount = (subtotal + tax_amount).quantize(Decimal('0.01'))

            invoice_number = f'{SEED_REF_PREFIX}-SINV-{today.strftime("%Y%m%d")}-{i:04d}'

            SupplierInvoice.objects.using(self.db).update_or_create(
                company=self.company,
                invoice_number=invoice_number,
                defaults={
                    'supplier': supplier,
                    'supplier_invoice_number': f'SUPINV-{i:04d}',
                    'invoice_date': invoice_date,
                    'due_date': due_date,
                    'currency': currency,
                    'subtotal': subtotal,
                    'tax_amount': tax_amount,
                    'total_amount': total_amount,
                    'paid_amount': Decimal('0.00'),
                    'balance_due': total_amount,
                    'status': SupplierInvoice.Status.PENDING,
                    'notes': 'Synthetic payables for cash-flow ML validation',
                },
            )
            created += 1

        return created
