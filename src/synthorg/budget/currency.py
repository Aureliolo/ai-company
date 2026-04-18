"""Currency display formatting utilities and the ``CurrencyCode`` type.

Provides locale-independent currency formatting using ISO 4217 codes.
No external dependencies -- symbol lookup uses a built-in table of
common currencies with fallback to the ISO code for unknown codes.

Owns two related concerns:

* **Display formatting** -- ``format_cost`` / ``format_cost_detail`` /
  ``get_currency_symbol`` / ``CURRENCY_SYMBOLS`` / ``MINOR_UNITS``.
* **Validation** -- the ``CurrencyCode`` Annotated type used on every
  cost-bearing model (``CostRecord``, ``TaskMetricRecord``,
  ``AgentRuntimeState``, et al.) to reject typos and codes the display
  layer does not know how to format.

The ``CurrencyCode`` allowlist is derived from the union of keys in
``CURRENCY_SYMBOLS`` and ``MINOR_UNITS`` so that adopting a new
currency requires adding it to the display mappings first; a row with
a code the formatter cannot render would be a latent bug waiting to
surface in a report.
"""

import math
from types import MappingProxyType
from typing import Annotated, Final

from pydantic import AfterValidator, StringConstraints

DEFAULT_CURRENCY: Final[str] = "USD"
"""Default ISO 4217 currency code.

USD is the honest default: major LLM providers publish token pricing
in USD, and LiteLLM returns ``response_cost`` in USD.  SynthOrg does
not convert FX at record time or display time -- the
``budget.currency`` setting is a display-only preference.  Overridden
at runtime by the ``budget.currency`` setting; this constant is the
fallback when the setting has not been resolved yet.
"""

CURRENCY_SYMBOLS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "AUD": "A$",
        "BRL": "R$",
        "CAD": "CA$",
        "CHF": "CHF",
        "CNY": "CN\u00a5",
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

MINOR_UNITS: Final[MappingProxyType[str, int]] = MappingProxyType(
    {
        # Zero-decimal currencies (ISO 4217 exponent 0)
        "BIF": 0,
        "CLP": 0,
        "DJF": 0,
        "GNF": 0,
        "HUF": 0,  # ISO exponent=2 but integer for display (HNB)
        "ISK": 0,
        "JPY": 0,
        "KMF": 0,
        "KRW": 0,
        "MGA": 0,
        "PYG": 0,
        "RWF": 0,
        "UGX": 0,
        "VND": 0,
        "VUV": 0,
        "XAF": 0,
        "XOF": 0,
        "XPF": 0,
        # Three-decimal currencies (ISO 4217 exponent 3)
        "BHD": 3,
        "IQD": 3,
        "JOD": 3,
        "KWD": 3,
        "LYD": 3,
        "OMR": 3,
        "TND": 3,
    }
)
"""ISO 4217 minor-unit metadata.

Maps currency codes to their number of minor (fractional) units.
Currencies not listed default to 2 decimal places (the ISO 4217 norm).
"""


def get_currency_symbol(code: str) -> str:
    """Return the display symbol for an ISO 4217 currency code.

    Falls back to the code itself (e.g. ``"AED"``) when no dedicated
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
    currency based on ``MINOR_UNITS``.

    Args:
        value: The numeric cost value (must be finite).
        currency: ISO 4217 currency code.
        precision: Override decimal places.  When ``None``, uses the
            currency's minor-unit count from ``MINOR_UNITS`` (default 2).

    Returns:
        Formatted string, e.g. ``"$42.50"``, ``"\u20ac10.00"``,
        ``"\u00a51,234"``.

    Raises:
        ValueError: If *value* is not finite or *precision* is negative.
    """
    if not math.isfinite(value):
        msg = f"Cannot format non-finite cost value: {value!r}"
        raise ValueError(msg)
    if precision is not None and precision < 0:
        msg = f"precision must be non-negative, got {precision}"
        raise ValueError(msg)
    if precision is None:
        precision = MINOR_UNITS.get(currency, 2)
    symbol = get_currency_symbol(currency)
    sign = "-" if value < 0 else ""
    return f"{sign}{symbol}{abs(value):,.{precision}f}"


def format_cost_detail(value: float, currency: str = DEFAULT_CURRENCY) -> str:
    """Format a cost value with 4-decimal precision for detail views.

    Used in activity feeds and line-item displays where sub-unit
    precision matters (e.g. individual API call costs).

    Args:
        value: The numeric cost value.
        currency: ISO 4217 currency code.

    Returns:
        Formatted string with 4 decimal places, e.g. ``"$0.0315"``.
    """
    return format_cost(value, currency, precision=4)


_KNOWN_ISO4217: Final[frozenset[str]] = frozenset(CURRENCY_SYMBOLS) | frozenset(
    MINOR_UNITS
)
"""Allowlist of ISO 4217 codes the display/formatting layer supports.

Drawn from ``CURRENCY_SYMBOLS`` and ``MINOR_UNITS``.  A new currency
must be added to at least one of those mappings before any row may
carry the code; this keeps persistence and formatting in sync.
"""


def _check_iso4217(value: str) -> str:
    """Reject currency codes not present in the known ISO 4217 allowlist."""
    if value not in _KNOWN_ISO4217:
        msg = f"unknown ISO 4217 currency code: {value!r}"
        raise ValueError(msg)
    return value


CurrencyCode = Annotated[
    str,
    StringConstraints(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"),
    AfterValidator(_check_iso4217),
]
"""An ISO 4217 currency code (3 uppercase ASCII letters).

Validation is two-phase: the string pattern rejects blank, lowercase,
and wrong-length inputs at parse time; the ``AfterValidator`` then
requires the code to be present in ``_KNOWN_ISO4217`` so typos
(``EURR``) and well-formed but unsupported codes (``ZZZ``) are rejected
together.
"""
