"""Tests for currency display formatting utilities."""

from types import MappingProxyType

import pytest

from synthorg.budget.currency import (
    CURRENCY_SYMBOLS,
    MINOR_UNITS,
    format_cost,
    format_cost_detail,
    get_currency_symbol,
)


@pytest.mark.unit
class TestGetCurrencySymbol:
    """Tests for get_currency_symbol lookup and fallback."""

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("USD", "$"),
            ("EUR", "\u20ac"),
            ("GBP", "\u00a3"),
            ("JPY", "\u00a5"),
            ("INR", "\u20b9"),
            ("CNY", "CN\u00a5"),
        ],
        ids=["usd", "eur", "gbp", "jpy", "inr", "cny"],
    )
    def test_known_symbol(self, code: str, expected: str) -> None:
        assert get_currency_symbol(code) == expected

    def test_unknown_falls_back_to_code(self) -> None:
        assert get_currency_symbol("XYZ") == "XYZ"

    def test_unknown_real_currency_code(self) -> None:
        """Unmapped but real ISO 4217 code returns the code itself."""
        assert get_currency_symbol("AED") == "AED"


@pytest.mark.unit
class TestFormatCost:
    """Tests for format_cost with various currencies and precisions."""

    def test_eur_default(self) -> None:
        assert format_cost(42.50) == "\u20ac42.50"

    def test_usd_explicit(self) -> None:
        assert format_cost(42.50, "USD") == "$42.50"

    def test_eur_explicit(self) -> None:
        assert format_cost(10.00, "EUR") == "\u20ac10.00"

    def test_gbp(self) -> None:
        assert format_cost(99.99, "GBP") == "\u00a399.99"

    @pytest.mark.parametrize(
        ("value", "currency", "expected"),
        [
            (1234.0, "JPY", "\u00a51,234"),
            (50000.0, "KRW", "\u20a950,000"),
            (500000.0, "VND", "\u20ab500,000"),
        ],
        ids=["jpy", "krw", "vnd"],
    )
    def test_zero_decimal_currency(
        self, value: float, currency: str, expected: str
    ) -> None:
        """Zero-decimal currencies have no fractional digits."""
        assert format_cost(value, currency) == expected

    def test_three_decimal_currency(self) -> None:
        """Three-decimal currencies (BHD, KWD, etc.) format with 3 decimals."""
        assert format_cost(1.234, "BHD") == "BHD1.234"

    def test_unknown_currency_uses_code(self) -> None:
        assert format_cost(42.50, "XYZ") == "XYZ42.50"

    def test_zero_value(self) -> None:
        assert format_cost(0.0, "USD") == "$0.00"

    def test_large_value_with_grouping(self) -> None:
        assert format_cost(1234567.89, "USD") == "$1,234,567.89"

    def test_custom_precision(self) -> None:
        assert format_cost(42.5678, "USD", precision=4) == "$42.5678"

    def test_custom_precision_zero(self) -> None:
        assert format_cost(42.5678, "USD", precision=0) == "$43"

    def test_negative_value(self) -> None:
        result = format_cost(-10.50, "USD")
        assert result == "-$10.50"

    def test_nan_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            format_cost(float("nan"), "USD")

    def test_negative_precision_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="precision must be non-negative"):
            format_cost(42.0, "USD", precision=-1)


@pytest.mark.unit
class TestFormatCostDetail:
    """Tests for format_cost_detail (4-decimal precision)."""

    def test_eur_default(self) -> None:
        assert format_cost_detail(0.0315) == "\u20ac0.0315"

    def test_usd(self) -> None:
        assert format_cost_detail(0.0315, "USD") == "$0.0315"

    def test_jpy_still_4_decimals(self) -> None:
        """Detail view always uses 4 decimals, even for zero-decimal currencies."""
        assert format_cost_detail(0.0315, "JPY") == "\u00a50.0315"

    def test_zero(self) -> None:
        assert format_cost_detail(0.0, "USD") == "$0.0000"


@pytest.mark.unit
class TestCurrencyConstants:
    """Validate constant integrity."""

    def test_symbols_keys_are_3_uppercase(self) -> None:
        for code in CURRENCY_SYMBOLS:
            assert len(code) == 3, f"Code {code!r} is not 3 characters"
            assert code == code.upper(), f"Code {code!r} is not uppercase"

    def test_minor_units_is_mapping_proxy(self) -> None:
        """MINOR_UNITS is a MappingProxyType with 3-uppercase-letter keys."""
        assert isinstance(MINOR_UNITS, MappingProxyType)
        for code in MINOR_UNITS:
            assert len(code) == 3, f"Code {code!r} is not 3 characters"
            assert code == code.upper(), f"Code {code!r} is not uppercase"

    def test_usd_in_symbols(self) -> None:
        assert "USD" in CURRENCY_SYMBOLS

    def test_eur_in_symbols(self) -> None:
        assert "EUR" in CURRENCY_SYMBOLS

    def test_jpy_in_minor_units(self) -> None:
        assert "JPY" in MINOR_UNITS

    def test_usd_not_in_minor_units(self) -> None:
        assert "USD" not in MINOR_UNITS
