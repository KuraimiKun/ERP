"""
Signal Tests

Tests for audit signals (create/update/delete logging),
invoice line total sync signals, and auth event signals.
"""

from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model

from erp.models import (
    AuditLog,
    Department,
    Invoice,
    InvoiceLine,
)
from erp.services.audit import _audit_thread_locals
from erp.tests.helpers import ERPTestCase

User = get_user_model()


class _AuditContextMixin:
    """Set up the thread-local audit context that signals depend on."""

    def _set_audit_context(self, user, ip="127.0.0.1"):
        _audit_thread_locals.user = user
        _audit_thread_locals.ip_address = ip
        _audit_thread_locals.user_agent = "test-agent"

    def _clear_audit_context(self):
        _audit_thread_locals.user = None
        _audit_thread_locals.ip_address = None
        _audit_thread_locals.user_agent = ""


class TestAuditSignals(_AuditContextMixin, ERPTestCase):
    """Test that model create/update/delete signals produce AuditLog entries."""

    def setUp(self):
        self._set_audit_context(self.user)

    def tearDown(self):
        self._clear_audit_context()

    def test_create_department_logs_create(self):
        dept = Department.objects.create(
            company=self.company,
            name="Finance",
            code="FIN",
            is_active=True,
            created_by=self.user,
        )
        log = AuditLog.objects.filter(
            action="create",
            object_id=dept.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.user)

    def test_update_department_logs_update_with_changes(self):
        dept = Department.objects.create(
            company=self.company,
            name="HR",
            code="HR",
            is_active=True,
            created_by=self.user,
        )
        # Clear create log
        AuditLog.objects.filter(object_id=dept.pk).delete()

        dept.name = "Human Resources"
        dept.save()

        log = AuditLog.objects.filter(
            action="update",
            object_id=dept.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("name", log.changes)
        self.assertEqual(log.changes["name"]["before"], "HR")
        self.assertEqual(log.changes["name"]["after"], "Human Resources")

    def test_delete_department_logs_delete(self):
        dept = Department.objects.create(
            company=self.company,
            name="Temp",
            code="TMP",
            is_active=True,
            created_by=self.user,
        )
        dept_pk = dept.pk
        dept.delete()

        log = AuditLog.objects.filter(
            action="delete",
            object_id=dept_pk,
        ).first()
        self.assertIsNotNone(log)

    def test_auditlog_save_does_not_recurse(self):
        """Saving an AuditLog row itself must not trigger another audit entry."""
        initial_count = AuditLog.objects.count()
        AuditLog.objects.create(
            user=self.user,
            action="create",
            object_repr="test",
            ip_address="127.0.0.1",
        )
        # Only the one we just created, no recursive entry
        self.assertEqual(AuditLog.objects.count(), initial_count + 1)

    def test_no_audit_log_without_user_context(self):
        """When no user is in the audit context, signals skip logging."""
        self._clear_audit_context()

        initial_count = AuditLog.objects.count()
        Department.objects.create(
            company=self.company,
            name="NoAudit",
            code="NA",
            is_active=True,
            created_by=self.user,
        )
        self.assertEqual(AuditLog.objects.count(), initial_count)

    def test_sensitive_field_redacted(self):
        """Fields with 'password'/'secret' in their name are redacted."""
        from erp.services.audit import get_field_changes, _REDACTED

        class FakeInstance:
            class _meta:
                fields = []

            password_hash = "new"

        class FakeOld:
            password_hash = "old"

        # Build a minimal field mock
        from unittest.mock import MagicMock

        field = MagicMock()
        field.name = "password_hash"
        FakeInstance._meta.fields = [field]

        changes = get_field_changes(FakeInstance(), FakeOld())
        self.assertEqual(changes["password_hash"]["before"], _REDACTED)
        self.assertEqual(changes["password_hash"]["after"], _REDACTED)


class TestInvoiceLineSyncSignals(ERPTestCase):
    """Test that adding/updating/deleting InvoiceLine recalculates Invoice totals."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.invoice = Invoice.objects.create(
            company=cls.company,
            customer=cls.customer,
            invoice_number="INV-SIGNAL-001",
            invoice_date=date(2026, 3, 1),
            due_date=date(2026, 4, 1),
            currency=cls.currency,
            created_by=cls.user,
        )

    def test_adding_line_updates_totals(self):
        InvoiceLine.objects.create(
            invoice=self.invoice,
            description="Service A",
            quantity=Decimal("2"),
            unit_price=Decimal("100"),
            tax_rate=self.zero_tax,
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.subtotal, Decimal("200"))

    def test_updating_line_recalculates_totals(self):
        line = InvoiceLine.objects.create(
            invoice=self.invoice,
            description="Service B",
            quantity=Decimal("1"),
            unit_price=Decimal("50"),
            tax_rate=self.zero_tax,
        )
        self.invoice.refresh_from_db()
        old_total = self.invoice.subtotal

        line.quantity = Decimal("3")
        line.save()

        self.invoice.refresh_from_db()
        self.assertGreater(self.invoice.subtotal, old_total)

    def test_deleting_line_recalculates_totals(self):
        line = InvoiceLine.objects.create(
            invoice=self.invoice,
            description="Service C",
            quantity=Decimal("1"),
            unit_price=Decimal("500"),
            tax_rate=self.zero_tax,
        )
        self.invoice.refresh_from_db()
        total_with_line = self.invoice.subtotal

        line.delete()
        self.invoice.refresh_from_db()
        self.assertLess(self.invoice.subtotal, total_with_line)


class TestAuthSignals(ERPTestCase):
    """Test login/logout audit signals."""

    def test_login_creates_audit_log(self):
        initial_count = AuditLog.objects.filter(action="login").count()
        self.client.login(email="test@example.com", password="TestPass123!")
        self.assertEqual(
            AuditLog.objects.filter(action="login").count(),
            initial_count + 1,
        )

    def test_logout_creates_audit_log(self):
        self.client.login(email="test@example.com", password="TestPass123!")
        initial_count = AuditLog.objects.filter(action="logout").count()
        self.client.logout()
        self.assertEqual(
            AuditLog.objects.filter(action="logout").count(),
            initial_count + 1,
        )

    def test_logout_with_none_user_does_not_fail(self):
        """Logout signal with user=None should not raise."""
        from erp.signals import audit_user_logout

        # Should not raise
        audit_user_logout(sender=None, request=None, user=None)
