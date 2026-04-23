"""
Tests for erp.templatetags.currency_filters
"""

from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from erp.templatetags.currency_filters import currency_display


def make_currency(code, symbol, decimal_places=2):
    c = MagicMock()
    c.code = code
    c.symbol = symbol
    c.decimal_places = decimal_places
    return c


class CurrencyDisplayFilterTest(TestCase):
    # --- LTR currencies (prefix symbol) ---

    def test_usd_ltr(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display(Decimal("1234.56"), usd), "$1,234.56")

    def test_eur_ltr(self):
        eur = make_currency("EUR", "€")
        self.assertEqual(currency_display(Decimal("1234.56"), eur), "€1,234.56")

    def test_idr_zero_decimal_places(self):
        idr = make_currency("IDR", "Rp", decimal_places=0)
        self.assertEqual(currency_display(Decimal("1234567"), idr), "Rp1,234,567")

    def test_large_amount_thousand_separator(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display(Decimal("1234567.89"), usd), "$1,234,567.89")

    # --- Arabic-script currencies (suffix symbol regardless of UI language) ---

    def test_sar_suffix_in_english_session(self):
        sar = make_currency("SAR", "ر.س")
        self.assertEqual(currency_display(Decimal("1234.56"), sar), "1,234.56 ر.س")

    @override_settings(LANGUAGE_CODE="ar")
    def test_sar_suffix_in_arabic_session(self):
        sar = make_currency("SAR", "ر.س")
        self.assertEqual(currency_display(Decimal("1234.56"), sar), "1,234.56 ر.س")

    def test_aed_suffix(self):
        aed = make_currency("AED", "د.إ")
        self.assertEqual(currency_display(Decimal("500.00"), aed), "500.00 د.إ")

    # --- Fallback: empty symbol → use code ---

    def test_fallback_to_code_ltr(self):
        usd = make_currency("USD", "")
        self.assertEqual(currency_display(Decimal("1234.56"), usd), "USD1,234.56")

    def test_fallback_to_code_arabic_currency(self):
        sar = make_currency("SAR", "")
        self.assertEqual(currency_display(Decimal("1234.56"), sar), "1,234.56 SAR")

    # --- Fallback: no currency object → '$' prefix ---

    def test_no_currency_defaults_to_dollar(self):
        self.assertEqual(currency_display(Decimal("100.00"), None), "$100.00")

    def test_no_currency_zero(self):
        self.assertEqual(currency_display(0, None), "$0.00")

    # --- Edge cases ---

    def test_none_amount(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display(None, usd), "$0.00")

    def test_empty_string_amount(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display("", usd), "$0.00")

    def test_integer_amount(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display(1000, usd), "$1,000.00")

    def test_float_amount(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display(1234.5, usd), "$1,234.50")

    def test_negative_amount(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display(Decimal("-500.00"), usd), "$-500.00")

    def test_zero_amount(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display(Decimal("0"), usd), "$0.00")

    def test_rounding_half_up(self):
        usd = make_currency("USD", "$")
        # 1234.555 should round up to 1234.56
        self.assertEqual(currency_display(Decimal("1234.555"), usd), "$1,234.56")

    def test_string_amount(self):
        usd = make_currency("USD", "$")
        self.assertEqual(currency_display("999.99", usd), "$999.99")
