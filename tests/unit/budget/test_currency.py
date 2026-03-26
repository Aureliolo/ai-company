"""Tests for currency display formatting utilities."""

import pytest

from synthorg.budget.currency import (
    CURRENCY_SYMBOLS,
    ZERO_DECIMAL_CURRENCIES,
    format_cost,
    format_cost_detail,
    get_currency_symbol,
)


@pytest.mark.unit
class TestGetCurrencySymbol:
    """Tests for get_currency_symbol lookup and fallback."""

    def test_known_usd(self) -> None:
        assert get_currency_symbol("USD") == "$"

    def test_known_eur(self) -> None:
        assert get_currency_symbol("EUR") == "\u20ac"

    def test_known_gbp(self) -> None:
        assert get_currency_symbol("GBP") == "\u00a3"

    def test_known_jpy(self) -> None:
        assert get_currency_symbol("JPY") == "\u00a5"

    def test_known_inr(self) -> None:
        assert get_currency_symbol("INR") == "\u20b9"

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

    def test_jpy_zero_decimal(self) -> None:
        """JPY is a zero-decimal currency -- no fractional digits."""
        assert format_cost(1234.0, "JPY") == "\u00a51,234"

    def test_krw_zero_decimal(self) -> None:
        assert format_cost(50000.0, "KRW") == "\u20a950,000"

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
        assert result == "$-10.50"

    def test_vnd_zero_decimal(self) -> None:
        assert format_cost(500000.0, "VND") == "\u20ab500,000"


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

    def test_zero_decimal_keys_are_3_uppercase(self) -> None:
        for code in ZERO_DECIMAL_CURRENCIES:
            assert len(code) == 3, f"Code {code!r} is not 3 characters"
            assert code == code.upper(), f"Code {code!r} is not uppercase"

    def test_usd_in_symbols(self) -> None:
        assert "USD" in CURRENCY_SYMBOLS

    def test_eur_in_symbols(self) -> None:
        assert "EUR" in CURRENCY_SYMBOLS

    def test_jpy_in_zero_decimal(self) -> None:
        assert "JPY" in ZERO_DECIMAL_CURRENCIES

    def test_usd_not_in_zero_decimal(self) -> None:
        assert "USD" not in ZERO_DECIMAL_CURRENCIES
