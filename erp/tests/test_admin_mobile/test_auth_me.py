"""End-to-end tests for the ``/api/mobile/admin/v1/auth/me/`` smoke endpoint.

Verifies the full request path through the admin-mobile URL mount,
``DefaultDbTokenAuthentication``, and ``IsCompanyAdmin``.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.test import APIClient

from erp.tests.helpers import ERPAPITestCase
from erp.tests.test_admin_mobile.helpers import (
    AdminMobileAPITestCase,
    grant_admin_assignment,
)

AUTH_ME_URL = '/api/mobile/admin/v1/auth/me/'


class AdminAuthMeTests(AdminMobileAPITestCase):
    """Happy-path tests — caller has admin DatabaseAssignment."""

    def test_returns_200_for_admin(self):
        resp = self.admin_client.get(AUTH_ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body['user']['email'], self.user.email)
        self.assertEqual(body['role'], 'admin')
        # Employee and company should both be populated by the test fixture.
        self.assertIsNotNone(body['employee'])
        self.assertEqual(body['employee']['id'], self.employee.pk)
        self.assertIsNotNone(body['company'])
        self.assertEqual(body['company']['id'], self.company.pk)

    def test_role_reflects_owner_assignment(self):
        # Deactivate the default 'admin' assignment and grant 'owner'.
        self.admin_assignment.is_active = False
        self.admin_assignment.save(update_fields=['is_active'])
        grant_admin_assignment(self.user, role='owner')
        resp = self.admin_client.get(AUTH_ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['role'], 'owner')


class AdminAuthMeRejectionTests(ERPAPITestCase):
    """Caller lacks admin rights — endpoint must refuse."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_unauthenticated_rejected(self):
        client = APIClient()  # no credentials
        resp = client.get(AUTH_ME_URL)
        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_non_admin_rejected(self):
        # Authenticated but no admin DatabaseAssignment exists.
        resp = self.client.get(AUTH_ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_role_rejected(self):
        grant_admin_assignment(self.user, role='user')
        resp = self.client.get(AUTH_ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
