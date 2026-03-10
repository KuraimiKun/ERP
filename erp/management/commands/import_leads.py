"""
Management command: import_leads

Imports the synthetic CRM leads dataset into the ERP system
for ML model testing (Lead Scoring).

Expected CSV file in datasets/:
  - crm_leads_dataset.csv   (~5,000 rows)

Usage:
    python manage.py import_leads
    python manage.py import_leads --tenant erp_pg_alkuraimi --company-id 1
    python manage.py import_leads --limit 2000
    python manage.py import_leads --clear
"""

import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Company,
    Department,
    Employee,
    Lead,
    LeadActivity,
)

DATASET_DIR = Path(__file__).resolve().parents[3] / "datasets"

ACTIVITY_SUBJECTS = {
    'call': [
        'Initial discovery call', 'Follow-up call', 'Pricing discussion call',
        'Demo scheduling call', 'Decision maker call',
    ],
    'email': [
        'Introduction email sent', 'Proposal sent via email', 'Follow-up email',
        'Pricing details emailed', 'Contract draft emailed',
    ],
    'meeting': [
        'On-site product demo', 'Requirements gathering meeting',
        'Stakeholder presentation', 'Contract negotiation meeting',
    ],
    'whatsapp': [
        'Quick check-in via WhatsApp', 'Shared project timeline',
        'Sent brochure via WhatsApp',
    ],
    'note': [
        'Internal notes on lead status', 'Updated requirements',
        'Budget confirmed by lead',
    ],
}


