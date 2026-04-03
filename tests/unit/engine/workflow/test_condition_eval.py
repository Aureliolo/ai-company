"""Tests for safe workflow condition expression evaluator."""

import pytest

from synthorg.engine.workflow.condition_eval import evaluate_condition


class TestEvaluateCondition:
    """Safe condition expression evaluator."""

    # ── Boolean literals ──────────────────────────────────────────

    @pytest.mark.unit
    def test_true_literal(self) -> None:
        assert evaluate_condition("true", {}) is True

    @pytest.mark.unit
    def test_false_literal(self) -> None:
        assert evaluate_condition("false", {}) is False

    @pytest.mark.unit
    def test_true_case_insensitive(self) -> None:
        assert evaluate_condition("True", {}) is True

    @pytest.mark.unit
    def test_false_case_insensitive(self) -> None:
        assert evaluate_condition("FALSE", {}) is False

    # ── Key lookup (truthy check) ─────────────────────────────────

    @pytest.mark.unit
    def test_key_truthy_string(self) -> None:
        assert evaluate_condition("has_budget", {"has_budget": "yes"}) is True

    @pytest.mark.unit
    def test_key_truthy_true(self) -> None:
        assert evaluate_condition("enabled", {"enabled": True}) is True

    @pytest.mark.unit
    def test_key_truthy_nonzero(self) -> None:
        assert evaluate_condition("count", {"count": 5}) is True

    @pytest.mark.unit
    def test_key_falsy_false(self) -> None:
        assert evaluate_condition("enabled", {"enabled": False}) is False

    @pytest.mark.unit
    def test_key_falsy_zero(self) -> None:
        assert evaluate_condition("count", {"count": 0}) is False

    @pytest.mark.unit
    def test_key_falsy_empty_string(self) -> None:
        assert evaluate_condition("name", {"name": ""}) is False

    @pytest.mark.unit
    def test_key_falsy_none(self) -> None:
        assert evaluate_condition("val", {"val": None}) is False

    @pytest.mark.unit
    def test_missing_key_returns_false(self) -> None:
        assert evaluate_condition("missing", {}) is False

    # ── Equality comparison ───────────────────────────────────────

    @pytest.mark.unit
    def test_equality_match(self) -> None:
        assert (
            evaluate_condition(
                "priority == high",
                {"priority": "high"},
            )
            is True
        )

    @pytest.mark.unit
    def test_equality_mismatch(self) -> None:
        assert (
            evaluate_condition(
                "priority == high",
                {"priority": "low"},
            )
            is False
        )

    @pytest.mark.unit
    def test_equality_missing_key(self) -> None:
        assert evaluate_condition("env == prod", {}) is False

    @pytest.mark.unit
    def test_equality_extra_spaces(self) -> None:
        assert (
            evaluate_condition(
                "  env  ==  staging  ",
                {"env": "staging"},
            )
            is True
        )

    # ── Inequality comparison ─────────────────────────────────────

    @pytest.mark.unit
    def test_inequality_match(self) -> None:
        assert (
            evaluate_condition(
                "env != prod",
                {"env": "staging"},
            )
            is True
        )

    @pytest.mark.unit
    def test_inequality_mismatch(self) -> None:
        assert (
            evaluate_condition(
                "env != prod",
                {"env": "prod"},
            )
            is False
        )

    @pytest.mark.unit
    def test_inequality_missing_key(self) -> None:
        assert evaluate_condition("env != prod", {}) is True

    # ── Whitespace handling ───────────────────────────────────────

    @pytest.mark.unit
    def test_whitespace_stripped(self) -> None:
        assert evaluate_condition("  true  ", {}) is True

    @pytest.mark.unit
    def test_key_whitespace_stripped(self) -> None:
        assert evaluate_condition("  enabled  ", {"enabled": True}) is True

    # ── Empty and invalid expressions ─────────────────────────────

    @pytest.mark.unit
    def test_empty_expression_returns_false(self) -> None:
        assert evaluate_condition("", {}) is False

    @pytest.mark.unit
    def test_whitespace_only_returns_false(self) -> None:
        assert evaluate_condition("   ", {}) is False

    # ── Safety: no code execution ─────────────────────────────────

    @pytest.mark.unit
    def test_import_expression_treated_as_key(self) -> None:
        """Dangerous expressions are just treated as key lookups."""
        assert evaluate_condition("__import__('os')", {}) is False

    @pytest.mark.unit
    def test_eval_expression_treated_as_key(self) -> None:
        assert evaluate_condition("eval('1+1')", {}) is False
