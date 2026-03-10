"""
Management command: import_attendance

Imports the synthetic attendance time-series dataset into the ERP system
for ML model testing (Attendance Anomaly Detection).

Expected CSV file in datasets/:
  - attendance_timeseries_dataset.csv   (~52,000 rows)

Usage:
    python manage.py import_attendance
    python manage.py import_attendance --tenant erp_pg_alkuraimi --company-id 1
    python manage.py import_attendance --limit 10000
    python manage.py import_attendance --clear
"""

from datetime import time as dt_time
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Attendance,
    Company,
    Department,
    Employee,
)

DATASET_DIR = Path(__file__).resolve().parents[3] / "datasets"


class Command(BaseCommand):
    help = "Import synthetic attendance time-series dataset into ERP for ML testing."

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
            help="Max number of attendance records to import.",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete previously imported attendance data before importing.",
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

        # Build employee lookup
        self.departments = self._ensure_departments()
        self.employee_map = self._build_employee_map()

        # Optional clear
        if options["clear"]:
            self._clear_attendance_data()

        # Load CSV
        csv_path = DATASET_DIR / "attendance_timeseries_dataset.csv"
        if not csv_path.exists():
            raise CommandError(
                f"Dataset not found: {csv_path}\n"
                "Run: python datasets/generate_synthetic.py"
            )
        df = pd.read_csv(csv_path)
        if options["limit"]:
            df = df.head(options["limit"])
        self.stdout.write(f"Loaded {len(df)} attendance records from dataset.")

        # Import
        self.stdout.write("\n[Phase 1] Importing attendance records …")
        self._import_attendance(df)

        self.stdout.write(self.style.SUCCESS("\n✓ Attendance import complete!"))
        self._print_summary()

    # ==================================================================
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

    def _build_employee_map(self):
        """Map dataset employee_id → DB Employee, creating placeholders if needed."""
        # First, get existing employees by employee_id
        existing = {}
        for emp in Employee.objects.using(self.db).filter(
            company=self.company
        ).only('id', 'employee_id', 'department'):
            existing[emp.employee_id] = emp
        return existing

    def _clear_attendance_data(self):
        self.stdout.write(self.style.WARNING("Clearing attendance data for mapped employees …"))
        # Get employee IDs from dataset
        csv_path = DATASET_DIR / "attendance_timeseries_dataset.csv"
        df = pd.read_csv(csv_path, usecols=['employee_id'])
        emp_ids = df['employee_id'].unique().tolist()
        cnt = Attendance.objects.using(self.db).filter(
            employee__employee_id__in=emp_ids
        ).delete()[0]
        self.stdout.write(f"  Attendance records deleted: {cnt}")

    # ==================================================================
    def _import_attendance(self, df):
        # Get unique employee IDs from dataset
        dataset_emp_ids = df['employee_id'].unique()
        self.stdout.write(f"  Dataset has {len(dataset_emp_ids)} unique employees.")

        # Make sure all dataset employees exist in DB
        missing_count = 0
        for emp_id in dataset_emp_ids:
            if emp_id not in self.employee_map:
                # Get dept from first row for this employee
                emp_row = df[df['employee_id'] == emp_id].iloc[0]
                dept = self.departments.get(emp_row.get('department', ''))
                self._create_placeholder_employee(emp_id, dept)
                missing_count += 1

        if missing_count:
            self.stdout.write(f"  Created {missing_count} placeholder employees.")

        # Build set of existing (employee_pk, date) to skip duplicates
        existing_keys = set()
        mapped_emp_pks = [e.pk for e in self.employee_map.values()]
        for att in Attendance.objects.using(self.db).filter(
            employee__pk__in=mapped_emp_pks
        ).values_list('employee_id', 'date'):
            existing_keys.add((att[0], str(att[1])))

        created = 0
        skipped = 0
        batch = []

        for _, row in df.iterrows():
            emp = self.employee_map.get(row['employee_id'])
            if not emp:
                skipped += 1
                continue

            date_str = row['date']
            key = (emp.pk, date_str)
            if key in existing_keys:
                skipped += 1
                continue

            check_in = self._parse_time(row.get('check_in'))
            check_out = self._parse_time(row.get('check_out'))
            is_present = bool(row.get('is_present', False))
            is_late = bool(row.get('is_late', False))

            att = Attendance(
                employee=emp,
                date=pd.to_datetime(date_str).date(),
                check_in=check_in,
                check_out=check_out,
                hours_worked=Decimal(str(round(float(row.get('hours_worked', 0)), 2))),
                overtime_hours=Decimal(str(round(float(row.get('overtime_hours', 0)), 2))),
                is_present=is_present,
                is_late=is_late,
                late_minutes=max(0, int((float(row.get('hours_worked', 8)) - 8) * -7.5)) if is_late else 0,
                notes=row.get('anomaly_type', '') if pd.notna(row.get('anomaly_type')) else '',
            )
            batch.append(att)

            if len(batch) >= 1000:
                Attendance.objects.using(self.db).bulk_create(batch, ignore_conflicts=True)
                created += len(batch)
                batch = []
                self.stdout.write(f"  … {created} attendance records imported")

        # Flush remaining
        if batch:
            Attendance.objects.using(self.db).bulk_create(batch, ignore_conflicts=True)
            created += len(batch)

        self.stdout.write(f"  Created: {created}, Skipped (existing/unmapped): {skipped}")

    # ------------------------------------------------------------------
    def _create_placeholder_employee(self, emp_id, department=None):
        """Create a minimal placeholder employee for attendance data."""
        from django.utils import timezone
        from erp.models import Currency
        idx = int(emp_id.split('-')[1]) if '-' in emp_id else 0
        currency, _ = Currency.objects.using(self.db).get_or_create(
            code="USD",
            defaults={"name": "US Dollar", "symbol": "$",
                       "is_base": True, "exchange_rate": 1},
        )
        emp = Employee(
            company=self.company,
            employee_id=emp_id,
            first_name=f"Employee",
            last_name=f"{idx:04d}",
            gender='male' if idx % 2 == 0 else 'female',
            date_of_birth='1990-01-01',
            nationality='Omani',
            email=f"{emp_id.lower().replace('-', '')}@example.com",
            phone=f"+968-{90000000 + idx}",
            department=department,
            job_title='Staff',
            employment_type='full_time',
            employment_status='active',
            hire_date=timezone.now().date().replace(year=2020, month=1, day=1),
            currency=currency,
        )
        emp.save(using=self.db)
        self.employee_map[emp_id] = emp

    @staticmethod
    def _parse_time(val):
        """Parse HH:MM string into datetime.time, or None."""
        if pd.isna(val) or val == '' or val is None:
            return None
        try:
            parts = str(val).split(':')
            return dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return None

    # ==================================================================
    def _print_summary(self):
        total = Attendance.objects.using(self.db).filter(
            employee__company=self.company,
        ).count()
        present = Attendance.objects.using(self.db).filter(
            employee__company=self.company, is_present=True,
        ).count()
        late = Attendance.objects.using(self.db).filter(
            employee__company=self.company, is_late=True,
        ).count()

        self.stdout.write(f"\n  Summary:")
        self.stdout.write(f"    Total records:  {total}")
        self.stdout.write(f"    Present:        {present}")
        self.stdout.write(f"    Late:           {late}")
        self.stdout.write(f"    Absent:         {total - present}")
