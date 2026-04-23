"""Tests for admin-mobile dashboard endpoints."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import status

from erp.tests.test_admin_mobile.helpers import AdminMobileAPITestCase

DASHBOARD_URL = "/api/mobile/admin/v1/dashboard/"
ACTIVITY_URL = "/api/mobile/admin/v1/dashboard/activity/"
KPIS_URL = "/api/mobile/admin/v1/dashboard/kpis/"


class DashboardSummaryTests(AdminMobileAPITestCase):
    def test_dashboard_returns_expected_shape(self):
        resp = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        for key in (
            "today_revenue",
            "cash_in_hand",
            "pending_leave_approvals",
            "pending_expense_approvals",
            "pending_po_approvals",
            "low_stock_items",
            "open_pos_sessions",
            "overdue_invoices_amount",
            "this_month_revenue",
            "this_month_expenses",
        ):
            self.assertIn(key, body, f"missing key {key}")

    def test_dashboard_counts_low_stock(self):
        # Fixture product has quantity 50, reorder 10 → not low.
        resp = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(resp.json()["low_stock_items"], 0)

        # Drop quantity under reorder level to trigger the low-stock count.
        self.product.quantity_on_hand = Decimal("5")
        self.product.save(update_fields=["quantity_on_hand"])
        # Cache bust — the dashboard is cached 5 min per company.
        from django.core.cache import cache

        cache.delete(f"adminmobile:dashboard:{self.company.pk}")

        resp = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(resp.json()["low_stock_items"], 1)


class DashboardKPIsTests(AdminMobileAPITestCase):
    def test_kpis_shape(self):
        resp = self.admin_client.get(KPIS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["period_days"], 30)
        for key in ("revenue", "expenses", "net", "new_customers", "new_leads", "invoices_issued", "payments_received"):
            self.assertIn(key, body)


class DashboardActivityTests(AdminMobileAPITestCase):
    def test_activity_returns_list(self):
        resp = self.admin_client.get(ACTIVITY_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.json(), list)
