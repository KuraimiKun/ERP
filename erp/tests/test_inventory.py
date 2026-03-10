"""
Tests for Inventory models: UoM, UoMConversion, Warehouse, Zone, Bin,
LotBatch, SerialNumber, StockItem, StockMovement.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone

from erp.models import (
    UnitOfMeasure, UnitOfMeasureConversion,
    Warehouse, WarehouseZone, WarehouseBin,
    LotBatch, SerialNumber, StockItem, StockMovement,
)
from erp.tests.helpers import ERPTestCase


# ────────────────────────────────────────────────────────────────
# Unit of Measure
# ────────────────────────────────────────────────────────────────

class UnitOfMeasureModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.uom_kg = UnitOfMeasure.objects.create(
            company=cls.company, name='Kilogram', abbreviation='kg',
            category='weight', is_base=True,
        )
        cls.uom_g = UnitOfMeasure.objects.create(
            company=cls.company, name='Gram', abbreviation='g',
            category='weight',
        )

    def test_str_representation(self):
        self.assertEqual(str(self.uom_kg), 'kg – Kilogram')

    def test_unique_abbreviation_per_company(self):
        with self.assertRaises(IntegrityError):
            UnitOfMeasure.objects.create(
                company=self.company, name='Kg Dup', abbreviation='kg',
                category='weight',
            )


class UoMConversionTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.uom_kg = UnitOfMeasure.objects.create(
            company=cls.company, name='Kilogram', abbreviation='kg2',
            category='weight', is_base=True,
        )
        cls.uom_g = UnitOfMeasure.objects.create(
            company=cls.company, name='Gram', abbreviation='g2',
            category='weight',
        )

    def test_create_conversion(self):
        conv = UnitOfMeasureConversion.objects.create(
            company=self.company,
            from_uom=self.uom_kg, to_uom=self.uom_g,
            factor=Decimal('1000'),
        )
        self.assertEqual(str(conv), '1 kg2 = 1000 g2')

    def test_unique_together_conversion(self):
        UnitOfMeasureConversion.objects.create(
            company=self.company,
            from_uom=self.uom_kg, to_uom=self.uom_g,
            factor=Decimal('1000'),
        )
        with self.assertRaises(IntegrityError):
            UnitOfMeasureConversion.objects.create(
                company=self.company,
                from_uom=self.uom_kg, to_uom=self.uom_g,
                factor=Decimal('500'),
            )


# ────────────────────────────────────────────────────────────────
# Warehouse / Zone / Bin
# ────────────────────────────────────────────────────────────────

class WarehouseHierarchyTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.zone = WarehouseZone.objects.create(
            warehouse=cls.warehouse, code='A',
            name='Zone A', zone_type=WarehouseZone.ZoneType.STORAGE,
        )
        cls.bin = WarehouseBin.objects.create(
            zone=cls.zone, code='A-01-01', name='Shelf 1',
        )

    def test_warehouse_str(self):
        self.assertEqual(str(self.warehouse), 'WH1 – Main Warehouse')

    def test_zone_str(self):
        self.assertEqual(str(self.zone), 'WH1/A – Zone A')

    def test_bin_str(self):
        self.assertEqual(str(self.bin), 'WH1/A/A-01-01')

    def test_unique_zone_code_per_warehouse(self):
        with self.assertRaises(IntegrityError):
            WarehouseZone.objects.create(
                warehouse=self.warehouse, code='A', name='Dup',
            )

    def test_unique_bin_code_per_zone(self):
        with self.assertRaises(IntegrityError):
            WarehouseBin.objects.create(zone=self.zone, code='A-01-01')

    def test_zone_types(self):
        receiving = WarehouseZone.objects.create(
            warehouse=self.warehouse, code='R',
            name='Receiving', zone_type='receiving',
        )
        self.assertEqual(receiving.zone_type, 'receiving')

    def test_warehouse_soft_delete(self):
        self.warehouse.soft_delete(user=self.user)
        self.assertFalse(Warehouse.objects.filter(pk=self.warehouse.pk).exists())
        self.warehouse.restore()
        self.assertTrue(Warehouse.objects.filter(pk=self.warehouse.pk).exists())


# ────────────────────────────────────────────────────────────────
# Lot / Batch
# ────────────────────────────────────────────────────────────────

class LotBatchModelTest(ERPTestCase):

    def test_create_lot(self):
        lot = LotBatch.objects.create(
            company=self.company, product=self.product,
            lot_number='LOT-001',
            manufacture_date=date(2026, 1, 1),
            expiry_date=date(2027, 1, 1),
            created_by=self.user,
        )
        self.assertIn('LOT-001', str(lot))

    def test_is_expired_false(self):
        lot = LotBatch.objects.create(
            company=self.company, product=self.product,
            lot_number='LOT-FUT',
            expiry_date=date.today() + timedelta(days=365),
            created_by=self.user,
        )
        self.assertFalse(lot.is_expired)

    def test_is_expired_true(self):
        lot = LotBatch.objects.create(
            company=self.company, product=self.product,
            lot_number='LOT-EXP',
            expiry_date=date.today() - timedelta(days=1),
            created_by=self.user,
        )
        self.assertTrue(lot.is_expired)

    def test_is_expired_none(self):
        lot = LotBatch.objects.create(
            company=self.company, product=self.product,
            lot_number='LOT-NOEXP',
            created_by=self.user,
        )
        self.assertFalse(lot.is_expired)

    def test_unique_together(self):
        LotBatch.objects.create(
            company=self.company, product=self.product,
            lot_number='LOT-DUP', created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            LotBatch.objects.create(
                company=self.company, product=self.product,
                lot_number='LOT-DUP', created_by=self.user,
            )


# ────────────────────────────────────────────────────────────────
# Serial Number
# ────────────────────────────────────────────────────────────────

class SerialNumberModelTest(ERPTestCase):

    def test_create_serial(self):
        sn = SerialNumber.objects.create(
            company=self.company, product=self.product,
            serial_number='SN-00001',
            warehouse=self.warehouse,
        )
        self.assertEqual(sn.status, SerialNumber.Status.AVAILABLE)
        self.assertIn('SN-00001', str(sn))

    def test_unique_serial_per_product(self):
        SerialNumber.objects.create(
            company=self.company, product=self.product,
            serial_number='SN-UNQ',
        )
        with self.assertRaises(IntegrityError):
            SerialNumber.objects.create(
                company=self.company, product=self.product,
                serial_number='SN-UNQ',
            )


# ────────────────────────────────────────────────────────────────
# Stock Item
# ────────────────────────────────────────────────────────────────

class StockItemModelTest(ERPTestCase):

    def test_create_stock_item(self):
        si = StockItem.objects.create(
            company=self.company, product=self.product,
            warehouse=self.warehouse,
            on_hand=Decimal('100'), allocated=Decimal('20'),
        )
        self.assertEqual(si.available, Decimal('80'))

    def test_available_property_with_zero_allocated(self):
        si = StockItem.objects.create(
            company=self.company, product=self.product,
            warehouse=self.warehouse,
            on_hand=Decimal('50'),
        )
        self.assertEqual(si.available, Decimal('50'))

    def test_str_representation(self):
        si = StockItem.objects.create(
            company=self.company, product=self.product,
            warehouse=self.warehouse,
            on_hand=Decimal('100'),
        )
        self.assertIn('PROD-0001', str(si))
        self.assertIn('WH1', str(si))


# ────────────────────────────────────────────────────────────────
# Stock Movement
# ────────────────────────────────────────────────────────────────

class StockMovementModelTest(ERPTestCase):

    def test_create_movement(self):
        mv = StockMovement.objects.create(
            company=self.company,
            movement_type=StockMovement.MovementType.PURCHASE_RECEIPT,
            product=self.product,
            warehouse=self.warehouse,
            quantity=Decimal('50'),
            unit_cost=Decimal('100'),
            total_cost=Decimal('5000'),
            performed_by=self.user,
        )
        self.assertEqual(mv.movement_type, 'purchase_receipt')

    def test_movement_types_inbound_outbound(self):
        inbound = StockMovement.objects.create(
            company=self.company,
            movement_type=StockMovement.MovementType.PURCHASE_RECEIPT,
            product=self.product, warehouse=self.warehouse,
            quantity=Decimal('10'),
        )
        outbound = StockMovement.objects.create(
            company=self.company,
            movement_type=StockMovement.MovementType.SALES_ISSUE,
            product=self.product, warehouse=self.warehouse,
            quantity=Decimal('3'),
        )
        self.assertEqual(inbound.movement_type, 'purchase_receipt')
        self.assertEqual(outbound.movement_type, 'sales_issue')
