"""Tests for admin-mobile auth endpoints (login, logout, change-password, device-register)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from erp.tests.helpers import ERPAPITestCase
from erp.tests.test_admin_mobile.helpers import (
    AdminMobileAPITestCase,
    grant_admin_assignment,
)

LOGIN_URL = '/api/mobile/admin/v1/auth/login/'
LOGOUT_URL = '/api/mobile/admin/v1/auth/logout/'
CHANGE_PW_URL = '/api/mobile/admin/v1/auth/change-password/'
DEVICE_URL = '/api/mobile/admin/v1/devices/register/'


class _TenantDbCleanupMixin:
    """Ensures Django's test teardown doesn't trip over tenant DBs added by login.

    ``erp.api.admin_mobile.views.auth.admin_login`` calls
    ``tenants.routers.get_tenant_db_alias`` which calls
    ``add_tenant_database`` — this inserts a new alias into
    ``settings.DATABASES`` and Django's ``connections`` map.  Django's
    ``_remove_databases_failures`` teardown then tries to unpatch methods
    on that connection and fails because it was created after the test
    case's class-level patching.  We undo it at the end of every test.
    """

    def tearDown(self):
        from django.conf import settings
        from django.db import connections

        for alias in list(settings.DATABASES):
            if alias.startswith('tenant_'):
                try:
                    connections[alias].close()
                except Exception:
                    pass
                if hasattr(connections, '_connections') and hasattr(
                    connections._connections, alias,
                ):
                    delattr(connections._connections, alias)
                settings.DATABASES.pop(alias, None)
        super().tearDown()


class AdminLoginTests(_TenantDbCleanupMixin, AdminMobileAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user.is_approved = True
        cls.user.save(update_fields=['is_approved'])

    def test_login_succeeds_for_admin(self):
        client = APIClient()
        resp = client.post(
            LOGIN_URL,
            {'email': self.user.email, 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertTrue(body['token'])
        self.assertEqual(body['role'], 'admin')
        self.assertEqual(body['employee']['id'], self.employee.pk)
        self.assertEqual(body['company']['id'], self.company.pk)
        self.assertIn('ai_enabled', body['feature_flags'])

    def test_login_rejects_wrong_password(self):
        client = APIClient()
        resp = client.post(
            LOGIN_URL,
            {'email': self.user.email, 'password': 'wrong'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_requires_both_fields(self):
        resp = APIClient().post(LOGIN_URL, {'email': self.user.email}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class AdminLoginRejectionTests(_TenantDbCleanupMixin, ERPAPITestCase):
    def test_login_rejects_non_admin(self):
        # self.user has no DatabaseAssignment → must be refused.
        client = APIClient()
        resp = client.post(
            LOGIN_URL,
            {'email': self.user.email, 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_rejects_plain_user_role(self):
        grant_admin_assignment(self.user, role='user')  # 'user' is not admin/owner
        resp = APIClient().post(
            LOGIN_URL,
            {'email': self.user.email, 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AdminLogoutTests(AdminMobileAPITestCase):
    def test_logout_invalidates_token(self):
        resp = self.admin_client.post(LOGOUT_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Subsequent request with the same token must fail.
        resp2 = self.admin_client.get('/api/mobile/admin/v1/auth/me/')
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminChangePasswordTests(AdminMobileAPITestCase):
    def test_change_password_happy_path(self):
        resp = self.admin_client.post(
            CHANGE_PW_URL,
            {'old_password': 'TestPass123!', 'new_password': 'NewSecretPw99!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecretPw99!'))

    def test_change_password_wrong_old_rejected(self):
        resp = self.admin_client.post(
            CHANGE_PW_URL,
            {'old_password': 'nope', 'new_password': 'NewSecretPw99!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_rejects_short_new_password(self):
        resp = self.admin_client.post(
            CHANGE_PW_URL,
            {'old_password': 'TestPass123!', 'new_password': 'short'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class AdminDeviceRegisterTests(AdminMobileAPITestCase):
    def test_register_android_device(self):
        resp = self.admin_client.post(
            DEVICE_URL,
            {'token': 'fcm-abc-123', 'platform': 'android'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_register_rejects_invalid_platform(self):
        resp = self.admin_client.post(
            DEVICE_URL,
            {'token': 'abc', 'platform': 'windows'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
