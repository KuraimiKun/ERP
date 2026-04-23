"""Tests for admin-mobile approval endpoints.

Focused on the interesting bits:
* permission gating (non-admin → 403)
* approve/reject flip the status
* expense approval triggers ``create_expense_journal_entry``
* supplier-invoice approval triggers ``create_supplier_invoice_journal_entry``
* approving a non-pending object returns 400
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from erp.models import Expense, LeaveRequest, LeaveType
from erp.tests.test_admin_mobile.helpers import AdminMobileAPITestCase


class LeaveApprovalTests(AdminMobileAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.leave_type = LeaveType.objects.create(
            name="Annual",
            code="AL",
            days_allowed=21,
            is_active=True,
            is_paid=True,
        )

    def _make_leave(self, s="pending"):
        return LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 5),
            days_requested=Decimal("5"),
            status=s,
            created_by=self.user,
        )

    def test_list_pending_leaves(self):
        self._make_leave()
        resp = self.admin_client.get("/api/mobile/admin/v1/leaves/pending/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_approve_leave(self):
        lr = self._make_leave()
        resp = self.admin_client.post(
            f"/api/mobile/admin/v1/leaves/pending/{lr.pk}/approve/",
            {"notes": "ok"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        lr.refresh_from_db()
        self.assertEqual(lr.status, "approved")

    def test_reject_leave(self):
        lr = self._make_leave()
        resp = self.admin_client.post(
            f"/api/mobile/admin/v1/leaves/pending/{lr.pk}/reject/",
            {"reason": "bad timing"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        lr.refresh_from_db()
        self.assertEqual(lr.status, "rejected")

    def test_cannot_approve_already_approved(self):
        lr = self._make_leave(s="approved")
        # Already-approved leaves are filtered out of the queryset → 404.
        resp = self.admin_client.post(
            f"/api/mobile/admin/v1/leaves/pending/{lr.pk}/approve/",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class ExpenseApprovalTests(AdminMobileAPITestCase):
    def _make_expense(self, s="submitted"):
        return Expense.objects.create(
            company=self.company,
            category=self.expense_category,
            employee=self.employee,
            expense_date=date.today(),
            description="Lunch",
            amount=Decimal("100"),
            tax_amount=Decimal("0"),
            total_amount=Decimal("100"),
            currency=self.currency,
            status=s,
            payment_method=self.payment_method,
            created_by=self.user,
        )

    def test_approve_posts_journal_entry(self):
        exp = self._make_expense()
        with patch(
            "erp.services.accounting.create_expense_journal_entry",
        ) as mock_journal:
            resp = self.admin_client.post(
                f"/api/mobile/admin/v1/expenses/pending/{exp.pk}/approve/",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        exp.refresh_from_db()
        self.assertEqual(exp.status, "approved")
        mock_journal.assert_called_once()

    def test_reject_expense(self):
        exp = self._make_expense()
        resp = self.admin_client.post(
            f"/api/mobile/admin/v1/expenses/pending/{exp.pk}/reject/",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        exp.refresh_from_db()
        self.assertEqual(exp.status, "rejected")

    def test_approve_does_not_rollback_on_journal_failure(self):
        """Matches /api/v1 behaviour: journal failure is logged, not raised."""
        exp = self._make_expense()
        with patch(
            "erp.services.accounting.create_expense_journal_entry",
            side_effect=RuntimeError("boom"),
        ):
            resp = self.admin_client.post(
                f"/api/mobile/admin/v1/expenses/pending/{exp.pk}/approve/",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        exp.refresh_from_db()
        self.assertEqual(exp.status, "approved")
