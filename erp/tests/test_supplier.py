"""
Tests for Supplier model.
"""

from decimal import Decimal

from django.db import IntegrityError

from erp.models import Supplier
from erp.tests.helpers import ERPTestCase


class SupplierModelTest(ERPTestCase):

    def test_str_representation(self):
        self.assertIn(self.supplier.name, str(self.supplier))

    def test_unique_supplier_id(self):
        with self.assertRaises(IntegrityError):
            Supplier.objects.create(
                company=self.company, supplier_id='SUP-0001',
                supplier_type='other', name='Dup',
                created_by=self.user,
            )

    def test_supplier_type_choices(self):
        for choice_val, _ in Supplier.SupplierType.choices:
            self.supplier.supplier_type = choice_val
            self.supplier.save()
            self.supplier.refresh_from_db()
            self.assertEqual(self.supplier.supplier_type, choice_val)

    def test_soft_delete_and_restore(self):
        self.supplier.soft_delete(user=self.user)
        self.assertFalse(Supplier.objects.filter(pk=self.supplier.pk).exists())
        self.supplier.restore()
        self.assertTrue(Supplier.objects.filter(pk=self.supplier.pk).exists())

    def test_default_balance(self):
        self.assertEqual(self.supplier.current_balance, Decimal('0'))
