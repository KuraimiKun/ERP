"""
Tests for HR models: Employee, LeaveType, LeaveRequest, Attendance, Payroll.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.db import IntegrityError

from erp.models import (
    Employee, LeaveType, LeaveRequest, Attendance, Payroll,
    PayrollEarning, PayrollDeduction,
)
from erp.tests.helpers import ERPTestCase


# ────────────────────────────────────────────────────────────────
# Employee
# ────────────────────────────────────────────────────────────────

class EmployeeModelTest(ERPTestCase):

    def test_str_representation(self):
        self.assertEqual(str(self.employee), 'Ahmad Ali (EMP-0001)')

    def test_full_name(self):
        self.assertEqual(self.employee.full_name, 'Ahmad Ali')

    def test_unique_employee_id(self):
        with self.assertRaises(IntegrityError):
            Employee.objects.create(
                company=self.company, employee_id='EMP-0001',
                first_name='Sara', last_name='X',
                gender='female', date_of_birth=date(1995, 1, 1),
                nationality='Saudi', email='s@x.com', phone='123',
                job_title='Dev', hire_date=date(2024, 1, 1),
                basic_salary=5000, currency=self.currency,
            )

    def test_default_employment_status(self):
        self.assertEqual(self.employee.employment_status, 'active')

    def test_default_approval_status(self):
        self.assertEqual(self.employee.approval_status, 'approved')

    def test_portal_permissions_defaults(self):
        self.assertTrue(self.employee.portal_can_scan_qr)
        self.assertTrue(self.employee.portal_can_view_attendance)
        self.assertTrue(self.employee.portal_can_manage_leaves)
        self.assertTrue(self.employee.portal_can_view_payslips)
        self.assertTrue(self.employee.portal_can_edit_profile)
        self.assertTrue(self.employee.portal_can_view_tasks)
        self.assertFalse(self.employee.portal_can_use_pos)

    def test_soft_delete_and_restore(self):
        self.employee.soft_delete(user=self.user)
        self.assertFalse(Employee.objects.filter(pk=self.employee.pk).exists())
        self.employee.restore()
        self.assertTrue(Employee.objects.filter(pk=self.employee.pk).exists())

    def test_reporting_hierarchy(self):
        manager = Employee.objects.create(
            company=self.company, employee_id='EMP-MGR',
            first_name='Boss', last_name='Man',
            gender='male', date_of_birth=date(1985, 1, 1),
            nationality='Saudi', email='boss@test.com', phone='555',
            job_title='Manager', hire_date=date(2020, 1, 1),
            basic_salary=15000, currency=self.currency,
            created_by=self.user,
        )
        self.employee.reports_to = manager
        self.employee.save()
        self.assertIn(self.employee, manager.subordinates.all())

    def test_full_name_ar(self):
        self.employee.first_name_ar = 'أحمد'
        self.employee.last_name_ar = 'علي'
        self.employee.save()
        self.assertEqual(self.employee.full_name_ar, 'أحمد علي')


# ────────────────────────────────────────────────────────────────
# Leave Type & Leave Request
# ────────────────────────────────────────────────────────────────

class LeaveTypeModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.leave_type = LeaveType.objects.create(
            name='Annual Leave', code='AL',
            days_allowed=21, is_paid=True,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.leave_type), 'Annual Leave')

    def test_unique_code(self):
        with self.assertRaises(IntegrityError):
            LeaveType.objects.create(name='Dup', code='AL')


class LeaveRequestModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.leave_type = LeaveType.objects.create(
            name='Annual Leave', code='ALR',
            days_allowed=21, is_paid=True,
        )

    def test_create_leave_request(self):
        lr = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            days_requested=Decimal('3'),
            reason='Vacation',
            created_by=self.user,
        )
        self.assertEqual(lr.status, LeaveRequest.Status.PENDING)

    def test_leave_request_approval(self):
        lr = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            days_requested=Decimal('2'),
            created_by=self.user,
        )
        lr.status = LeaveRequest.Status.APPROVED
        lr.approved_by = self.employee
        lr.save()
        self.assertEqual(lr.status, 'approved')


# ────────────────────────────────────────────────────────────────
# Attendance
# ────────────────────────────────────────────────────────────────

class AttendanceModelTest(ERPTestCase):

    def test_create_attendance(self):
        att = Attendance.objects.create(
            employee=self.employee,
            date=date.today(),
            check_in=time(8, 0),
            check_out=time(17, 0),
            hours_worked=Decimal('8'),
            is_present=True,
        )
        self.assertTrue(att.is_present)
        self.assertEqual(att.hours_worked, Decimal('8'))

    def test_unique_together_employee_date(self):
        Attendance.objects.create(
            employee=self.employee, date=date.today(),
            check_in=time(8, 0), is_present=True,
        )
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(
                employee=self.employee, date=date.today(),
                check_in=time(9, 0), is_present=True,
            )

    def test_late_tracking(self):
        att = Attendance.objects.create(
            employee=self.employee,
            date=date.today() - timedelta(days=1),
            check_in=time(8, 30),
            is_present=True, is_late=True, late_minutes=30,
        )
        self.assertTrue(att.is_late)
        self.assertEqual(att.late_minutes, 30)


# ────────────────────────────────────────────────────────────────
# Payroll
# ────────────────────────────────────────────────────────────────

class PayrollModelTest(ERPTestCase):

    def _create_payroll(self):
        return Payroll.objects.create(
            employee=self.employee,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            basic_salary=Decimal('10000'),
            currency=self.currency,
            status='draft',
            created_by=self.user,
        )

    def test_str_representation(self):
        pr = self._create_payroll()
        self.assertIn('Ahmad Ali', str(pr))

    def test_default_status(self):
        pr = self._create_payroll()
        self.assertEqual(pr.status, 'draft')

    def test_calculate_totals_from_earning_lines(self):
        pr = self._create_payroll()
        PayrollEarning.objects.create(
            payroll=pr, earning_type='basic_salary',
            description='Basic', amount=Decimal('10000'),
        )
        PayrollEarning.objects.create(
            payroll=pr, earning_type='housing_allowance',
            description='Housing', amount=Decimal('2500'),
        )
        PayrollDeduction.objects.create(
            payroll=pr, deduction_type='social_insurance',
            description='GOSI', amount=Decimal('1000'),
        )
        pr.calculate_totals()
        self.assertEqual(pr.gross_salary, Decimal('12500'))
        self.assertEqual(pr.total_deductions, Decimal('1000'))
        self.assertEqual(pr.net_salary, Decimal('11500'))

    def test_unique_together_employee_period(self):
        self._create_payroll()
        with self.assertRaises(IntegrityError):
            Payroll.objects.create(
                employee=self.employee,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                basic_salary=Decimal('10000'),
                currency=self.currency,
                created_by=self.user,
            )

    def test_sync_legacy_fields(self):
        pr = self._create_payroll()
        PayrollEarning.objects.create(
            payroll=pr, earning_type='basic_salary',
            description='Basic', amount=Decimal('10000'),
        )
        PayrollEarning.objects.create(
            payroll=pr, earning_type='overtime',
            description='OT', amount=Decimal('500'),
        )
        pr.calculate_totals()
        self.assertEqual(pr.basic_salary, Decimal('10000'))
        self.assertEqual(pr.overtime_amount, Decimal('500'))
