"""
Management command: import_ibm_hr

Imports the IBM HR Employee Attrition dataset into the ERP system
for realistic ML model testing (Attrition Prediction, Attendance
Anomaly Detection).

Expected CSV file in datasets/:
  - WA_Fn-UseC_-HR-Employee-Attrition.csv   (1,470 rows)

Usage:
    python manage.py import_ibm_hr
    python manage.py import_ibm_hr --tenant erp_pg_alkuraimi --company-id 1
    python manage.py import_ibm_hr --clear
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import (
    Attendance,
    Company,
    Currency,
    Department,
    Employee,
    LeaveRequest,
    LeaveType,
    Payroll,
)

DATASET_DIR = Path(__file__).resolve().parents[3] / "datasets"

# Reference date: we pretend "today" is 2024-06-01 so hire dates look recent-ish
REFERENCE_DATE = date(2024, 6, 1)

IBM_DEPARTMENTS = {
    "Sales": "SALES",
    "Research & Development": "R&D",
    "Human Resources": "HR",
}

EMPLOYMENT_TYPES = {
    1: "intern",
    2: "full_time",
    3: "full_time",
    4: "full_time",
    5: "full_time",
}


class Command(BaseCommand):
    help = "Import the IBM HR Employee Attrition dataset into ERP for ML testing."

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
            help="Company ID. Defaults to first company.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete previously imported IBM HR data before importing.",
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        db_alias = self._activate_tenant(options["tenant"])
        with TenantDatabaseContext(db_alias):
            self._run(options, db_alias)

    # ------------------------------------------------------------------
    # Tenant resolution
    # ------------------------------------------------------------------
    def _activate_tenant(self, tenant_name):
        if tenant_name is None:
            tenant_db = TenantDatabase.objects.filter(status="active").first()
            if not tenant_db:
                raise CommandError("No active tenant. Pass --tenant <name>.")
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

        # -- Reference data ------------------------------------------------
        self.currency = self._ensure_currency()
        self.departments = self._ensure_departments()
        self.leave_types = self._ensure_leave_types()

        # -- Optional clear ------------------------------------------------
        if options["clear"]:
            self._clear_hr_data()

        # -- Load CSV ------------------------------------------------------
        csv_path = DATASET_DIR / "WA_Fn-UseC_-HR-Employee-Attrition.csv"
        df = pd.read_csv(csv_path)
        self.stdout.write(f"Loaded {len(df)} employees from IBM HR dataset.")

        # -- Phase 1: Employees --------------------------------------------
        self.stdout.write("\n[Phase 1] Importing employees …")
        self._import_employees(df)

        # -- Phase 2: Attendance records -----------------------------------
        self.stdout.write("\n[Phase 2] Generating attendance records …")
        self._generate_attendance()

        # -- Phase 3: Leave requests ---------------------------------------
        self.stdout.write("\n[Phase 3] Generating leave requests …")
        self._generate_leave_requests()

        # -- Phase 4: Payroll records --------------------------------------
        self.stdout.write("\n[Phase 4] Generating payroll records …")
        self._generate_payroll()

        self.stdout.write(self.style.SUCCESS("\n✓ IBM HR import complete!"))
        self._print_summary()

    # ==================================================================
    # Reference data
    # ==================================================================
    def _ensure_currency(self):
        cur, _ = Currency.objects.using(self.db).get_or_create(
            code="USD",
            defaults={"name": "US Dollar", "symbol": "$", "is_base": True, "exchange_rate": 1},
        )
        return cur

    def _ensure_departments(self):
        dept_map = {}
        for name, code in IBM_DEPARTMENTS.items():
            dept, _ = Department.objects.using(self.db).get_or_create(
                company=self.company,
                code=code,
                defaults={"name": name, "is_active": True},
            )
            dept_map[name] = dept
        return dept_map

    def _ensure_leave_types(self):
        leave_types = {}
        defaults_list = [
            ("annual", "Annual Leave", 21, True),
            ("sick", "Sick Leave", 15, True),
            ("unpaid", "Unpaid Leave", 0, False),
        ]
        for code, name, days, is_paid in defaults_list:
            lt, _ = LeaveType.objects.using(self.db).get_or_create(
                code=code,
                defaults={"name": name, "days_allowed": days, "is_paid": is_paid},
            )
            leave_types[code] = lt
        return leave_types

    # ==================================================================
    # Clear
    # ==================================================================
    def _clear_hr_data(self):
        self.stdout.write(self.style.WARNING("Clearing previously imported IBM HR data …"))

        cnt = Payroll.all_objects.using(self.db).filter(employee__employee_id__startswith="IBM-").delete()[0]
        self.stdout.write(f"  Payroll deleted: {cnt}")

        cnt = LeaveRequest.all_objects.using(self.db).filter(employee__employee_id__startswith="IBM-").delete()[0]
        self.stdout.write(f"  LeaveRequests deleted: {cnt}")

        cnt = Attendance.objects.using(self.db).filter(employee__employee_id__startswith="IBM-").delete()[0]
        self.stdout.write(f"  Attendance deleted: {cnt}")

        cnt = Employee.all_objects.using(self.db).filter(employee_id__startswith="IBM-").delete()[0]
        self.stdout.write(f"  Employees deleted: {cnt}")

    # ==================================================================
    # Phase 1: Employees
    # ==================================================================
    def _import_employees(self, df):
        existing_ids = set(
            Employee.objects.using(self.db).filter(employee_id__startswith="IBM-").values_list("employee_id", flat=True)
        )

        new_employees = []
        for _, row in df.iterrows():
            emp_num = row["EmployeeNumber"]
            emp_id = f"IBM-{emp_num:05d}"
            if emp_id in existing_ids:
                continue

            # Derive hire date from YearsAtCompany
            years_at_company = int(row.get("YearsAtCompany", 0))
            hire_date = REFERENCE_DATE - timedelta(days=years_at_company * 365 + random.randint(0, 30))

            # Termination: if Attrition == "Yes", they left
            attrition = str(row.get("Attrition", "No"))
            is_terminated = attrition.strip().lower() == "yes"
            termination_date = None
            employment_status = "active"
            if is_terminated:
                # Left somewhere in the last year
                termination_date = REFERENCE_DATE - timedelta(days=random.randint(1, 365))
                employment_status = random.choice(["terminated", "resigned"])

            # Gender
            gender_raw = str(row.get("Gender", "Male")).strip().lower()
            gender = "male" if gender_raw == "male" else "female"

            # Department
            dept_name = row.get("Department", "Research & Development")
            department = self.departments.get(dept_name)

            # Employment type from JobLevel
            job_level = int(row.get("JobLevel", 2))
            emp_type = EMPLOYMENT_TYPES.get(job_level, "full_time")

            # Salary
            monthly_income = Decimal(str(row.get("MonthlyIncome", 5000)))

            # Date of birth from Age
            age = int(row.get("Age", 30))
            dob = REFERENCE_DATE - timedelta(days=age * 365 + random.randint(0, 364))

            # Job role
            job_role = str(row.get("JobRole", "Associate"))

            # Leave balance — WorkLifeBalance (1-4) → map to leave days
            wlb = int(row.get("WorkLifeBalance", 3))
            annual_leave = Decimal(str(max(0, wlb * 5 + random.randint(-3, 3))))
            sick_leave = Decimal(str(random.randint(0, 10)))

            # Names (synthetic, since IBM dataset has no names)
            first_names_m = [
                "James",
                "John",
                "Robert",
                "Michael",
                "David",
                "William",
                "Richard",
                "Joseph",
                "Thomas",
                "Daniel",
                "Matthew",
                "Anthony",
                "Mark",
                "Steven",
                "Paul",
                "Andrew",
                "Kevin",
                "Brian",
            ]
            first_names_f = [
                "Mary",
                "Jennifer",
                "Linda",
                "Patricia",
                "Elizabeth",
                "Barbara",
                "Susan",
                "Jessica",
                "Sarah",
                "Karen",
                "Lisa",
                "Nancy",
                "Betty",
                "Margaret",
                "Sandra",
                "Ashley",
                "Dorothy",
                "Kimberly",
            ]
            last_names = [
                "Smith",
                "Johnson",
                "Williams",
                "Brown",
                "Jones",
                "Garcia",
                "Miller",
                "Davis",
                "Rodriguez",
                "Martinez",
                "Hernandez",
                "Lopez",
                "Gonzalez",
                "Wilson",
                "Anderson",
                "Thomas",
                "Taylor",
                "Moore",
                "Jackson",
                "Martin",
                "Lee",
                "White",
                "Harris",
                "Clark",
            ]

            first_name = random.choice(first_names_m if gender == "male" else first_names_f)
            last_name = random.choice(last_names)

            new_employees.append(
                Employee(
                    company=self.company,
                    employee_id=emp_id,
                    first_name=first_name,
                    last_name=last_name,
                    gender=gender,
                    date_of_birth=dob,
                    nationality="American",
                    email=f"{first_name.lower()}.{last_name.lower()}.{emp_num}@example.com",
                    phone=f"+1-555-{random.randint(1000, 9999):04d}",
                    department=department,
                    job_title=job_role,
                    employment_type=emp_type,
                    employment_status=employment_status,
                    hire_date=hire_date,
                    termination_date=termination_date,
                    basic_salary=monthly_income,
                    currency=self.currency,
                    annual_leave_balance=annual_leave,
                    sick_leave_balance=sick_leave,
                    city="New York",
                    country="United States",
                )
            )

        if new_employees:
            Employee.objects.using(self.db).bulk_create(new_employees, batch_size=500)

        self.employees = list(Employee.objects.using(self.db).filter(employee_id__startswith="IBM-"))
        active = [e for e in self.employees if e.employment_status == "active"]
        terminated = [e for e in self.employees if e.employment_status in ("terminated", "resigned")]
        self.stdout.write(
            self.style.SUCCESS(
                f"  Employees imported: {len(new_employees)} "
                f"(active: {len(active)}, terminated/resigned: {len(terminated)})"
            )
        )

    # ==================================================================
    # Phase 2: Attendance
    # ==================================================================
    def _generate_attendance(self):
        existing_count = Attendance.objects.using(self.db).filter(employee__employee_id__startswith="IBM-").count()
        if existing_count > 0:
            self.stdout.write(f"  Skipping — {existing_count} attendance records already exist.")
            return

        # Generate a 90-day attendance window ending at each employee's
        # personal snapshot date (termination_date for leavers,
        # REFERENCE_DATE for active). This ensures both classes have the
        # SAME number of records — previously terminated employees whose
        # termination_date fell more than 90 days before REFERENCE_DATE
        # got zero attendance, which let the Attrition model trivially
        # separate the classes by record-count alone (target leakage).
        ATT_WINDOW_DAYS = 90

        all_records = []
        for emp in self.employees:
            emp_end = emp.termination_date or REFERENCE_DATE
            emp_start = emp_end - timedelta(days=ATT_WINDOW_DAYS - 1)
            # Don't generate before hire_date.
            if emp.hire_date:
                emp_start = max(emp_start, emp.hire_date)
            if emp_start > emp_end:
                continue
            current = emp_start
            while current <= emp_end:
                # Skip weekends
                if current.weekday() >= 5:
                    current += timedelta(days=1)
                    continue
                # 90% present, 10% absent
                is_present = random.random() < 0.90
                is_late = False
                late_mins = 0
                hours = Decimal("0")
                check_in = None
                check_out = None

                if is_present:
                    # Normal check-in 8:00, with some variance
                    late_mins = max(0, int(random.gauss(0, 15)))
                    is_late = late_mins > 10
                    from datetime import time

                    ci_hour = 8
                    ci_min = late_mins
                    if ci_min >= 60:
                        ci_hour += ci_min // 60
                        ci_min = ci_min % 60
                    check_in = time(ci_hour, ci_min)
                    # Check out 5pm +/- some variance
                    co_extra = random.randint(-30, 60)
                    co_total = 17 * 60 + co_extra  # minutes from midnight
                    check_out = time(co_total // 60, co_total % 60)
                    hours = Decimal(str(round((co_total - (ci_hour * 60 + ci_min)) / 60, 2)))
                    hours = max(Decimal("0"), hours)

                overtime = max(Decimal("0"), hours - Decimal("8"))

                all_records.append(
                    Attendance(
                        employee=emp,
                        date=current,
                        check_in=check_in,
                        check_out=check_out,
                        hours_worked=hours,
                        overtime_hours=overtime,
                        is_present=is_present,
                        is_late=is_late,
                        late_minutes=late_mins if is_late else 0,
                    )
                )
                current += timedelta(days=1)

        if all_records:
            Attendance.objects.using(self.db).bulk_create(all_records, batch_size=5000)
        self.stdout.write(self.style.SUCCESS(f"  Attendance records created: {len(all_records)}"))

    # ==================================================================
    # Phase 3: Leave Requests
    # ==================================================================
    def _generate_leave_requests(self):
        existing = LeaveRequest.objects.using(self.db).filter(employee__employee_id__startswith="IBM-").count()
        if existing > 0:
            self.stdout.write(f"  Skipping — {existing} leave requests already exist.")
            return

        annual_lt = self.leave_types.get("annual")
        sick_lt = self.leave_types.get("sick")
        if not annual_lt or not sick_lt:
            self.stdout.write(self.style.WARNING("  Leave types not found, skipping."))
            return

        all_requests = []
        for emp in self.employees:
            # Each employee gets 1-4 leave requests in the past year
            n_requests = random.randint(1, 4)
            for _ in range(n_requests):
                leave_type = random.choice([annual_lt, sick_lt])
                days = random.randint(1, 5)
                start = REFERENCE_DATE - timedelta(days=random.randint(10, 350))
                end = start + timedelta(days=days - 1)
                status = random.choices(
                    ["approved", "pending", "rejected"],
                    weights=[0.7, 0.2, 0.1],
                )[0]
                all_requests.append(
                    LeaveRequest(
                        employee=emp,
                        leave_type=leave_type,
                        start_date=start,
                        end_date=end,
                        days_requested=Decimal(str(days)),
                        reason=f"{'Vacation' if leave_type == annual_lt else 'Medical'} leave",
                        status=status,
                    )
                )

        if all_requests:
            LeaveRequest.objects.using(self.db).bulk_create(all_requests, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(f"  Leave requests created: {len(all_requests)}"))

    # ==================================================================
    # Phase 4: Payroll
    # ==================================================================
    def _generate_payroll(self):
        existing = Payroll.objects.using(self.db).filter(employee__employee_id__startswith="IBM-").count()
        if existing > 0:
            self.stdout.write(f"  Skipping — {existing} payroll records already exist.")
            return

        all_payrolls = []
        # Generate 6 months of payroll ending at each employee's personal
        # snapshot date (termination_date for leavers, REFERENCE_DATE for
        # active). Without per-employee anchoring, terminated employees
        # systematically had fewer payroll rows than active ones, which
        # leaked the label into any window-based payroll feature.
        for emp in self.employees:
            emp_end = emp.termination_date or REFERENCE_DATE
            # Find the last full month ending on/before emp_end.
            anchor = date(emp_end.year, emp_end.month, 1)
            for month_offset in range(6):
                # Walk back 0..5 months from the anchor.
                year = anchor.year
                month = anchor.month - month_offset
                while month <= 0:
                    month += 12
                    year -= 1
                period_start = date(year, month, 1)
                if period_start.month == 12:
                    period_end = date(period_start.year, 12, 31)
                else:
                    period_end = date(period_start.year, period_start.month + 1, 1) - timedelta(days=1)

                # Don't generate before hire_date or after termination.
                if emp.hire_date and period_end < emp.hire_date:
                    continue
                if emp.termination_date and period_start > emp.termination_date:
                    continue

                basic = emp.basic_salary
                housing = (basic * Decimal("0.25")).quantize(Decimal("0.01"))
                transport = Decimal("300")
                overtime_amt = Decimal(str(random.randint(0, 500)))
                gross = basic + housing + transport + overtime_amt

                social_ins = (basic * Decimal("0.0975")).quantize(Decimal("0.01"))
                tax = (gross * Decimal("0.05")).quantize(Decimal("0.01"))
                total_ded = social_ins + tax
                net = gross - total_ded

                all_payrolls.append(
                    Payroll(
                        employee=emp,
                        period_start=period_start,
                        period_end=period_end,
                        basic_salary=basic,
                        housing_allowance=housing,
                        transport_allowance=transport,
                        overtime_amount=overtime_amt,
                        gross_salary=gross,
                        social_insurance=social_ins,
                        tax_deduction=tax,
                        total_deductions=total_ded,
                        net_salary=net,
                        status="paid",
                        payment_date=period_end + timedelta(days=random.randint(1, 5)),
                        currency=self.currency,
                    )
                )

        if all_payrolls:
            Payroll.objects.using(self.db).bulk_create(all_payrolls, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(f"  Payroll records created: {len(all_payrolls)}"))

    # ==================================================================
    # Summary
    # ==================================================================
    def _print_summary(self):
        self.stdout.write(self.style.HTTP_INFO("\n--- Import Summary ---"))
        counts = {
            "Employees (total)": Employee.objects.using(self.db).filter(employee_id__startswith="IBM-").count(),
            "  - active": Employee.objects.using(self.db)
            .filter(employee_id__startswith="IBM-", employment_status="active")
            .count(),
            "  - terminated/resigned": Employee.objects.using(self.db)
            .filter(employee_id__startswith="IBM-", employment_status__in=["terminated", "resigned"])
            .count(),
            "Departments": Department.objects.using(self.db)
            .filter(company=self.company, code__in=list(IBM_DEPARTMENTS.values()))
            .count(),
            "Attendance": Attendance.objects.using(self.db).filter(employee__employee_id__startswith="IBM-").count(),
            "Leave Requests": LeaveRequest.objects.using(self.db)
            .filter(employee__employee_id__startswith="IBM-")
            .count(),
            "Payroll": Payroll.objects.using(self.db).filter(employee__employee_id__startswith="IBM-").count(),
        }
        for label, cnt in counts.items():
            self.stdout.write(f"  {label}: {cnt}")