class Command(BaseCommand):
    help = "Import the synthetic CRM leads dataset into ERP for ML testing."

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
            help="Max number of leads to import.",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete previously imported lead data before importing.",
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
        self.sales_employees = self._ensure_sales_employees()

        # Optional clear
        if options["clear"]:
            self._clear_lead_data()

        # Load CSV
        csv_path = DATASET_DIR / "crm_leads_dataset.csv"
        if not csv_path.exists():
            raise CommandError(
                f"Dataset not found: {csv_path}\n"
                "Run: python datasets/generate_synthetic.py"
            )
        df = pd.read_csv(csv_path)
        if options["limit"]:
            df = df.head(options["limit"])
        self.stdout.write(f"Loaded {len(df)} leads from CRM dataset.")

        # Phase 1: Import leads
        self.stdout.write("\n[Phase 1] Importing leads …")
        lead_map = self._import_leads(df)

        # Phase 2: Generate activities
        self.stdout.write("\n[Phase 2] Generating lead activities …")
        self._generate_activities(df, lead_map)

        self.stdout.write(self.style.SUCCESS("\n✓ CRM lead import complete!"))
        self._print_summary()

    # ==================================================================
    def _ensure_sales_employees(self):
        """Get or create sales employees for lead assignment."""
        dept, _ = Department.objects.using(self.db).get_or_create(
            company=self.company, code="SALES",
            defaults={"name": "Sales", "is_active": True},
        )
        employees = list(
            Employee.objects.using(self.db).filter(
                company=self.company, department=dept, employment_status='active',
            )[:10]
        )
        if not employees:
            # Create a few placeholder sales employees
            for i, name in enumerate(['Salesperson A', 'Salesperson B', 'Salesperson C']):
                emp = Employee.objects.using(self.db).create(
                    company=self.company,
                    employee_id=f'SALE-{i+1:03d}',
                    first_name=name.split()[0],
                    last_name=name.split()[1],
                    department=dept,
                    employment_status='active',
                    employment_type='full_time',
                    basic_salary=Decimal('5000'),
                    hire_date='2022-01-01',
                )
                employees.append(emp)
        return employees

    def _clear_lead_data(self):
        self.stdout.write(self.style.WARNING("Clearing previously imported lead data …"))
        cnt = LeadActivity.objects.using(self.db).filter(
            lead__lead_number__startswith="LD-"
        ).delete()[0]
        self.stdout.write(f"  LeadActivities deleted: {cnt}")

        cnt = Lead.all_objects.using(self.db).filter(
            lead_number__startswith="LD-"
        ).delete()[0]
        self.stdout.write(f"  Leads deleted: {cnt}")

    # ==================================================================
    def _import_leads(self, df):
        existing = set(
            Lead.objects.using(self.db)
            .filter(lead_number__startswith="LD-")
            .values_list("lead_number", flat=True)
        )

        lead_map = {}
        created = 0
        skipped = 0

        for _, row in df.iterrows():
            ln = row['lead_number']
            if ln in existing:
                skipped += 1
                continue

            assigned = random.choice(self.sales_employees) if self.sales_employees else None

            created_at = timezone.make_aware(
                pd.to_datetime(row['created_at']).to_pydatetime()
            )
            last_contact = timezone.make_aware(
                pd.to_datetime(row['last_contact_date']).to_pydatetime()
            ) if pd.notna(row.get('last_contact_date')) else None

            conversion_date = None
            if pd.notna(row.get('conversion_date')) and row['conversion_date']:
                conversion_date = timezone.make_aware(
                    pd.to_datetime(row['conversion_date']).to_pydatetime()
                )

            lead = Lead(
                company=self.company,
                lead_number=ln,
                status=row['status'],
                source=row['source'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                email=row['email'],
                phone=str(row['phone']) if pd.notna(row.get('phone')) and row['phone'] else '',
                mobile=str(row['mobile']) if pd.notna(row.get('mobile')) and row['mobile'] else '',
                company_name=row.get('company_name', '') or '',
                job_title=row.get('job_title', '') or '',
                city=row.get('city', ''),
                country=row.get('country', ''),
                service_interest=row.get('service_interest', ''),
                estimated_value=Decimal(str(row['estimated_value'])) if pd.notna(row.get('estimated_value')) else None,
                probability=int(row.get('probability', 10)),
                assigned_to=assigned,
                last_contact_date=last_contact,
                conversion_date=conversion_date,
            )
            lead.save(using=self.db)
            # Override created_at
            Lead.objects.using(self.db).filter(pk=lead.pk).update(created_at=created_at)
            lead_map[ln] = lead
            created += 1

            if created % 500 == 0:
                self.stdout.write(f"  … {created} leads imported")

        self.stdout.write(f"  Created: {created}, Skipped (existing): {skipped}")
        return lead_map

    # ==================================================================
    def _generate_activities(self, df, lead_map):
        activities_created = 0

        for _, row in df.iterrows():
            ln = row['lead_number']
            lead = lead_map.get(ln)
            if not lead:
                continue

            activity_count = int(row.get('activity_count', 0))
            if activity_count == 0:
                continue

            created_at = pd.to_datetime(row['created_at']).to_pydatetime()
            days_pipeline = int(row.get('days_in_pipeline', 30))

            activity_types = list(ACTIVITY_SUBJECTS.keys())

            for j in range(activity_count):
                act_type = random.choice(activity_types)
                subjects = ACTIVITY_SUBJECTS[act_type]
                subject = random.choice(subjects)

                # Spread activities across pipeline duration
                day_offset = int(random.uniform(0, max(days_pipeline, 1)))
                act_date = timezone.make_aware(created_at + timedelta(days=day_offset))

                performed_by = random.choice(self.sales_employees) if self.sales_employees else None

                LeadActivity.objects.using(self.db).create(
                    lead=lead,
                    activity_type=act_type,
                    subject=subject,
                    description="Auto-generated activity for ML testing.",
                    activity_date=act_date,
                    is_completed=True,
                    completed_date=act_date,
                    performed_by=performed_by,
                )
                activities_created += 1

        self.stdout.write(f"  Activities created: {activities_created}")

    # ==================================================================
    def _print_summary(self):
        leads = Lead.objects.using(self.db).filter(
            company=self.company, lead_number__startswith="LD-"
        )
        won = leads.filter(status='won').count()
        lost = leads.filter(status='lost').count()
        total = leads.count()
        activities = LeadActivity.objects.using(self.db).filter(
            lead__company=self.company, lead__lead_number__startswith="LD-"
        ).count()

        self.stdout.write("\n  Summary:")
        self.stdout.write(f"    Leads:      {total}")
        self.stdout.write(f"    Won:        {won} ({won/max(total,1):.1%})")
        self.stdout.write(f"    Lost:       {lost} ({lost/max(total,1):.1%})")
        self.stdout.write(f"    Activities: {activities}")
