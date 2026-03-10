"""
Tests for Core models: Currency, Company, Department, Branch, FiscalYear, Sequence.
"""

from datetime import date

from django.db import IntegrityError

from erp.models import Currency, Company, Department, Branch, FiscalYear, Sequence
from erp.tests.helpers import ERPTestCase


# ────────────────────────────────────────────────────────────────
# Currency
# ────────────────────────────────────────────────────────────────

class CurrencyModelTest(ERPTestCase):

    def test_str_representation(self):
        self.assertEqual(str(self.currency), 'SAR - Saudi Riyal')

    def test_only_one_base_currency(self):
        """Setting a second currency as base should unset the first."""
        self.usd.is_base = True
        self.usd.save()
        self.currency.refresh_from_db()
        self.assertFalse(self.currency.is_base)
        self.assertTrue(Currency.objects.get(code='USD').is_base)

    def test_unique_code(self):
        with self.assertRaises(IntegrityError):
            Currency.objects.create(code='SAR', name='Dup', symbol='X')

    def test_default_ordering(self):
        """Base currency should appear first due to ordering."""
        qs = Currency.objects.all()
        self.assertEqual(qs.first().code, 'SAR')

    def test_decimal_places_default(self):
        self.assertEqual(self.currency.decimal_places, 2)


# ────────────────────────────────────────────────────────────────
# Company
# ────────────────────────────────────────────────────────────────

class CompanyModelTest(ERPTestCase):

    def test_str_representation(self):
        self.assertEqual(str(self.company), 'Test Corp')

    def test_company_has_currency(self):
        self.assertEqual(self.company.base_currency, self.currency)

    def test_soft_delete_hides_from_queryset(self):
        self.company.soft_delete(user=self.user)
        self.assertFalse(Company.objects.filter(pk=self.company.pk).exists())
        self.assertTrue(Company.all_objects.filter(pk=self.company.pk).exists())

    def test_restore_after_soft_delete(self):
        self.company.soft_delete(user=self.user)
        self.company.restore()
        self.assertTrue(Company.objects.filter(pk=self.company.pk).exists())

    def test_ai_fields_defaults(self):
        self.assertTrue(self.company.ai_enabled)
        self.assertEqual(self.company.openai_model, 'gpt-4o-mini')


# ────────────────────────────────────────────────────────────────
# Department
# ────────────────────────────────────────────────────────────────

class DepartmentModelTest(ERPTestCase):

    def test_str_representation(self):
        self.assertEqual(str(self.department), 'Engineering')

    def test_department_belongs_to_company(self):
        self.assertEqual(self.department.company, self.company)

    def test_hierarchical_departments(self):
        child = Department.objects.create(
            company=self.company, name='Backend', code='BE',
            parent=self.department, created_by=self.user,
        )
        self.assertEqual(child.parent, self.department)
        self.assertIn(child, self.department.children.all())


# ────────────────────────────────────────────────────────────────
# Branch
# ────────────────────────────────────────────────────────────────

class BranchModelTest(ERPTestCase):

    def test_str_representation(self):
        self.assertEqual(str(self.branch), 'HQ (Test Corp)')

    def test_is_headquarters(self):
        self.assertTrue(self.branch.is_headquarters)

    def test_ordering(self):
        """HQ should come before non-HQ branches."""
        Branch.objects.create(
            company=self.company, name='Branch B',
            address='addr', city='Jeddah', country='SA',
            created_by=self.user,
        )
        qs = list(Branch.objects.filter(company=self.company))
        self.assertEqual(qs[0], self.branch)  # HQ first


# ────────────────────────────────────────────────────────────────
# FiscalYear
# ────────────────────────────────────────────────────────────────

class FiscalYearModelTest(ERPTestCase):

    def test_str_representation(self):
        self.assertEqual(str(self.fiscal_year), 'FY2026')

    def test_only_one_current_per_company(self):
        fy2 = FiscalYear.objects.create(
            company=self.company, name='FY2027',
            start_date=date(2027, 1, 1), end_date=date(2027, 12, 31),
            is_current=True, created_by=self.user,
        )
        self.fiscal_year.refresh_from_db()
        self.assertFalse(self.fiscal_year.is_current)
        self.assertTrue(fy2.is_current)

    def test_default_not_closed(self):
        self.assertFalse(self.fiscal_year.is_closed)


# ────────────────────────────────────────────────────────────────
# Sequence
# ────────────────────────────────────────────────────────────────

class SequenceModelTest(ERPTestCase):

    def test_get_next_generates_formatted_number(self):
        seq = Sequence.objects.create(
            company=self.company,
            sequence_type=Sequence.SequenceType.INVOICE,
            prefix='INV-',
            padding=5,
        )
        result = seq.get_next()
        self.assertEqual(result, 'INV-00001')

    def test_get_next_increments(self):
        seq = Sequence.objects.create(
            company=self.company,
            sequence_type=Sequence.SequenceType.PAYMENT,
            prefix='PAY-',
            padding=4,
        )
        n1 = seq.get_next()
        n2 = seq.get_next()
        self.assertEqual(n1, 'PAY-0001')
        self.assertEqual(n2, 'PAY-0002')

    def test_suffix_applied(self):
        seq = Sequence.objects.create(
            company=self.company,
            sequence_type=Sequence.SequenceType.CUSTOMER,
            prefix='C-', suffix='-SA',
            padding=3,
        )
        self.assertEqual(seq.get_next(), 'C-001-SA')

    def test_unique_together_company_type(self):
        Sequence.objects.create(
            company=self.company,
            sequence_type=Sequence.SequenceType.EXPENSE,
        )
        with self.assertRaises(IntegrityError):
            Sequence.objects.create(
                company=self.company,
                sequence_type=Sequence.SequenceType.EXPENSE,
            )
