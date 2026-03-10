"""
Tests for POS models: POSTerminal, POSSession, POSOrder.
"""

from decimal import Decimal

from django.db import IntegrityError
from django.utils import timezone

from erp.models import (
    POSTerminal, POSSession, POSOrder,
)
from erp.tests.helpers import ERPTestCase


class POSTerminalModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.terminal = POSTerminal.objects.create(
            company=cls.company,
            name='Cashier 1',
            code='POS-01',
            warehouse=cls.warehouse,
            created_by=cls.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.terminal), 'POS-01 - Cashier 1')

    def test_unique_code_per_company(self):
        with self.assertRaises(IntegrityError):
            POSTerminal.objects.create(
                company=self.company, name='Dup',
                code='POS-01', warehouse=self.warehouse,
                created_by=self.user,
            )

    def test_default_active(self):
        self.assertTrue(self.terminal.is_active)

    def test_soft_delete(self):
        self.terminal.soft_delete(user=self.user)
        self.assertFalse(POSTerminal.objects.filter(pk=self.terminal.pk).exists())
        self.terminal.restore()
        self.assertTrue(POSTerminal.objects.filter(pk=self.terminal.pk).exists())


class POSSessionModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.terminal = POSTerminal.objects.create(
            company=cls.company, name='T1', code='POS-S1',
            warehouse=cls.warehouse, created_by=cls.user,
        )
        cls.session = POSSession.objects.create(
            company=cls.company,
            terminal=cls.terminal,
            session_number='SESS-001',
            opened_by=cls.employee,
            opening_balance=Decimal('500.00'),
            created_by=cls.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.session), 'POS-S1 - SESS-001')

    def test_default_status_open(self):
        self.assertEqual(self.session.status, POSSession.Status.OPEN)

    def test_close_session(self):
        self.session.status = POSSession.Status.CLOSED
        self.session.closed_by = self.employee
        self.session.closing_balance = Decimal('1200.00')
        self.session.closed_at = timezone.now()
        self.session.save()
        self.assertEqual(self.session.status, 'closed')

    def test_cash_difference_calculation(self):
        self.session.expected_cash = Decimal('1100.00')
        self.session.closing_balance = Decimal('1080.00')
        self.session.cash_difference = (
            self.session.closing_balance - self.session.expected_cash
        )
        self.session.save()
        self.assertEqual(self.session.cash_difference, Decimal('-20.00'))


class POSOrderModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.terminal = POSTerminal.objects.create(
            company=cls.company, name='T2', code='POS-O1',
            warehouse=cls.warehouse, created_by=cls.user,
        )
        cls.session = POSSession.objects.create(
            company=cls.company, terminal=cls.terminal,
            session_number='SESS-O1', opened_by=cls.employee,
            created_by=cls.user,
        )

    def test_create_order(self):
        order = POSOrder.objects.create(
            company=self.company,
            session=self.session,
            order_number='POS-ORD-001',
            employee=self.employee,
            subtotal=Decimal('100'),
            tax_amount=Decimal('15'),
            total_amount=Decimal('115'),
            created_by=self.user,
        )
        self.assertEqual(order.status, POSOrder.Status.DRAFT)

    def test_unique_order_number(self):
        POSOrder.objects.create(
            company=self.company, session=self.session,
            order_number='POS-UNQ', employee=self.employee,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            POSOrder.objects.create(
                company=self.company, session=self.session,
                order_number='POS-UNQ', employee=self.employee,
                created_by=self.user,
            )
