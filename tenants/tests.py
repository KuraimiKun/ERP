"""
Tests for Tenant models: TenantUser, PostgresServer, TenantDatabase, DatabaseAssignment.
"""

from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone

from tenants.models import (
    TenantUser, PostgresServer, TenantDatabase, DatabaseAssignment,
)


class TenantUserModelTest(TestCase):

    def test_create_user(self):
        user = TenantUser.objects.create_user(
            email='user@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe',
        )
        self.assertEqual(user.email, 'user@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_no_email_raises(self):
        with self.assertRaises(ValueError):
            TenantUser.objects.create_user(email='', password='pw')

    def test_create_superuser(self):
        su = TenantUser.objects.create_superuser(
            email='admin@example.com',
            password='adminpass',
            first_name='Admin',
            last_name='User',
        )
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_superuser)
        self.assertTrue(su.is_approved)
        self.assertEqual(su.approval_status, 'approved')

    def test_create_superuser_must_be_staff(self):
        with self.assertRaises(ValueError):
            TenantUser.objects.create_superuser(
                email='x@x.com', password='p',
                first_name='X', last_name='Y', is_staff=False,
            )

    def test_str_representation(self):
        user = TenantUser.objects.create_user(
            email='str@test.com', password='pw',
            first_name='A', last_name='B',
        )
        self.assertEqual(str(user), 'str@test.com')

    def test_get_full_name(self):
        user = TenantUser.objects.create_user(
            email='fn@test.com', password='pw',
            first_name='Hassan', last_name='Ahmed',
        )
        self.assertEqual(user.get_full_name(), 'Hassan Ahmed')

    def test_default_approval_status(self):
        user = TenantUser.objects.create_user(
            email='pending@test.com', password='pw',
            first_name='P', last_name='Q',
        )
        self.assertEqual(user.approval_status, 'pending')
        self.assertFalse(user.is_approved)

    def test_approve(self):
        admin = TenantUser.objects.create_superuser(
            email='adm@test.com', password='pw',
            first_name='Admin', last_name='A',
        )
        user = TenantUser.objects.create_user(
            email='app@test.com', password='pw',
            first_name='U', last_name='V',
        )
        user.approve(approved_by=admin)
        user.refresh_from_db()
        self.assertTrue(user.is_approved)
        self.assertEqual(user.approval_status, 'approved')
        self.assertEqual(user.approved_by, admin)
        self.assertIsNotNone(user.approved_at)

    def test_reject(self):
        user = TenantUser.objects.create_user(
            email='rej@test.com', password='pw',
            first_name='U', last_name='V',
        )
        user.reject(reason='Incomplete info')
        user.refresh_from_db()
        self.assertFalse(user.is_approved)
        self.assertEqual(user.approval_status, 'rejected')
        self.assertEqual(user.rejection_reason, 'Incomplete info')

    def test_suspend(self):
        user = TenantUser.objects.create_user(
            email='sus@test.com', password='pw',
            first_name='S', last_name='S',
        )
        user.suspend()
        user.refresh_from_db()
        self.assertFalse(user.is_approved)
        self.assertFalse(user.is_active)
        self.assertEqual(user.approval_status, 'suspended')

    def test_assigned_database_none(self):
        user = TenantUser.objects.create_user(
            email='no_db@test.com', password='pw',
            first_name='N', last_name='N',
        )
        self.assertIsNone(user.assigned_database)

    def test_unique_email(self):
        TenantUser.objects.create_user(
            email='unq@test.com', password='pw',
            first_name='A', last_name='B',
        )
        with self.assertRaises(IntegrityError):
            TenantUser.objects.create_user(
                email='unq@test.com', password='pw2',
                first_name='C', last_name='D',
            )


class PostgresServerModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.server = PostgresServer.objects.create(
            name='Server-1',
            server_type='docker',
            host='localhost',
            port=5432,
            admin_username='postgres',
            admin_password='secret',
            max_databases=5,
            status='active',
        )

    def test_str_representation(self):
        self.assertEqual(str(self.server), 'Server-1 (Local Docker Container)')

    def test_database_count_zero(self):
        self.assertEqual(self.server.database_count, 0)

    def test_available_slots(self):
        self.assertEqual(self.server.available_slots, 5)

    def test_is_full_false(self):
        self.assertFalse(self.server.is_full)

    def test_unique_name(self):
        with self.assertRaises(IntegrityError):
            PostgresServer.objects.create(
                name='Server-1', host='localhost',
                admin_password='x',
            )


class TenantDatabaseModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.server = PostgresServer.objects.create(
            name='DB-Server',
            host='localhost', port=5432,
            admin_username='postgres', admin_password='pw',
            max_databases=50,
        )

    def test_create_database(self):
        db = TenantDatabase.objects.create(
            server=self.server,
            name='erp_tenant_abc',
            db_username='user_abc',
            status='active',
        )
        self.assertIn('DB-Server', str(db))

    def test_auto_generate_name_and_username(self):
        db = TenantDatabase(server=self.server)
        db.save()
        self.assertTrue(db.name.startswith('erp_tenant_'))
        self.assertTrue(db.db_username.startswith('user_'))

    def test_connection_config(self):
        db = TenantDatabase.objects.create(
            server=self.server,
            name='test_db',
            db_username='test_user',
            db_password='test_pw',
        )
        cfg = db.connection_config
        self.assertEqual(cfg['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(cfg['NAME'], 'test_db')
        self.assertEqual(cfg['USER'], 'test_user')
        self.assertEqual(cfg['PASSWORD'], 'test_pw')
        self.assertEqual(cfg['HOST'], 'localhost')

    def test_unique_together_server_name(self):
        TenantDatabase.objects.create(
            server=self.server, name='unq_db',
            db_username='u1',
        )
        with self.assertRaises(IntegrityError):
            TenantDatabase.objects.create(
                server=self.server, name='unq_db',
                db_username='u2',
            )

    def test_server_database_count(self):
        TenantDatabase.objects.create(
            server=self.server, name='db1', db_username='u1',
        )
        TenantDatabase.objects.create(
            server=self.server, name='db2', db_username='u2',
        )
        self.assertEqual(self.server.database_count, 2)
        self.assertEqual(self.server.available_slots, 48)


class DatabaseAssignmentModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = TenantUser.objects.create_user(
            email='assign@test.com', password='pw',
            first_name='A', last_name='B',
        )
        cls.server = PostgresServer.objects.create(
            name='Assign-Server', host='localhost',
            admin_password='pw', max_databases=50,
        )
        cls.database = TenantDatabase.objects.create(
            server=cls.server, name='assign_db',
            db_username='u1', status='active',
        )

    def test_create_assignment(self):
        assignment = DatabaseAssignment.objects.create(
            user=self.user, database=self.database,
            role='owner',
        )
        self.assertTrue(assignment.is_active)
        self.assertEqual(assignment.role, 'owner')

    def test_assigned_database_property(self):
        DatabaseAssignment.objects.create(
            user=self.user, database=self.database,
            role='admin', is_active=True,
        )
        self.assertEqual(self.user.assigned_database, self.database)

    def test_inactive_assignment_not_returned(self):
        DatabaseAssignment.objects.create(
            user=self.user, database=self.database,
            is_active=False,
        )
        self.assertIsNone(self.user.assigned_database)
