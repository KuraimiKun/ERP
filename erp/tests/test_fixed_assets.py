"""
Tests for Fixed Assets models: AssetCategory, FixedAsset, DepreciationSchedule.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError

from erp.models import AssetCategory, FixedAsset
from erp.tests.helpers import ERPTestCase


class AssetCategoryModelTest(ERPTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = AssetCategory.objects.create(
            company=cls.company,
            name="Office Equipment",
            code="OE",
            depreciation_method=AssetCategory.DepreciationMethod.STRAIGHT_LINE,
            useful_life_months=60,
            salvage_value_percent=Decimal("10.00"),
            created_by=cls.user,
        )

    def test_str_with_code(self):
        self.assertEqual(str(self.category), "[OE] Office Equipment")

    def test_str_without_code(self):
        cat = AssetCategory.objects.create(
            company=self.company,
            name="Misc",
            code="",
            created_by=self.user,
        )
        self.assertEqual(str(cat), "Misc")

    def test_unique_together_company_code(self):
        with self.assertRaises(IntegrityError):
            AssetCategory.objects.create(
                company=self.company,
                name="Dup",
                code="OE",
                created_by=self.user,
            )

    def test_depreciation_method_choices(self):
        methods = [c[0] for c in AssetCategory.DepreciationMethod.choices]
        self.assertIn("straight_line", methods)
        self.assertIn("declining_balance", methods)
        self.assertIn("no_depreciation", methods)


class FixedAssetModelTest(ERPTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = AssetCategory.objects.create(
            company=cls.company,
            name="Equipment",
            code="EQ",
            useful_life_months=60,
            depreciation_method="straight_line",
            created_by=cls.user,
        )
        cls.asset = FixedAsset.objects.create(
            company=cls.company,
            asset_number="FA-0001",
            name="Laptop Dell XPS",
            category=cls.category,
            acquisition_date=date(2025, 1, 1),
            acquisition_cost=Decimal("5000.00"),
            salvage_value=Decimal("500.00"),
            currency=cls.currency,
            useful_life_months=60,
            current_book_value=Decimal("5000.00"),
            created_by=cls.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.asset), "FA-0001 – Laptop Dell XPS")

    def test_unique_asset_number(self):
        with self.assertRaises(IntegrityError):
            FixedAsset.objects.create(
                company=self.company,
                asset_number="FA-0001",
                name="Dup",
                category=self.category,
                acquisition_date=date.today(),
                acquisition_cost=Decimal("1000"),
                currency=self.currency,
                created_by=self.user,
            )

    def test_depreciable_amount(self):
        # 5000 - 500 = 4500
        self.assertEqual(self.asset.depreciable_amount, Decimal("4500.00"))

    def test_remaining_book_value(self):
        self.asset.accumulated_depreciation = Decimal("1000.00")
        self.asset.save()
        self.assertEqual(self.asset.remaining_book_value, Decimal("4000.00"))

    def test_straight_line_monthly_depreciation(self):
        # depreciable = 4500, life = 60 months → 75.00/month
        monthly = self.asset.calculate_monthly_depreciation()
        self.assertEqual(monthly, Decimal("75.00"))

    def test_no_depreciation_method(self):
        self.asset.depreciation_method = "no_depreciation"
        self.assertEqual(
            self.asset.calculate_monthly_depreciation(),
            Decimal("0.00"),
        )

    def test_default_status(self):
        self.assertEqual(self.asset.status, FixedAsset.Status.DRAFT)

    def test_soft_delete(self):
        self.asset.soft_delete(user=self.user)
        self.assertFalse(FixedAsset.objects.filter(pk=self.asset.pk).exists())
        self.asset.restore()
        self.assertTrue(FixedAsset.objects.filter(pk=self.asset.pk).exists())

    def test_get_account_fallback_to_category(self):
        """Asset-level account is None → falls back to category."""
        self.assertIsNone(self.asset.asset_account)
        self.category.asset_account = self.cash_account
        self.category.save()
        self.assertEqual(
            self.asset.get_account("asset_account"),
            self.cash_account,
        )
