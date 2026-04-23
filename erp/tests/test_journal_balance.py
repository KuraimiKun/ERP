"""
Double-Entry Balance Assertion Tests.

Invariant under test:
    For every journal entry produced by the accounting service, the sum of
    debits must equal the sum of credits.  The ``JournalEntry.is_balanced``
    property already encodes this rule, but these tests guard against
    regressions in the *service layer* that actually constructs the entries
    (``erp.services.accounting`` and ``erp.services.inventory_accounting``),
    which is where business-rule bugs most often slip in.

Each test exercises one workflow from the plan's Priority 1, creates the
business object, invokes the service, and asserts:
    1. A ``JournalEntry`` was created.
    2. It is marked POSTED.
    3. Its total debits equal its total credits (exactly, using Decimal).
    4. The direct sum of its lines also balances (defence-in-depth against
       the ``calculate_totals()`` helper drifting from the line data).
"""

from datetime import date
from decimal import Decimal

from erp.models import (
    Invoice,
    Payment,
    Expense,
    JournalEntry,
    SupplierInvoice,
    SupplierPayment,
)
from erp.services.accounting import (
    create_invoice_journal_entry,
    create_payment_journal_entry,
    create_expense_journal_entry,
    create_supplier_invoice_journal_entry,
    create_supplier_payment_journal_entry,
)
from erp.tests.helpers import ERPTestCase


def _assert_journal_balanced(testcase, je):
    """Shared assertion — every journal entry must debit == credit."""
    testcase.assertIsNotNone(je, "Service returned no JournalEntry")
    testcase.assertEqual(je.status, JournalEntry.Status.POSTED)
    # Header totals
    testcase.assertEqual(
        je.total_debit,
        je.total_credit,
        f"Header totals unbalanced: debit={je.total_debit} credit={je.total_credit}",
    )
    # Line-level totals (defence-in-depth)
    line_debits = sum((line.debit_amount for line in je.lines.all()), Decimal("0"))
    line_credits = sum((line.credit_amount for line in je.lines.all()), Decimal("0"))
    testcase.assertEqual(
        line_debits,
        line_credits,
        f"Line totals unbalanced: debit={line_debits} credit={line_credits}",
    )
    testcase.assertTrue(je.is_balanced)


class InvoiceJournalBalanceTest(ERPTestCase):
    """Sales invoice: DR AR / CR Revenue (+ CR Tax)."""

    def _build_invoice(self, subtotal, tax):
        total = subtotal + tax
        return Invoice.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_number=f"INV-BAL-{subtotal}-{tax}",
            invoice_date=date(2026, 1, 15),
            due_date=date(2026, 2, 15),
            currency=self.currency,
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            balance_due=total,
            exchange_rate_at_date=Decimal("1"),
            created_by=self.user,
        )

    def test_invoice_with_tax_balances(self):
        invoice = self._build_invoice(Decimal("1000.00"), Decimal("150.00"))
        je = create_invoice_journal_entry(invoice, self.user)
        _assert_journal_balanced(self, je)
        # Exactly three legs expected: AR debit, Revenue credit, Tax credit.
        self.assertEqual(je.lines.count(), 3)

    def test_invoice_without_tax_balances(self):
        invoice = self._build_invoice(Decimal("500.00"), Decimal("0"))
        je = create_invoice_journal_entry(invoice, self.user)
        _assert_journal_balanced(self, je)
        # No tax line — just AR and Revenue.
        self.assertEqual(je.lines.count(), 2)

    def test_zero_amount_invoice_creates_no_entry(self):
        invoice = Invoice.objects.create(
            company=self.company,
            customer=self.customer,
            invoice_number="INV-BAL-ZERO",
            invoice_date=date(2026, 1, 15),
            due_date=date(2026, 2, 15),
            currency=self.currency,
            subtotal=Decimal("0"),
            tax_amount=Decimal("0"),
            total_amount=Decimal("0"),
            balance_due=Decimal("0"),
            exchange_rate_at_date=Decimal("1"),
            created_by=self.user,
        )
        self.assertIsNone(create_invoice_journal_entry(invoice, self.user))


