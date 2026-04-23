"""
Tests for Services models: ServiceCategory, ServicePricing, ServicePackage,
Product, Quote, QuoteLine.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError

from erp.models import (
    ServiceCategory,
    ServicePricing,
    ServicePackage,
    Product,
    Quote,
    QuoteLine,
)
from erp.tests.helpers import ERPTestCase


# ────────────────────────────────────────────────────────────────
# Service Category
# ────────────────────────────────────────────────────────────────


class ServiceCategoryModelTest(ERPTestCase):
    def test_create_category(self):
        cat = ServiceCategory.objects.create(
            company=self.company,
            name="Travel Services",
            code="TRAV",
        )
        self.assertEqual(str(cat), "Travel Services")

    def test_hierarchical_category(self):
        parent = ServiceCategory.objects.create(
            company=self.company,
            name="Transport",
        )
        child = ServiceCategory.objects.create(
            company=self.company,
            name="Air Transport",
            parent=parent,
        )
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())


# ────────────────────────────────────────────────────────────────
# Service Pricing
# ────────────────────────────────────────────────────────────────


class ServicePricingModelTest(ERPTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.service = ServicePricing.objects.create(
            company=cls.company,
            name="Visa Processing",
            code="SRV-VP",
            base_price=Decimal("500.00"),
            cost_price=Decimal("300.00"),
            currency=cls.currency,
            created_by=cls.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.service), "SRV-VP - Visa Processing")

    def test_profit_margin(self):
        # (500-300)/500 * 100 = 40%
        self.assertEqual(self.service.profit_margin, Decimal("40"))

    def test_profit_margin_zero_price(self):
        srv = ServicePricing.objects.create(
            company=self.company,
            name="Free",
            code="SRV-FREE",
            base_price=Decimal("0"),
            cost_price=Decimal("0"),
            currency=self.currency,
            created_by=self.user,
        )
        self.assertEqual(srv.profit_margin, 0)

    def test_unique_code(self):
        with self.assertRaises(IntegrityError):
            ServicePricing.objects.create(
                company=self.company,
                name="Dup",
                code="SRV-VP",
                currency=self.currency,
                created_by=self.user,
            )


# ────────────────────────────────────────────────────────────────
# Service Package
# ────────────────────────────────────────────────────────────────


class ServicePackageModelTest(ERPTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.package = ServicePackage.objects.create(
            company=cls.company,
            name="VIP Package",
            code="PKG-VIP",
            regular_price=Decimal("1000.00"),
            package_price=Decimal("800.00"),
            cost_price=Decimal("500.00"),
            currency=cls.currency,
            created_by=cls.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.package), "PKG-VIP - VIP Package")

    def test_discount_amount(self):
        self.assertEqual(self.package.discount_amount, Decimal("200.00"))

    def test_discount_percent(self):
        # (1000-800)/1000 * 100 = 20%
        self.assertEqual(self.package.discount_percent, Decimal("20"))

    def test_discount_percent_zero_price(self):
        pkg = ServicePackage.objects.create(
            company=self.company,
            name="Free",
            code="PKG-FREE",
            regular_price=Decimal("0"),
            package_price=Decimal("0"),
            currency=self.currency,
            created_by=self.user,
        )
        self.assertEqual(pkg.discount_percent, 0)


# ────────────────────────────────────────────────────────────────
# Product
# ────────────────────────────────────────────────────────────────


class ProductModelTest(ERPTestCase):
    def test_str_representation(self):
        self.assertEqual(str(self.product), "PROD-0001 - Widget A")

    def test_profit_margin(self):
        # (100-60)/100 * 100 = 40%
        self.assertEqual(self.product.profit_margin, Decimal("40"))

    def test_profit_margin_zero_selling_price(self):
        self.product.selling_price = Decimal("0")
        self.product.save()
        self.assertEqual(self.product.profit_margin, 0)

    def test_is_low_stock_when_below_reorder(self):
        self.product.track_inventory = True
        self.product.quantity_on_hand = Decimal("3")
        self.product.reorder_level = Decimal("5")
        self.product.save()
        self.assertTrue(self.product.is_low_stock)

    def test_is_low_stock_false_when_above_reorder(self):
        self.product.track_inventory = True
        self.product.quantity_on_hand = Decimal("10")
        self.product.reorder_level = Decimal("5")
        self.product.save()
        self.assertFalse(self.product.is_low_stock)

    def test_is_low_stock_false_when_not_tracked(self):
        self.product.track_inventory = False
        self.product.quantity_on_hand = Decimal("0")
        self.product.reorder_level = Decimal("5")
        self.product.save()
        self.assertFalse(self.product.is_low_stock)

    def test_unique_sku(self):
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                company=self.company,
                sku="PROD-0001",
                name="Dup",
                currency=self.currency,
                created_by=self.user,
            )

    def test_soft_delete(self):
        self.product.soft_delete(user=self.user)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.product.restore()
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())


# ────────────────────────────────────────────────────────────────
# Quote
# ────────────────────────────────────────────────────────────────


class QuoteModelTest(ERPTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.quote = Quote.objects.create(
            company=cls.company,
            customer=cls.customer,
            quote_number="QT-0001",
            quote_date=date(2026, 1, 1),
            valid_until=date(2026, 2, 1),
            currency=cls.currency,
            created_by=cls.user,
        )

    def test_str_representation(self):
        self.assertIn("QT-0001", str(self.quote))

    def test_default_status(self):
        self.assertEqual(self.quote.status, Quote.Status.DRAFT)

    def test_unique_quote_number(self):
        with self.assertRaises(IntegrityError):
            Quote.objects.create(
                company=self.company,
                customer=self.customer,
                quote_number="QT-0001",
                quote_date=date(2026, 1, 1),
                valid_until=date(2026, 2, 1),
                currency=self.currency,
                created_by=self.user,
            )

    def test_calculate_totals(self):
        QuoteLine.objects.create(
            quote=self.quote,
            description="Service A",
            quantity=Decimal("2"),
            unit_price=Decimal("500"),
            tax_rate=self.tax_rate,
        )
        QuoteLine.objects.create(
            quote=self.quote,
            description="Service B",
            quantity=Decimal("1"),
            unit_price=Decimal("1000"),
            tax_rate=self.zero_tax,
        )
        self.quote.discount_percent = Decimal("10")
        self.quote.calculate_totals()
        # subtotal = 1000 + 1000 = 2000
        # discount = 2000 * 10/100 = 200
        # tax on line A = 1000 * 15/100 = 150, line B = 0
        self.assertEqual(self.quote.subtotal, Decimal("2000"))
        self.assertEqual(self.quote.discount_amount, Decimal("200"))
        self.assertEqual(self.quote.tax_amount, Decimal("150"))
        self.assertEqual(self.quote.total_amount, Decimal("1950"))


class QuoteLineModelTest(ERPTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.quote = Quote.objects.create(
            company=cls.company,
            customer=cls.customer,
            quote_number="QT-QL",
            quote_date=date(2026, 1, 1),
            valid_until=date(2026, 2, 1),
            currency=cls.currency,
            created_by=cls.user,
        )

    def test_line_total_calculation(self):
        ql = QuoteLine.objects.create(
            quote=self.quote,
            description="Widget",
            quantity=Decimal("5"),
            unit_price=Decimal("100"),
        )
        self.assertEqual(ql.line_total, Decimal("500"))

    def test_line_with_discount(self):
        ql = QuoteLine.objects.create(
            quote=self.quote,
            description="Widget",
            quantity=Decimal("10"),
            unit_price=Decimal("100"),
            discount_percent=Decimal("20"),
        )
        # 10 * 100 = 1000, discount = 200
        self.assertEqual(ql.line_total, Decimal("800"))

    def test_line_with_tax(self):
        ql = QuoteLine.objects.create(
            quote=self.quote,
            description="Widget",
            quantity=Decimal("1"),
            unit_price=Decimal("1000"),
            tax_rate=self.tax_rate,
        )
        self.assertEqual(ql.line_total, Decimal("1000"))
        self.assertEqual(ql.tax_amount, Decimal("150"))
