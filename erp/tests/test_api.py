"""
API ViewSet Tests

Tests for authentication, company isolation, CRUD operations, custom
actions, filtering, and soft-delete across key API ViewSets.
"""

from datetime import date, timedelta
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from erp.models import (
    Department, Customer, Invoice,
    LeaveType, LeaveRequest, Lead, Notification, Expense, Employee,
)
from erp.tests.helpers import ERPAPITestCase

# ──────────────────────────────────────────────────────────────────────────────
# Authentication & Permission
# ──────────────────────────────────────────────────────────────────────────────

class TestAPIAuthentication(ERPAPITestCase):
    """Verify auth enforcement on API endpoints."""

    def test_unauthenticated_request_denied(self):
        client = APIClient()  # no credentials
        response = client.get('/api/v1/departments/')
        # SessionAuthentication + IsAuthenticated returns 403 for anonymous
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_invalid_token_denied(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token invalidtokenvalue')
        response = client.get('/api/v1/departments/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_authenticated_user_with_employee_succeeds(self):
        response = self.client.get('/api/v1/departments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_without_employee_returns_403(self):
        """User without employee_profile should get 403 on company-scoped endpoints."""
        orphan_user = type(self).user.__class__.objects.create_user(
            email='orphan@example.com', password='Pass123!',
        )
        orphan_token = Token.objects.create(user=orphan_user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {orphan_token.key}')
        response = client.get('/api/v1/departments/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ──────────────────────────────────────────────────────────────────────────────
# Company Isolation
# ──────────────────────────────────────────────────────────────────────────────

class TestCompanyIsolation(ERPAPITestCase):
    """Ensure users can only see their own company's data."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_user, cls.other_company, cls.other_employee, cls.other_token = (
            cls.create_other_company_user()
        )
        # Create a department in the other company
        cls.other_dept = Department.objects.create(
            company=cls.other_company, name='Other Dept', code='OTH',
            is_active=True, created_by=cls.other_user,
        )

    def test_user_sees_only_own_company_departments(self):
        response = self.client.get('/api/v1/departments/')
        self.assertEqual(response.status_code, 200)
        dept_names = [d['name'] for d in response.data['results']]
        self.assertIn('Engineering', dept_names)
        self.assertNotIn('Other Dept', dept_names)

    def test_other_user_sees_only_own_departments(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')
        response = client.get('/api/v1/departments/')
        dept_names = [d['name'] for d in response.data['results']]
        self.assertIn('Other Dept', dept_names)
        self.assertNotIn('Engineering', dept_names)

    def test_user_cannot_access_other_company_customer_by_id(self):
        other_customer = Customer.objects.create(
            company=self.other_company, customer_id='CUS-OTHER',
            name='Secret Corp', email='secret@other.com',
            currency=self.currency, created_by=self.other_user,
        )
        response = self.client.get(f'/api/v1/customers/{other_customer.pk}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ──────────────────────────────────────────────────────────────────────────────
# Department CRUD
# ──────────────────────────────────────────────────────────────────────────────

class TestDepartmentAPI(ERPAPITestCase):
    """CRUD + search/filter for departments."""

    def test_list_departments(self):
        response = self.client.get('/api/v1/departments/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_create_department(self):
        response = self.client.post('/api/v1/departments/', {
            'name': 'Marketing', 'code': 'MKT', 'is_active': True,
            'company': self.company.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Marketing')

    def test_update_department(self):
        response = self.client.patch(
            f'/api/v1/departments/{self.department.pk}/',
            {'name': 'Engineering v2'},
        )
        self.assertEqual(response.status_code, 200)
        self.department.refresh_from_db()
        self.assertEqual(self.department.name, 'Engineering v2')

    def test_delete_department_soft_deletes(self):
        dept = Department.objects.create(
            company=self.company, name='Temp Dept', code='TMP',
            is_active=True, created_by=self.user,
        )
        response = self.client.delete(f'/api/v1/departments/{dept.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        dept.refresh_from_db()
        self.assertTrue(dept.is_deleted)

    def test_soft_deleted_excluded_from_list(self):
        dept = Department.objects.create(
            company=self.company, name='Deleted Dept', code='DEL',
            is_active=True, created_by=self.user,
        )
        dept.soft_delete(self.user)

        response = self.client.get('/api/v1/departments/')
        dept_names = [d['name'] for d in response.data['results']]
        self.assertNotIn('Deleted Dept', dept_names)

    def test_search_departments(self):
        response = self.client.get('/api/v1/departments/', {'search': 'Engineering'})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_filter_departments_by_is_active(self):
        response = self.client.get('/api/v1/departments/', {'is_active': 'true'})
        self.assertEqual(response.status_code, 200)


# ──────────────────────────────────────────────────────────────────────────────
# Customer API
# ──────────────────────────────────────────────────────────────────────────────

class TestCustomerAPI(ERPAPITestCase):
    """CRUD and custom actions for customers."""

    def test_list_customers(self):
        response = self.client.get('/api/v1/customers/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_create_customer(self):
        response = self.client.post('/api/v1/customers/', {
            'company': self.company.pk,
            'customer_id': 'CUS-NEW',
            'name': 'New Customer',
            'email': 'new@customer.com',
            'currency': self.currency.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_retrieve_customer(self):
        response = self.client.get(f'/api/v1/customers/{self.customer.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Acme LLC')

    def test_customer_invoices_action(self):
        Invoice.objects.create(
            company=self.company, customer=self.customer,
            invoice_number='INV-API-001', invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=self.currency, created_by=self.user,
        )
        response = self.client.get(f'/api/v1/customers/{self.customer.pk}/invoices/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

    def test_customer_statement_action(self):
        response = self.client.get(f'/api/v1/customers/{self.customer.pk}/statement/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('balance', response.data)
        self.assertIn('invoices', response.data)

    def test_search_customers(self):
        response = self.client.get('/api/v1/customers/', {'search': 'Acme'})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)


# ──────────────────────────────────────────────────────────────────────────────
# Invoice API
# ──────────────────────────────────────────────────────────────────────────────

class TestInvoiceAPI(ERPAPITestCase):
    """CRUD and custom actions for invoices."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.invoice = Invoice.objects.create(
            company=cls.company, customer=cls.customer,
            invoice_number='INV-TEST-001',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=cls.currency, created_by=cls.user,
        )

    def test_list_invoices(self):
        response = self.client.get('/api/v1/invoices/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_retrieve_invoice(self):
        response = self.client.get(f'/api/v1/invoices/{self.invoice.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['invoice_number'], 'INV-TEST-001')

    def test_overdue_action(self):
        response = self.client.get('/api/v1/invoices/overdue/')
        self.assertEqual(response.status_code, 200)

    def test_summary_action(self):
        response = self.client.get('/api/v1/invoices/summary/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_count', response.data)
        self.assertIn('outstanding', response.data)

    def test_filter_by_status(self):
        response = self.client.get('/api/v1/invoices/', {'status': 'draft'})
        self.assertEqual(response.status_code, 200)


# ──────────────────────────────────────────────────────────────────────────────
# Employee API
# ──────────────────────────────────────────────────────────────────────────────

class TestEmployeeAPI(ERPAPITestCase):
    """Employee ViewSet tests including custom actions."""

    def test_list_employees(self):
        response = self.client.get('/api/v1/employees/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_me_action(self):
        response = self.client.get('/api/v1/employees/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['employee_id'], 'EMP-0001')

    def test_me_action_without_profile_returns_404(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        orphan = User.objects.create_user(email='noprofile@test.com', password='Pass123!')
        token = Token.objects.create(user=orphan)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        # This will hit the me endpoint; the user has no employee_profile
        # The view returns 404 if no profile exists
        response = client.get('/api/v1/employees/me/')
        self.assertIn(response.status_code, [403, 404])

    def test_employee_attendance_action(self):
        response = self.client.get(f'/api/v1/employees/{self.employee.pk}/attendance/')
        self.assertEqual(response.status_code, 200)

    def test_search_employees(self):
        response = self.client.get('/api/v1/employees/', {'search': 'Ahmad'})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)


# ──────────────────────────────────────────────────────────────────────────────
# Leave Request API
# ──────────────────────────────────────────────────────────────────────────────

class TestLeaveRequestAPI(ERPAPITestCase):
    """Leave request CRUD and approve/reject actions."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.leave_type = LeaveType.objects.create(
            name='Annual Leave', code='AL',
            days_allowed=21, is_active=True, is_paid=True,
        )

    def _create_leave_request(self):
        return LeaveRequest.objects.create(
            employee=Employee.objects.create(company=self.company, department=self.department, branch=self.branch, employee_id=('EMP-OTHER-'+str(abs(hash(self))))[:20], first_name='Other', last_name='Employee', email='other'+str(abs(hash(self)))+'@company.com', hire_date=date.today(), date_of_birth=date(1990, 1, 1), basic_salary=1000, currency=self.currency, reports_to=self.employee), leave_type=self.leave_type,
            start_date=date(2026, 6, 1), end_date=date(2026, 6, 5),
            days_requested=5, status='pending',
            created_by=self.user,
        )

    def test_list_leave_requests(self):
        self._create_leave_request()
        response = self.client.get('/api/v1/leave-requests/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_approve_leave_request(self):
        lr = self._create_leave_request()
        response = self.client.post(f'/api/v1/leave-requests/{lr.pk}/approve/')
        self.assertEqual(response.status_code, 200)
        lr.refresh_from_db()
        self.assertEqual(lr.status, 'approved')

    def test_reject_leave_request(self):
        lr = self._create_leave_request()
        response = self.client.post(
            f'/api/v1/leave-requests/{lr.pk}/reject/',
            {'reason': 'Scheduling conflict'},
        )
        self.assertEqual(response.status_code, 200)
        lr.refresh_from_db()
        self.assertEqual(lr.status, 'rejected')

    def test_approve_non_pending_returns_400(self):
        lr = self._create_leave_request()
        lr.status = 'approved'
        lr.save()
        response = self.client.post(f'/api/v1/leave-requests/{lr.pk}/approve/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_non_pending_returns_400(self):
        lr = self._create_leave_request()
        lr.status = 'approved'
        lr.save()
        response = self.client.post(f'/api/v1/leave-requests/{lr.pk}/reject/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ──────────────────────────────────────────────────────────────────────────────
# Lead API
# ──────────────────────────────────────────────────────────────────────────────

class TestLeadAPI(ERPAPITestCase):
    """Lead ViewSet CRUD and custom actions."""

    def _create_lead(self, **kwargs):
        defaults = {
            'company': self.company,
            'lead_number': 'LEAD-001',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@lead.com',
            'status': 'new',
            'created_by': self.user,
        }
        defaults.update(kwargs)
        return Lead.objects.create(**defaults)

    def test_list_leads(self):
        self._create_lead()
        response = self.client.get('/api/v1/leads/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_retrieve_lead(self):
        lead = self._create_lead()
        response = self.client.get(f'/api/v1/leads/{lead.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'john@lead.com')

    def test_pipeline_action(self):
        self._create_lead()
        response = self.client.get('/api/v1/leads/pipeline/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_convert_lead_to_customer(self):
        lead = self._create_lead()
        response = self.client.post(f'/api/v1/leads/{lead.pk}/convert/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('customer', response.data)
        lead.refresh_from_db()
        self.assertEqual(lead.status, 'won')

    def test_convert_already_won_returns_400(self):
        lead = self._create_lead(status='won')
        response = self.client.post(f'/api/v1/leads/{lead.pk}/convert/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ──────────────────────────────────────────────────────────────────────────────
# Notification API
# ──────────────────────────────────────────────────────────────────────────────

class TestNotificationAPI(ERPAPITestCase):
    """Notification ViewSet tests — scoped to current user."""

    def _create_notification(self, user=None, is_read=False):
        return Notification.objects.create(
            recipient=user or self.user,
            title='Test Notification',
            message='Something happened.',
            is_read=is_read,
        )

    def test_list_own_notifications(self):
        self._create_notification()
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_unread_action(self):
        self._create_notification(is_read=False)
        self._create_notification(is_read=True)
        response = self.client.get('/api/v1/notifications/unread/')
        self.assertEqual(response.status_code, 200)
        for notif in response.data:
            self.assertFalse(notif['is_read'])

    def test_mark_read_action(self):
        notif = self._create_notification()
        response = self.client.post(f'/api/v1/notifications/{notif.pk}/mark_read/')
        self.assertEqual(response.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_all_read_action(self):
        self._create_notification()
        self._create_notification()
        response = self.client.post('/api/v1/notifications/mark_all_read/')
        self.assertEqual(response.status_code, 200)
        unread = Notification.objects.filter(recipient=self.user, is_read=False).count()
        self.assertEqual(unread, 0)


# ──────────────────────────────────────────────────────────────────────────────
# Expense API
# ──────────────────────────────────────────────────────────────────────────────

class TestExpenseAPI(ERPAPITestCase):
    """Expense approve action."""

    def _create_expense(self):
        return Expense.objects.create(
            company=self.company,
            expense_number='EXP-001',
            expense_date=date.today(),
            category=self.expense_category,
            description='Test expense',
            currency=self.currency,
            amount=Decimal('250.00'),
            total_amount=Decimal('250.00'),
            status='pending',
            employee=Employee.objects.create(company=self.company, department=self.department, branch=self.branch, employee_id=('EMP-OTHER-'+str(abs(hash(self))))[:20], first_name='Other', last_name='Employee', email='other'+str(abs(hash(self)))+'@company.com', hire_date=date.today(), date_of_birth=date(1990, 1, 1), basic_salary=1000, currency=self.currency, reports_to=self.employee),
            created_by=self.user,
        )

    def test_approve_expense(self):
        expense = self._create_expense()
        response = self.client.post(f'/api/v1/expenses/{expense.pk}/approve/')
        self.assertEqual(response.status_code, 200)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'approved')

    def test_approve_non_pending_returns_400(self):
        expense = self._create_expense()
        expense.status = 'approved'
        expense.save()
        response = self.client.post(f'/api/v1/expenses/{expense.pk}/approve/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
