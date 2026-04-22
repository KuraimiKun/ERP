"""Shared helpers for admin-mobile API tests.

``AdminMobileAPITestCase`` extends ``ERPAPITestCase`` with a minimal
``PostgresServer`` / ``TenantDatabase`` / ``DatabaseAssignment`` chain so
the ``IsCompanyAdmin`` permission has a real row to inspect.
"""

from __future__ import annotations

from rest_framework.test import APIClient

from erp.tests.helpers import ERPAPITestCase
from tenants.models import (
    DatabaseAssignment,
    PostgresServer,
    TenantDatabase,
)


def grant_admin_assignment(user, role: str = 'admin') -> DatabaseAssignment:
    """Create (or update) an active ``DatabaseAssignment`` for ``user``.

    Creates a minimal ``PostgresServer`` + ``TenantDatabase`` chain the
    first time it is called; subsequent calls reuse them so a single test
    class can grant admin rights to several users without constraint
    clashes.  ``role`` must be one of the choices on
    ``DatabaseAssignment`` — ``owner``, ``admin``, ``user``, ``readonly``.
    """
    server, _ = PostgresServer.objects.get_or_create(
        name='test-server',
        defaults={
            'server_type': 'docker',
            'host': 'localhost',
            'port': 5432,
            'admin_username': 'postgres',
            'admin_password': 'test-password',
            'status': 'active',
        },
    )
    tenant_db, _ = TenantDatabase.objects.get_or_create(
        server=server,
        name='tenant_test',
        defaults={
            'display_name': 'Tenant Test DB',
            'db_username': 'tenant_test_user',
            'status': 'active',
        },
    )
    # Deactivate any existing assignment so ``is_active=True`` remains
    # unique-ish per (user, database).
    DatabaseAssignment.objects.filter(user=user, database=tenant_db).update(
        is_active=False,
    )
    return DatabaseAssignment.objects.create(
        user=user,
        database=tenant_db,
        role=role,
        is_active=True,
    )


class AdminMobileAPITestCase(ERPAPITestCase):
    """Base for admin-mobile API tests.

    On top of ``ERPAPITestCase`` (company, employee, token), this:
    * promotes the default ``cls.user`` to role ``admin`` via a real
      ``DatabaseAssignment`` row so ``IsCompanyAdmin`` passes;
    * exposes ``self.admin_client`` — an ``APIClient`` pre-authenticated
      with that user's token.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_assignment = grant_admin_assignment(cls.user, role='admin')

    def setUp(self):
        super().setUp()
        self.admin_client = APIClient()
        self.admin_client.credentials(
            HTTP_AUTHORIZATION=f'Token {self.token.key}'
        )
