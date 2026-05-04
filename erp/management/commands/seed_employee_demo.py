"""
Management command: seed_employee_demo

Seeds demo data for a specific employee (by user email) so the mobile app
looks great for screenshots.  Creates:
  - 90 days of attendance records
  - 6 months of paid payslips
  - Leave requests (approved, pending, rejected)
  - Tasks (various statuses & priorities)
  - Notifications

Usage:
    python manage.py seed_employee_demo --email ahmedalkur@gmail.com
    python manage.py seed_employee_demo --email ahmedalkur@gmail.com --clear
"""

import random
from datetime import date, timedelta, time, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tenants.models import TenantUser, DatabaseAssignment
from tenants.routers import add_tenant_database, TenantDatabaseContext


class Command(BaseCommand):
    help = "Seed demo HR data (attendance, payslips, leaves, tasks, notifications) for one employee."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email of the TenantUser whose employee profile to seed.")
        parser.add_argument("--clear", action="store_true", help="Clear existing records for this employee first.")

    def handle(self, *args, **options):
        email = options["email"]

        # --- resolve user & tenant DB ---
        try:
            user = TenantUser.objects.get(email=email)
        except TenantUser.DoesNotExist:
            raise CommandError(f"No TenantUser found with email '{email}'.")

        da = DatabaseAssignment.objects.filter(user=user).select_related("database").first()
        if not da:
            raise CommandError(f"No database assignment found for '{email}'.")

        db_alias = add_tenant_database(da.database)
        self.stdout.write(self.style.HTTP_INFO(f"Using tenant DB: {da.database.name}"))

        with TenantDatabaseContext(db_alias):
            self._seed(user, options)

    # ------------------------------------------------------------------

    def _seed(self, user, options):
        from erp.models import (
            Employee, LeaveType, LeaveRequest, Attendance,
            Payroll, Task, Notification, Company, Currency,
        )

        emp = Employee.objects.filter(user=user).first()
        if not emp:
            raise CommandError(f"No Employee record linked to user '{user.email}'.")

        self.stdout.write(f"Employee: {emp.full_name} ({emp.employee_id})")

        if options["clear"]:
            self.stdout.write(self.style.WARNING("Clearing existing records..."))
            Attendance.objects.filter(employee=emp).delete()
            Payroll.objects.filter(employee=emp).delete()
            LeaveRequest.objects.filter(employee=emp).delete()
            Task.objects.filter(assigned_to=emp).delete()
            Notification.objects.filter(recipient=user).delete()
            self.stdout.write("  Cleared.")

        today = date.today()

        self._seed_attendance(emp, today)
        self._seed_payslips(emp, today)
        self._seed_leaves(emp, today)
        self._seed_tasks(emp, today)
        self._seed_notifications(user, emp, today)

        self.stdout.write(self.style.SUCCESS("\nDone! Demo data seeded successfully."))

    # ------------------------------------------------------------------
    # Attendance: last 90 working days
    # ------------------------------------------------------------------
    def _seed_attendance(self, emp, today):
        from erp.models import Attendance

        self.stdout.write("  Seeding attendance...")
        records = []
        d = today - timedelta(days=1)
        created = 0
        while created < 90:
            if d.weekday() >= 5:  # skip weekends
                d -= timedelta(days=1)
                continue

            if Attendance.objects.filter(employee=emp, date=d).exists():
                d -= timedelta(days=1)
                continue

            # occasional absence (~8% chance)
            absent = random.random() < 0.08
            late = (not absent) and (random.random() < 0.15)
            late_mins = random.randint(5, 40) if late else 0

            check_in = None
            check_out = None
            hours_worked = Decimal("0")
            overtime = Decimal("0")

            if not absent:
                base_in = time(8, 0)
                ci_hour = 8
                ci_min = late_mins if late else random.randint(0, 10)
                if ci_min >= 60:
                    ci_hour += 1
                    ci_min -= 60
                check_in = time(ci_hour, ci_min)

                co_hour = random.choice([17, 17, 17, 18, 18, 19])
                co_min = random.randint(0, 59)
                check_out = time(co_hour, co_min)

                ci_total = ci_hour * 60 + ci_min
                co_total = co_hour * 60 + co_min
                minutes_worked = co_total - ci_total
                hours_worked = Decimal(str(round(minutes_worked / 60, 2)))
                overtime = Decimal(str(max(0, round((co_total - 17 * 60) / 60, 2))))

            records.append(Attendance(
                employee=emp,
                date=d,
                check_in=check_in,
                check_out=check_out,
                hours_worked=hours_worked,
                overtime_hours=overtime,
                is_present=not absent,
                is_late=late,
                late_minutes=late_mins,
            ))

            created += 1
            d -= timedelta(days=1)

        Attendance.objects.bulk_create(records, ignore_conflicts=True)
        self.stdout.write(f"    Created {len(records)} attendance records.")

    # ------------------------------------------------------------------
    # Payslips: last 6 months, status = paid
    # ------------------------------------------------------------------
    def _seed_payslips(self, emp, today):
        from erp.models import Payroll

        self.stdout.write("  Seeding payslips...")
        currency = emp.currency
        basic = emp.basic_salary or Decimal("5000")
        housing = (basic * Decimal("0.25")).quantize(Decimal("0.01"))
        transport = (basic * Decimal("0.10")).quantize(Decimal("0.01"))
        social = (basic * Decimal("0.09")).quantize(Decimal("0.01"))
        tax = (basic * Decimal("0.05")).quantize(Decimal("0.01"))

        created = 0
        for i in range(1, 7):
            # period: 1st to last day of month, going back i months
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1

            import calendar
            last_day = calendar.monthrange(year, month)[1]
            period_start = date(year, month, 1)
            period_end = date(year, month, last_day)
            payment_date = date(year, month, last_day)

            if Payroll.objects.filter(employee=emp, period_start=period_start, period_end=period_end).exists():
                continue

            bonus = Decimal("500") if month in (1, 7) else Decimal("0")
            gross = basic + housing + transport + bonus
            deductions = social + tax
            net = gross - deductions

            Payroll.objects.create(
                employee=emp,
                period_start=period_start,
                period_end=period_end,
                basic_salary=basic,
                housing_allowance=housing,
                transport_allowance=transport,
                bonus=bonus,
                social_insurance=social,
                tax_deduction=tax,
                gross_salary=gross,
                total_deductions=deductions,
                net_salary=net,
                status="paid",
                payment_date=payment_date,
                currency=currency,
            )
            created += 1

        self.stdout.write(f"    Created {created} payslip(s).")

    # ------------------------------------------------------------------
    # Leave requests: approved, pending, rejected
    # ------------------------------------------------------------------
    def _seed_leaves(self, emp, today):
        from erp.models import LeaveRequest, LeaveType

        self.stdout.write("  Seeding leave requests...")

        try:
            annual = LeaveType.objects.get(code="ANNUAL")
        except LeaveType.DoesNotExist:
            annual = LeaveType.objects.filter(name__icontains="annual").first()
        try:
            sick = LeaveType.objects.get(code="SICK")
        except LeaveType.DoesNotExist:
            sick = LeaveType.objects.filter(name__icontains="sick").first()

        if not annual or not sick:
            self.stdout.write(self.style.WARNING("    Leave types not found, skipping."))
            return

        leaves = [
            # approved annual leave ~3 months ago
            dict(
                leave_type=annual,
                start_date=today - timedelta(days=90),
                end_date=today - timedelta(days=85),
                days_requested=Decimal("5"),
                reason="Family vacation",
                status="approved",
                approval_date=timezone.now() - timedelta(days=92),
            ),
            # approved sick leave ~1 month ago
            dict(
                leave_type=sick,
                start_date=today - timedelta(days=30),
                end_date=today - timedelta(days=29),
                days_requested=Decimal("2"),
                reason="Medical appointment",
                status="approved",
                approval_date=timezone.now() - timedelta(days=31),
            ),
            # rejected leave
            dict(
                leave_type=annual,
                start_date=today - timedelta(days=15),
                end_date=today - timedelta(days=13),
                days_requested=Decimal("3"),
                reason="Personal matter",
                status="rejected",
                approval_date=timezone.now() - timedelta(days=16),
            ),
            # pending future leave
            dict(
                leave_type=annual,
                start_date=today + timedelta(days=14),
                end_date=today + timedelta(days=18),
                days_requested=Decimal("5"),
                reason="Annual holiday",
                status="pending",
                approval_date=None,
            ),
        ]

        created = 0
        for lv in leaves:
            if LeaveRequest.objects.filter(
                employee=emp,
                start_date=lv["start_date"],
                leave_type=lv["leave_type"],
            ).exists():
                continue
            LeaveRequest.objects.create(employee=emp, **lv)
            created += 1

        self.stdout.write(f"    Created {created} leave request(s).")

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------
    def _seed_tasks(self, emp, today):
        from erp.models import Task

        self.stdout.write("  Seeding tasks...")

        tasks_data = [
            dict(
                title="Complete Q2 performance review",
                description="Fill in the self-assessment form and submit to HR before the deadline.",
                priority="high",
                status="todo",
                due_date=timezone.make_aware(datetime.combine(today + timedelta(days=7), time(17, 0))),
            ),
            dict(
                title="Update personal contact details",
                description="Verify and update emergency contact and bank account information in the HR portal.",
                priority="medium",
                status="in_progress",
                due_date=timezone.make_aware(datetime.combine(today + timedelta(days=3), time(17, 0))),
            ),
            dict(
                title="Submit expense claims for April",
                description="Upload receipts and complete the expense claim form for April travel.",
                priority="high",
                status="completed",
                due_date=timezone.make_aware(datetime.combine(today - timedelta(days=5), time(17, 0))),
                completed_date=timezone.now() - timedelta(days=4),
            ),
            dict(
                title="Attend company safety training",
                description="Mandatory safety training session in the main conference room.",
                priority="urgent",
                status="todo",
                due_date=timezone.make_aware(datetime.combine(today + timedelta(days=2), time(10, 0))),
            ),
            dict(
                title="Review and sign updated employment contract",
                description="Read the revised contract terms and sign the digital copy sent by HR.",
                priority="high",
                status="todo",
                due_date=timezone.make_aware(datetime.combine(today + timedelta(days=5), time(17, 0))),
            ),
            dict(
                title="Prepare monthly team report",
                description="Compile team progress summary for May and share with the manager.",
                priority="medium",
                status="in_progress",
                due_date=timezone.make_aware(datetime.combine(today + timedelta(days=10), time(17, 0))),
            ),
            dict(
                title="Onboarding checklist for new hire",
                description="Help orient the new team member joining next Monday.",
                priority="low",
                status="completed",
                due_date=timezone.make_aware(datetime.combine(today - timedelta(days=10), time(17, 0))),
                completed_date=timezone.now() - timedelta(days=9),
            ),
            dict(
                title="Book annual medical checkup",
                description="Schedule the company-sponsored annual health checkup at the approved clinic.",
                priority="low",
                status="todo",
                due_date=timezone.make_aware(datetime.combine(today + timedelta(days=20), time(17, 0))),
            ),
        ]

        created = 0
        for td in tasks_data:
            if Task.objects.filter(assigned_to=emp, title=td["title"]).exists():
                continue
            Task.objects.create(company=emp.company, assigned_to=emp, **td)
            created += 1

        self.stdout.write(f"    Created {created} task(s).")

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def _seed_notifications(self, user, emp, today):
        from erp.models import Notification

        self.stdout.write("  Seeding notifications...")

        notifs = [
            dict(
                notification_type="success",
                title="Leave request approved",
                message="Your annual leave request for 5 days (Apr 5 – Apr 10) has been approved.",
                is_read=True,
            ),
            dict(
                notification_type="info",
                title="Payslip available",
                message="Your payslip for April 2026 is now available. Net pay: $4,275.00.",
                is_read=True,
            ),
            dict(
                notification_type="warning",
                title="Leave request rejected",
                message="Your leave request for Apr 19 – Apr 21 was rejected. Please contact HR.",
                is_read=False,
            ),
            dict(
                notification_type="task",
                title="New task assigned",
                message="You have been assigned: 'Complete Q2 performance review' due in 7 days.",
                is_read=False,
            ),
            dict(
                notification_type="reminder",
                title="Safety training tomorrow",
                message="Reminder: Mandatory safety training session is scheduled for tomorrow at 10:00 AM.",
                is_read=False,
            ),
            dict(
                notification_type="info",
                title="Payslip available",
                message="Your payslip for March 2026 is now available. Net pay: $4,275.00.",
                is_read=True,
            ),
            dict(
                notification_type="approval",
                title="Leave request pending",
                message="Your leave request for May 18 – May 22 is awaiting manager approval.",
                is_read=False,
            ),
            dict(
                notification_type="success",
                title="Expense claim processed",
                message="Your April expense claim of $320.00 has been processed and will be reimbursed.",
                is_read=True,
            ),
        ]

        created = 0
        for n in notifs:
            Notification.objects.create(recipient=user, **n)
            created += 1

        self.stdout.write(f"    Created {created} notification(s).")
