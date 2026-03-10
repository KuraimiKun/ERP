"""
Tests for Audit models: AuditLog, SystemSetting.
"""

import json
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError

from erp.models import AuditLog, SystemSetting
from erp.tests.helpers import ERPTestCase


class AuditLogModelTest(ERPTestCase):

    def test_create_log(self):
        ct = ContentType.objects.get_for_model(self.company)
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditLog.Action.CREATE,
            content_type=ct,
            object_id=self.company.pk,
            object_repr=str(self.company),
            changes={'name': {'old': '', 'new': 'Test Company'}},
        )
        self.assertIn('create', str(log))

    def test_action_choices(self):
        actions = [c[0] for c in AuditLog.Action.choices]
        self.assertIn('create', actions)
        self.assertIn('update', actions)
        self.assertIn('delete', actions)
        self.assertIn('approve', actions)

    def test_ordering_newest_first(self):
        ct = ContentType.objects.get_for_model(self.company)
        AuditLog.objects.create(
            user=self.user, action='create',
            content_type=ct, object_repr='First',
        )
        l2 = AuditLog.objects.create(
            user=self.user, action='update',
            content_type=ct, object_repr='Second',
        )
        logs = list(AuditLog.objects.all())
        self.assertEqual(logs[0], l2)

    def test_generic_foreign_key(self):
        ct = ContentType.objects.get_for_model(self.company)
        log = AuditLog.objects.create(
            user=self.user, action='view',
            content_type=ct, object_id=self.company.pk,
            object_repr=str(self.company),
        )
        self.assertEqual(log.content_object, self.company)


class SystemSettingModelTest(ERPTestCase):

    def test_create_string_setting(self):
        s = SystemSetting.objects.create(
            company=self.company, key='company_name',
            value='Test Corp', setting_type='string',
        )
        self.assertEqual(s.get_value(), 'Test Corp')

    def test_integer_setting(self):
        s = SystemSetting.objects.create(
            company=self.company, key='max_retries',
            value='5', setting_type='integer',
        )
        self.assertEqual(s.get_value(), 5)
        self.assertIsInstance(s.get_value(), int)

    def test_decimal_setting(self):
        s = SystemSetting.objects.create(
            company=self.company, key='tax_rate',
            value='15.5', setting_type='decimal',
        )
        self.assertEqual(s.get_value(), Decimal('15.5'))

    def test_boolean_setting_true(self):
        s = SystemSetting.objects.create(
            company=self.company, key='email_enabled',
            value='true', setting_type='boolean',
        )
        self.assertTrue(s.get_value())

    def test_boolean_setting_false(self):
        s = SystemSetting.objects.create(
            company=self.company, key='debug_mode',
            value='false', setting_type='boolean',
        )
        self.assertFalse(s.get_value())

    def test_json_setting(self):
        data = {'smtp_host': 'mail.example.com', 'port': 587}
        s = SystemSetting.objects.create(
            company=self.company, key='email_config',
            value=json.dumps(data), setting_type='json',
        )
        self.assertEqual(s.get_value(), data)

    def test_unique_together_company_key(self):
        SystemSetting.objects.create(
            company=self.company, key='unique_key', value='v1',
        )
        with self.assertRaises(IntegrityError):
            SystemSetting.objects.create(
                company=self.company, key='unique_key', value='v2',
            )

    def test_str_representation(self):
        s = SystemSetting.objects.create(
            company=self.company, key='test_key', value='v',
        )
        self.assertEqual(str(s), 'test_key')
