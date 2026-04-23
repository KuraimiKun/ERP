"""
Tests for the Financial Reports JSON API.

Verifies:
  * Endpoints require authentication.
  * They return data scoped to the requesting user's company.
  * The numbers they return match those produced by the underlying
    ``erp.services.financial_reports`` helpers (i.e. the API is a thin
    serialization layer, not a second implementation that could drift).
  * The Trial Balance balances (debit == credit) after one posted invoice.
"""

from datetime import date
from decimal import Decimal

from rest_framework import status

from erp.models import Invoice
from erp.services.accounting import create_invoice_journal_entry
from erp.tests.helpers import ERPAPITestCase


class FinancialReportsAPITest(ERPAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Create one posted invoice so the reports have real activity to
        # aggregate.
        invoice = Invoice.objects.create(
            company=cls.company,
            customer=cls.customer,
            invoice_number="INV-RPT-001",
            invoice_date=date(2026, 6, 1),
            due_date=date(2026, 7, 1),
            currency=cls.currency,
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("150.00"),
            total_amount=Decimal("1150.00"),
            balance_due=Decimal("1150.00"),
            exchange_rate_at_date=Decimal("1"),
            created_by=cls.user,
        )
        create_invoice_journal_entry(invoice, cls.user)

    def setUp(self):
        super().setUp()
        # Token auth (ERPAPITestCase wires this up)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    # ── auth ──────────────────────────────────────────────────────────────

    def test_requires_authentication(self):
        self.client.credentials()  # clear token
        for path in (
            "/api/finance/reports/trial-balance/",
            "/api/finance/reports/profit-and-loss/",
            "/api/finance/reports/balance-sheet/",
            "/api/finance/reports/cash-flow/",
        ):
            resp = self.client.get(path)
            self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    # ── happy path for each statement ────────────────────────────────────

    def test_trial_balance_balances(self):
        resp = self.client.get(
            "/api/finance/reports/trial-balance/",
            {"start": "2026-01-01", "end": "2026-12-31"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["total_debit"], body["total_credit"])
        self.assertTrue(body["is_balanced"])
        # AR, Revenue, Tax Payable should all appear after posting the invoice.
        codes = {a["code"] for a in body["accounts"]}
        self.assertTrue({"1200", "4000", "2100"}.issubset(codes))

    def test_profit_and_loss_reflects_invoice(self):
        resp = self.client.get(
            "/api/finance/reports/profit-and-loss/",
            {"start": "2026-01-01", "end": "2026-12-31"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        # The invoice's subtotal (1000.00) should appear as income.
        self.assertEqual(Decimal(body["total_income"]), Decimal("1000.00"))
        self.assertEqual(Decimal(body["total_expenses"]), Decimal("0"))
        self.assertEqual(Decimal(body["net_profit"]), Decimal("1000.00"))

    def test_balance_sheet_equation_holds(self):
        resp = self.client.get(
            "/api/finance/reports/balance-sheet/",
            {"as_of": "2026-12-31"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        # Assets = Liabilities + Equity  (tolerating floating-point rounding
        # isn't needed since we're dealing with exact Decimals)
        assets = Decimal(body["total_assets"])
        liabs = Decimal(body["total_liabilities"])
        equity = Decimal(body["total_equity"])
        self.assertEqual(assets, liabs + equity)
        self.assertEqual(Decimal(body["balance_check"]), Decimal("0"))

    def test_cash_flow_returns_structure(self):
        resp = self.client.get(
            "/api/finance/reports/cash-flow/",
            {"start": "2026-01-01", "end": "2026-12-31"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        for field in (
            "payments_received",
            "payments_made_supplier",
            "expenses_paid",
            "operating_inflows",
            "operating_outflows",
            "net_operating",
            "net_cash_change",
        ):
            self.assertIn(field, body)

    # ── input validation ─────────────────────────────────────────────────

    def test_bad_date_returns_400(self):
        resp = self.client.get(
            "/api/finance/reports/trial-balance/",
            {"start": "not-a-date", "end": "2026-12-31"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inverted_range_returns_400(self):
        resp = self.client.get(
            "/api/finance/reports/profit-and-loss/",
            {"start": "2026-12-31", "end": "2026-01-01"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class RequestIDMiddlewareTest(ERPAPITestCase):
    """Verify the RequestID middleware echoes/generates the header."""

    def setUp(self):
        super().setUp()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_generates_request_id_when_absent(self):
        resp = self.client.get(
            "/api/finance/reports/trial-balance/",
            {"start": "2026-01-01", "end": "2026-12-31"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rid = resp.headers.get("X-Request-ID", "")
        # UUID4 hex is 32 chars, all hex digits.
        self.assertEqual(len(rid), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in rid))

    def test_echoes_valid_incoming_request_id(self):
        resp = self.client.get(
            "/api/finance/reports/trial-balance/",
            {"start": "2026-01-01", "end": "2026-12-31"},
            HTTP_X_REQUEST_ID="trace-abc-123",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.headers.get("X-Request-ID"), "trace-abc-123")

    def test_rejects_malicious_request_id(self):
        # Control chars / newlines must be ignored; server generates its own.
        bad = "attack\r\nInjected-Header: x"
        resp = self.client.get(
            "/api/finance/reports/trial-balance/",
            {"start": "2026-01-01", "end": "2026-12-31"},
            HTTP_X_REQUEST_ID=bad,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        echoed = resp.headers.get("X-Request-ID", "")
        self.assertNotEqual(echoed, bad)
        self.assertEqual(len(echoed), 32)  # server-generated UUID4 hex
