"""Tests for admin-mobile reports, search, notifications, company endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from rest_framework import status

from erp.models import Notification
from erp.tests.test_admin_mobile.helpers import AdminMobileAPITestCase


class FinancialReportTests(AdminMobileAPITestCase):
    def test_trial_balance_returns_json(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/reports/trial-balance/',
            {'start': '2025-01-01', 'end': '2025-12-31'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.json(), dict)

    def test_profit_and_loss_returns_json(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/reports/profit-and-loss/',
            {'start': '2025-01-01', 'end': '2025-12-31'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_balance_sheet_requires_as_of_or_fiscal_year(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/reports/balance-sheet/',
            {'as_of': '2025-12-31'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_trial_balance_rejects_invalid_date(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/reports/trial-balance/',
            {'start': 'nope', 'end': '2025-12-31'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class OperationalReportTests(AdminMobileAPITestCase):
    def test_sales_summary(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/reports/sales-summary/',
            {'period': 'month'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body['period'], 'month')
        self.assertIn('revenue', body)

    def test_sales_summary_rejects_bad_period(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/reports/sales-summary/',
            {'period': 'decade'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_aging_receivables(self):
        resp = self.admin_client.get('/api/mobile/admin/v1/reports/aging-receivables/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        for key in ('0-30', '31-60', '61-90', '90+', 'total'):
            self.assertIn(key, body)


class SearchTests(AdminMobileAPITestCase):
    def test_search_finds_customer(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/search/', {'q': 'Acme'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertIn('customer', body['results'])
        self.assertTrue(
            any(c['name'] == 'Acme LLC' for c in body['results']['customer']),
        )

    def test_search_requires_query(self):
        resp = self.admin_client.get('/api/mobile/admin/v1/search/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_restricts_by_type(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/search/',
            {'q': 'Acme', 'types': 'customer'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(set(resp.json()['results'].keys()), {'customer'})

    def test_search_rejects_unknown_type(self):
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/search/',
            {'q': 'x', 'types': 'martians'},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class NotificationTests(AdminMobileAPITestCase):
    def _make_notification(self, is_read=False):
        return Notification.objects.create(
            recipient=self.user,
            notification_type='info',
            title='Test',
            message='hi',
            is_read=is_read,
        )

    def test_unread_count(self):
        self._make_notification()
        self._make_notification(is_read=True)
        resp = self.admin_client.get(
            '/api/mobile/admin/v1/notifications/unread-count/',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['count'], 1)

    def test_mark_all_read(self):
        self._make_notification()
        self._make_notification()
        resp = self.admin_client.post(
            '/api/mobile/admin/v1/notifications/read-all/',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 0)

    def test_mark_selected_read(self):
        n = self._make_notification()
        resp = self.admin_client.post(
            '/api/mobile/admin/v1/notifications/read/',
            {'ids': [n.pk]}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        n.refresh_from_db()
        self.assertTrue(n.is_read)


class CompanyEndpointTests(AdminMobileAPITestCase):
    def test_company_detail(self):
        resp = self.admin_client.get('/api/mobile/admin/v1/company/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['id'], self.company.pk)

    def test_company_patch_whitelisted(self):
        resp = self.admin_client.patch(
            '/api/mobile/admin/v1/company/',
            {'city': 'Jeddah'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.company.refresh_from_db()
        self.assertEqual(self.company.city, 'Jeddah')

    def test_company_patch_ignores_unknown_fields(self):
        resp = self.admin_client.patch(
            '/api/mobile/admin/v1/company/',
            {'tax_id': 'HACKED'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class MastersCRUDSmokeTests(AdminMobileAPITestCase):
    """Lightweight smoke tests on the registered router endpoints."""

    def test_customers_list(self):
        resp = self.admin_client.get('/api/mobile/admin/v1/customers/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()['count'], 1)

    def test_products_list(self):
        resp = self.admin_client.get('/api/mobile/admin/v1/products/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_warehouses_list(self):
        resp = self.admin_client.get('/api/mobile/admin/v1/warehouses/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_employees_list(self):
        resp = self.admin_client.get('/api/mobile/admin/v1/employees/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()['count'], 1)

    def test_accounts_list(self):
        resp = self.admin_client.get('/api/mobile/admin/v1/accounts/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