class PaymentJournalBalanceTest(ERPTestCase):
    """Customer payment: DR Cash / CR AR."""

    def test_payment_balances(self):
        payment = Payment.objects.create(
            company=self.company,
            customer=self.customer,
            payment_number="PMT-BAL-001",
            payment_date=date(2026, 2, 1),
            payment_method=self.payment_method,
            currency=self.currency,
            amount=Decimal("750.00"),
            exchange_rate_at_date=Decimal("1"),
            created_by=self.user,
        )
        je = create_payment_journal_entry(payment, self.user)
        _assert_journal_balanced(self, je)
        self.assertEqual(je.lines.count(), 2)


class ExpenseJournalBalanceTest(ERPTestCase):
    """Expense: DR Expense (+ DR Input Tax) / CR Cash-or-AP."""

    def _build_expense(self, amount, tax):
        return Expense.objects.create(
            company=self.company,
            expense_number=f"EXP-BAL-{amount}-{tax}",
            expense_date=date(2026, 3, 1),
            category=self.expense_category,
            description="Office chair",
            currency=self.currency,
            amount=amount,
            tax_amount=tax,
            total_amount=amount + tax,
            exchange_rate_at_date=Decimal("1"),
            payment_method=self.payment_method,
            status=Expense.Status.APPROVED,
            created_by=self.user,
        )

    def test_expense_with_tax_balances(self):
        exp = self._build_expense(Decimal("400.00"), Decimal("60.00"))
        je = create_expense_journal_entry(exp, self.user)
        _assert_journal_balanced(self, je)
        # Three legs: Expense, Input Tax, Cash/AP
        self.assertEqual(je.lines.count(), 3)

    def test_expense_without_tax_balances(self):
        exp = self._build_expense(Decimal("120.00"), Decimal("0"))
        je = create_expense_journal_entry(exp, self.user)
        _assert_journal_balanced(self, je)
        self.assertEqual(je.lines.count(), 2)


class SupplierInvoiceJournalBalanceTest(ERPTestCase):
    """Supplier invoice (bill): DR Purchases (+ DR Input Tax) / CR AP."""

    def _build_bill(self, subtotal, tax):
        total = subtotal + tax
        return SupplierInvoice.objects.create(
            company=self.company,
            supplier=self.supplier,
            invoice_number=f"BILL-{subtotal}-{tax}",
            invoice_date=date(2026, 4, 1),
            due_date=date(2026, 5, 1),
            currency=self.currency,
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            balance_due=total,
            exchange_rate_at_date=Decimal("1"),
            created_by=self.user,
        )

    def test_supplier_invoice_with_tax_balances(self):
        bill = self._build_bill(Decimal("2000.00"), Decimal("300.00"))
        je = create_supplier_invoice_journal_entry(bill, self.user)
        _assert_journal_balanced(self, je)
        self.assertEqual(je.lines.count(), 3)

    def test_supplier_invoice_without_tax_balances(self):
        bill = self._build_bill(Decimal("900.00"), Decimal("0"))
        je = create_supplier_invoice_journal_entry(bill, self.user)
        _assert_journal_balanced(self, je)
        self.assertEqual(je.lines.count(), 2)


class SupplierPaymentJournalBalanceTest(ERPTestCase):
    """Supplier payment: DR AP / CR Cash."""

    def test_supplier_payment_balances(self):
        sp = SupplierPayment.objects.create(
            company=self.company,
            supplier=self.supplier,
            payment_number="SPMT-BAL-001",
            payment_date=date(2026, 4, 15),
            payment_method=self.payment_method,
            currency=self.currency,
            amount=Decimal("1800.00"),
            exchange_rate_at_date=Decimal("1"),
            created_by=self.user,
        )
        je = create_supplier_payment_journal_entry(sp, self.user)
        _assert_journal_balanced(self, je)
        self.assertEqual(je.lines.count(), 2)
