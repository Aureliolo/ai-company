"""Currency display formatting utilities.

Provides locale-independent currency formatting using ISO 4217 codes.
No external dependencies -- symbol lookup uses a built-in table of
common currencies with fallback to the ISO code for unknown codes.

This module handles **display formatting only**.  Internal cost storage
remains in a single base currency; see the ``budget.currency`` setting
for the configured display currency.
"""

from types import MappingProxyType
from typing import Final

DEFAULT_CURRENCY: Final[str] = "EUR"
"""Default ISO 4217 currency code used across the system."""

CURRENCY_SYMBOLS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "AUD": "A$",
        "BRL": "R$",
        "CAD": "CA$",
        "CHF": "CHF",
        "CNY": "\u00a5",
        "CZK": "K\u010d",
        "DKK": "kr",
        "EUR": "\u20ac",
        "GBP": "\u00a3",
        "HKD": "HK$",
        "HUF": "Ft",
        "IDR": "Rp",
        "ILS": "\u20aa",
        "INR": "\u20b9",
        "JPY": "\u00a5",
        "KRW": "\u20a9",
        "MXN": "MX$",
        "NOK": "kr",
        "NZD": "NZ$",
        "PLN": "z\u0142",
        "SEK": "kr",
        "SGD": "S$",
        "THB": "\u0e3f",
        "TRY": "\u20ba",
        "TWD": "NT$",
        "USD": "$",
        "VND": "\u20ab",
        "ZAR": "R",
    }
)
"""Mapping of common ISO 4217 currency codes to display symbols."""

ZERO_DECIMAL_CURRENCIES: Final[frozenset[str]] = frozenset(
    {
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "HUF",
        "ISK",
        "JPY",
        "KMF",
        "KRW",
        "MGA",
        "PYG",
        "RWF",
        "UGX",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    }
)
"""ISO 4217 currencies that have no minor (fractional) units."""


def get_currency_symbol(code: str) -> str:
    """Return the display symbol for an ISO 4217 currency code.

    Falls back to the code itself (e.g. ``"CHF"``) when no dedicated
    symbol is mapped.

    Args:
        code: ISO 4217 currency code (e.g. ``"USD"``, ``"EUR"``).

    Returns:
        The currency symbol string.
    """
    return CURRENCY_SYMBOLS.get(code, code)


def format_cost(
    value: float,
    currency: str = DEFAULT_CURRENCY,
    *,
    precision: int | None = None,
) -> str:
    """Format a cost value with the appropriate currency symbol.

    Uses the symbol from ``CURRENCY_SYMBOLS`` (or the ISO code as
    fallback) and the appropriate number of decimal places for the
    currency.

    Args:
        value: The numeric cost value.
        currency: ISO 4217 currency code.
        precision: Override decimal places.  When ``None``, uses 0
            for zero-decimal currencies and 2 otherwise.

    Returns:
        Formatted string, e.g. ``"$42.50"``, ``"\u20ac10.00"``,
        ``"\u00a51234"``.
    """
    if precision is None:
        precision = 0 if currency in ZERO_DECIMAL_CURRENCIES else 2
    symbol = get_currency_symbol(currency)
    sign = "-" if value < 0 else ""
    return f"{sign}{symbol}{abs(value):,.{precision}f}"


def format_cost_detail(value: float, currency: str = DEFAULT_CURRENCY) -> str:
    """Format a cost value with 4-decimal precision for detail views.

    Used in activity feeds and line-item displays where sub-cent
    precision matters (e.g. individual API call costs).

    Args:
        value: The numeric cost value.
        currency: ISO 4217 currency code.

    Returns:
        Formatted string with 4 decimal places, e.g. ``"$0.0315"``.
    """
    return format_cost(value, currency, precision=4)
