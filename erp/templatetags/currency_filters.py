"""
Custom template filter for ERP currency display.

Usage:
    {% load currency_filters %}   (or rely on settings.py builtins)
    {{ amount|currency_display:currency_obj }}

Produces RTL-aware, comma-grouped output using the currency's
decimal_places, symbol (falling back to code), and currency code
to detect Arabic-script symbol placement.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django import template

register = template.Library()

# Arabic-script currency codes — symbol placed after the number regardless
# of the active UI language, because their symbols are Arabic-script glyphs.
_ARABIC_SYMBOL_CURRENCIES = frozenset(
    {
        "SAR",
        "AED",
        "KWD",
        "QAR",
        "BHD",
        "OMR",
        "JOD",
        "EGP",
    }
)


def _is_rtl_currency(code: str) -> bool:
    return (code or "").upper() in _ARABIC_SYMBOL_CURRENCIES


@register.filter(name="currency_display", is_safe=True)
def currency_display(amount, currency=None):
    """
    Format *amount* as a currency string.

    LTR example:  "$1,234.56"  |  "USD 1,234.56" (when symbol is blank)
    RTL example:  "1,234.56 ر.س"  |  "1,234.56 SAR" (when symbol is blank)

    Symbol placement is determined by the currency code, not the active
    language, so Arabic-script currencies always render with a suffix symbol
    even in an English-language session (e.g. PDF generated in English for a
    SAR invoice).
    """
    if amount is None or amount == "":
        amount = 0

    # Precision from the Currency model; default 2
    decimal_places = 2
    if currency is not None and hasattr(currency, "decimal_places"):
        decimal_places = int(currency.decimal_places)

    # Round with Decimal for ERP-grade precision
    try:
        quantize_str = ("0." + "0" * decimal_places) if decimal_places else "0"
        rounded = Decimal(str(amount)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        rounded = Decimal("0")

    # Build formatted number: comma thousands, period decimal (invariant locale)
    is_negative = rounded < 0
    abs_value = abs(rounded)
    int_part = int(abs_value)
    formatted_int = f"{int_part:,}"
    if decimal_places:
        # Extract fractional digits from the Decimal string to avoid float error
        dec_str = str(abs_value)
        if "." in dec_str:
            frac = dec_str.split(".")[1][:decimal_places].ljust(decimal_places, "0")
        else:
            frac = "0" * decimal_places
        formatted_number = f"{formatted_int}.{frac}"
    else:
        formatted_number = formatted_int
    if is_negative:
        formatted_number = f"-{formatted_number}"

    # Symbol with fallback to code, then to '$'
    symbol = ""
    code = ""
    if currency is not None:
        symbol = (getattr(currency, "symbol", "") or "").strip()
        code = (getattr(currency, "code", "") or "").strip()
    display_marker = symbol if symbol else (code if code else "$")

    # Arabic-script currencies: symbol after the number (with a separating space)
    if _is_rtl_currency(code):
        return f"{formatted_number} {display_marker}"
    else:
        return f"{display_marker}{formatted_number}"
