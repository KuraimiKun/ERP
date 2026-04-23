"""Unit tests for the ``IsCompanyAdmin`` permission class.

Covers the full permission matrix the plan mandates:

* unauthenticated → denied
* authenticated but no employee profile → denied
* employee profile exists, no ``DatabaseAssignment`` → denied
* ``DatabaseAssignment`` with role ``user`` / ``readonly`` → denied
* ``DatabaseAssignment`` with role ``admin`` / ``owner`` → allowed
* inactive assignment → denied
* superuser without any assignment → allowed (platform support escape hatch)
"""

from __future__ import annotations

from unittest.mock import Mock

from django.test import RequestFactory

from erp.api.permissions import IsCompanyAdmin
from erp.tests.helpers import ERPAPITestCase
from erp.tests.test_admin_mobile.helpers import grant_admin_assignment


class IsCompanyAdminTests(ERPAPITestCase):
    """Direct unit tests against the permission class."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.permission = IsCompanyAdmin()
        # Link user ↔ employee so company_id is populated.
        self.employee.user = self.user
        self.employee.save(update_fields=["user"])

    def _request(self, user):
        req = self.factory.get("/api/mobile/admin/v1/auth/me/")
        req.user = user
        return req

    def test_denied_for_anonymous(self):
        anonymous = Mock(is_authenticated=False)
        self.assertFalse(self.permission.has_permission(self._request(anonymous), None))

    def test_denied_without_employee_profile(self):
        self.user.refresh_from_db()
        # A fresh user with no Employee linked.
        from django.contrib.auth import get_user_model

        User = get_user_model()
        lone = User.objects.create_user(
            email="lone@example.com",
            password="p",
            first_name="Lone",
            last_name="Wolf",
        )
        self.assertFalse(self.permission.has_permission(self._request(lone), None))

    def test_denied_without_assignment(self):
        # Employee linked but no DatabaseAssignment row exists.
        self.assertFalse(self.permission.has_permission(self._request(self.user), None))

    def test_denied_for_user_role(self):
        grant_admin_assignment(self.user, role="user")
        self.assertFalse(self.permission.has_permission(self._request(self.user), None))

    def test_denied_for_readonly_role(self):
        grant_admin_assignment(self.user, role="readonly")
        self.assertFalse(self.permission.has_permission(self._request(self.user), None))

    def test_allowed_for_admin_role(self):
        grant_admin_assignment(self.user, role="admin")
        self.assertTrue(self.permission.has_permission(self._request(self.user), None))

    def test_allowed_for_owner_role(self):
        grant_admin_assignment(self.user, role="owner")
        self.assertTrue(self.permission.has_permission(self._request(self.user), None))

    def test_denied_when_assignment_inactive(self):
        assignment = grant_admin_assignment(self.user, role="admin")
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        self.assertFalse(self.permission.has_permission(self._request(self.user), None))

    def test_allowed_for_superuser_without_assignment(self):
        # Platform-support superuser escape hatch — no DatabaseAssignment needed.
        self.assertTrue(self.permission.has_permission(self._request(self.admin_user), None))
