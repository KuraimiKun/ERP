"""
Tests for Finance models: Account, Customer, Invoice, Payment, Expense,
JournalEntry, and related business logic.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError

from erp.models import (
    Account,
    Customer,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentAllocation,
    Expense,
    JournalEntry,
    JournalEntryLine,
)
from erp.tests.helpers import ERPTestCase


# ────────────────────────────────────────────────────────────────
# Account (Chart of Accounts)
# ────────────────────────────────────────────────────────────────


class AccountModelTest(ERPTestCase):
    def test_str_representation(self):
        self.assertEqual(str(self.cash_account), "1000 - Cash")

    def test_is_debit_normal_for_assets(self):
        self.assertTrue(self.cash_account.is_debit_normal)

    def test_is_debit_normal_for_expenses(self):
        self.assertTrue(self.expense_account.is_debit_normal)

    def test_is_credit_normal_for_liabilities(self):
        self.assertFalse(self.ap_account.is_debit_normal)

    def test_is_credit_normal_for_income(self):
        self.assertFalse(self.revenue_account.is_debit_normal)

    def test_update_balance_debit_normal(self):
        self.cash_account.update_balance(Decimal("500"), Decimal("200"))
        self.assertEqual(self.cash_account.current_balance, Decimal("300"))

    def test_update_balance_credit_normal(self):
        self.revenue_account.update_balance(Decimal("0"), Decimal("1000"))
        self.assertEqual(self.revenue_account.current_balance, Decimal("1000"))

    def test_unique_together_company_code(self):
        with self.assertRaises(IntegrityError):
            Account.objects.create(
                company=self.company,
                code="1000",
                name="Dup Cash",
                account_type="asset",
            )

    def test_hierarchical_accounts(self):
        parent = self.cash_account
        child = Account.objects.create(
            company=self.company,
            code="1001",
            name="Petty Cash",
            account_type="asset",
            parent=parent,
            created_by=self.user,
        )
        self.assertIn(child, parent.children.all())


# ────────────────────────────────────────────────────────────────
# Customer
# ────────────────────────────────────────────────────────────────


class CustomerModelTest(ERPTestCase):
    def test_str_representation(self):
        self.assertEqual(str(self.customer), "Acme LLC (CUS-0001)")

    def test_unique_customer_id(self):
        with self.assertRaises(IntegrityError):
            Customer.objects.create(
                company=self.company,
                customer_id="CUS-0001",
                name="Dup",
                currency=self.currency,
                created_by=self.user,
            )

    def test_default_balance_zero(self):
        self.assertEqual(self.customer.current_balance, 0)

    def test_soft_delete_customer(self):
        self.customer.soft_delete(user=self.user)
        self.assertFalse(Customer.objects.filter(pk=self.customer.pk).exists())
        self.customer.restore()
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())


# ────────────────────────────────────────────────────────────────
# Invoice & InvoiceLine
# ────────────────────────────────────────────────────────────────


class InvoiceModelTest(ERPTestCase):
    def _create_invoice(self, **kwargs):
        defaults = dict(
            company=self.company,
            customer=self.customer,
            invoice_number="INV-TEST-001",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=self.currency,
            created_by=self.user,
        )
        defaults.update(kwargs)
        return Invoice.objects.create(**defaults)

    def test_str_representation(self):
        inv = self._create_invoice()
        self.assertIn("INV-TEST-001", str(inv))

    def test_default_status_is_draft(self):
        inv = self._create_invoice()
        self.assertEqual(inv.status, Invoice.Status.DRAFT)

    def test_balance_due_calculation(self):
        inv = self._create_invoice(total_amount=Decimal("1000"), paid_amount=Decimal("400"))
        self.assertEqual(inv.balance_due, Decimal("600"))

    def test_calculate_totals_from_lines(self):
        inv = self._create_invoice()
        InvoiceLine.objects.create(
            invoice=inv,
            description="Item 1",
            quantity=2,
            unit_price=Decimal("100"),
        )
        InvoiceLine.objects.create(
            invoice=inv,
            description="Item 2",
            quantity=1,
            unit_price=Decimal("50"),
            tax_rate=self.tax_rate,
        )
        inv.calculate_totals()
        self.assertEqual(inv.subtotal, Decimal("250"))
        self.assertGreater(inv.tax_amount, 0)

    def test_invoice_line_calculates_line_total(self):
        inv = self._create_invoice()
        line = InvoiceLine.objects.create(
            invoice=inv,
            description="Widget",
            quantity=3,
            unit_price=Decimal("100"),
        )
        self.assertEqual(line.line_total, Decimal("300"))

    def test_invoice_line_discount(self):
        inv = self._create_invoice()
        line = InvoiceLine.objects.create(
            invoice=inv,
            description="Widget",
            quantity=2,
            unit_price=Decimal("100"),
            discount_percent=Decimal("10"),
        )
        # 200 - 10% = 180
        self.assertEqual(line.line_total, Decimal("180"))

    def test_invoice_line_tax_calculation(self):
        inv = self._create_invoice()
        line = InvoiceLine.objects.create(
            invoice=inv,
            description="Taxed Item",
            quantity=1,
            unit_price=Decimal("1000"),
            tax_rate=self.tax_rate,
        )
        # 15% of 1000 = 150
        self.assertEqual(line.tax_amount, Decimal("150"))

    def test_unique_invoice_number(self):
        self._create_invoice(invoice_number="INV-UNIQUE")
        with self.assertRaises(IntegrityError):
            self._create_invoice(invoice_number="INV-UNIQUE")

    def test_invoice_type_choices(self):
        inv = self._create_invoice(invoice_type="credit")
        self.assertEqual(inv.invoice_type, Invoice.InvoiceType.CREDIT)

    def test_paid_status_when_fully_paid(self):
        inv = self._create_invoice(
            total_amount=Decimal("1000"),
            paid_amount=Decimal("1000"),
        )
        # save() sets balance_due = total_amount - paid_amount
        inv.refresh_from_db()
        self.assertEqual(inv.balance_due, Decimal("0"))


# ────────────────────────────────────────────────────────────────
# Payment & PaymentAllocation
# ────────────────────────────────────────────────────────────────


class PaymentModelTest(ERPTestCase):
    def _create_payment(self, **kwargs):
        defaults = dict(
            company=self.company,
            customer=self.customer,
            payment_number="PAY-TEST-001",
            payment_date=date.today(),
            payment_method=self.payment_method,
            currency=self.currency,
            amount=Decimal("500"),
            created_by=self.user,
        )
        defaults.update(kwargs)
        return Payment.objects.create(**defaults)

    def test_str_representation(self):
        pay = self._create_payment()
        self.assertIn("PAY-TEST-001", str(pay))

    def test_unallocated_amount(self):
        pay = self._create_payment(amount=Decimal("1000"), allocated_amount=Decimal("300"))
        self.assertEqual(pay.unallocated_amount, Decimal("700"))

    def test_payment_allocation_unique_together(self):
        inv = Invoice.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_number="INV-ALLOC-1",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=self.currency,
            total_amount=Decimal("500"),
            created_by=self.user,
        )
        pay = self._create_payment()

        PaymentAllocation.objects.create(
            payment=pay,
            invoice=inv,
            amount=Decimal("200"),
        )
        with self.assertRaises(IntegrityError):
            PaymentAllocation.objects.create(
                payment=pay,
                invoice=inv,
                amount=Decimal("100"),
            )


# ────────────────────────────────────────────────────────────────
# Expense
# ────────────────────────────────────────────────────────────────


class ExpenseModelTest(ERPTestCase):
    def test_expense_total_calculation(self):
        exp = Expense.objects.create(
            company=self.company,
            expense_number="EXP-001",
            expense_date=date.today(),
            category=self.expense_category,
            description="Office stuff",
            currency=self.currency,
            amount=Decimal("200"),
            tax_amount=Decimal("30"),
            created_by=self.user,
        )
        self.assertEqual(exp.total_amount, Decimal("230"))

    def test_expense_default_status_is_draft(self):
        exp = Expense.objects.create(
            company=self.company,
            expense_number="EXP-002",
            expense_date=date.today(),
            category=self.expense_category,
            description="Test",
            currency=self.currency,
            amount=Decimal("100"),
            created_by=self.user,
        )
        self.assertEqual(exp.status, Expense.Status.DRAFT)


# ────────────────────────────────────────────────────────────────
# JournalEntry & Double-Entry Bookkeeping
# ────────────────────────────────────────────────────────────────


class JournalEntryModelTest(ERPTestCase):
    def _create_balanced_entry(self):
        je = JournalEntry.objects.create(
            company=self.company,
            entry_number="JE-001",
            entry_date=date.today(),
            entry_type="manual",
            status="draft",
            fiscal_year=self.fiscal_year,
            created_by=self.user,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=self.cash_account,
            debit_amount=Decimal("1000"),
            credit_amount=Decimal("0"),
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=self.revenue_account,
            debit_amount=Decimal("0"),
            credit_amount=Decimal("1000"),
        )
        je.refresh_from_db()
        return je

    def test_str_representation(self):
        je = self._create_balanced_entry()
        self.assertIn("JE-001", str(je))

    def test_is_balanced(self):
        je = self._create_balanced_entry()
        self.assertTrue(je.is_balanced)

    def test_is_not_balanced(self):
        je = JournalEntry.objects.create(
            company=self.company,
            entry_number="JE-UNBAL",
            entry_date=date.today(),
            entry_type="manual",
            created_by=self.user,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=self.cash_account,
            debit_amount=Decimal("500"),
            credit_amount=Decimal("0"),
        )
        je.refresh_from_db()
        self.assertFalse(je.is_balanced)

    def test_post_balanced_entry(self):
        je = self._create_balanced_entry()
        je.post(self.user)
        self.assertEqual(je.status, JournalEntry.Status.POSTED)
        self.assertIsNotNone(je.posted_at)

    def test_post_updates_account_balances(self):
        je = self._create_balanced_entry()
        initial_cash = self.cash_account.current_balance
        initial_rev = self.revenue_account.current_balance
        je.post(self.user)
        self.cash_account.refresh_from_db()
        self.revenue_account.refresh_from_db()
        # Cash is debit-normal, so debit increases balance
        self.assertEqual(
            self.cash_account.current_balance,
            initial_cash + Decimal("1000"),
        )
        # Revenue is credit-normal, so credit increases balance
        self.assertEqual(
            self.revenue_account.current_balance,
            initial_rev + Decimal("1000"),
        )

    def test_post_unbalanced_raises(self):
        je = JournalEntry.objects.create(
            company=self.company,
            entry_number="JE-FAIL",
            entry_date=date.today(),
            entry_type="manual",
            created_by=self.user,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=self.cash_account,
            debit_amount=Decimal("500"),
            credit_amount=Decimal("0"),
        )
        je.refresh_from_db()
        with self.assertRaises(ValueError):
            je.post(self.user)

    def test_post_non_draft_raises(self):
        je = self._create_balanced_entry()
        je.post(self.user)
        with self.assertRaises(ValueError):
            je.post(self.user)

    def test_calculate_totals(self):
        je = self._create_balanced_entry()
        self.assertEqual(je.total_debit, Decimal("1000"))
        self.assertEqual(je.total_credit, Decimal("1000"))

    def test_journal_line_auto_updates_entry_totals(self):
        """Saving a new line should recalculate parent entry totals."""
        je = JournalEntry.objects.create(
            company=self.company,
            entry_number="JE-AUTO",
            entry_date=date.today(),
            entry_type="manual",
            created_by=self.user,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=self.cash_account,
            debit_amount=Decimal("750"),
            credit_amount=Decimal("0"),
        )
        je.refresh_from_db()
        self.assertEqual(je.total_debit, Decimal("750"))

    def test_entry_type_choices(self):
        for choice_val, _ in JournalEntry.EntryType.choices:
            self.assertIn(
                choice_val,
                [
                    "manual",
                    "invoice",
                    "payment",
                    "expense",
                    "payroll",
                    "adjustment",
                    "opening",
                    "closing",
                    "inventory",
                ],
            )


# ────────────────────────────────────────────────────────────────
# Account Balance Recalculation
# ────────────────────────────────────────────────────────────────


class AccountBalanceRecalculationTest(ERPTestCase):
    def test_recalculate_balance_from_posted_entries(self):
        self.cash_account.opening_balance = Decimal("5000")
        self.cash_account.save()

        je = JournalEntry.objects.create(
            company=self.company,
            entry_number="JE-RECALC",
            entry_date=date.today(),
            entry_type="manual",
            created_by=self.user,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=self.cash_account,
            debit_amount=Decimal("2000"),
            credit_amount=Decimal("0"),
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=self.revenue_account,
            debit_amount=Decimal("0"),
            credit_amount=Decimal("2000"),
        )
        je.refresh_from_db()
        je.post(self.user)

        recalc = self.cash_account.recalculate_balance()
        self.assertEqual(recalc, Decimal("7000"))
