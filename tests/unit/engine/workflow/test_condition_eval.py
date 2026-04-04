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


@pytest.mark.unit
class TestCompoundConditions:
    """Compound expression evaluation (AND / OR / NOT / parentheses)."""

    # ── AND ───────────────────────────────────────────────────────

    def test_and_both_true(self) -> None:
        ctx = {"priority": "high", "env": "prod"}
        assert evaluate_condition("priority == high AND env == prod", ctx) is True

    def test_and_left_false(self) -> None:
        ctx = {"priority": "low", "env": "prod"}
        assert evaluate_condition("priority == high AND env == prod", ctx) is False

    def test_and_right_false(self) -> None:
        ctx = {"priority": "high", "env": "staging"}
        assert evaluate_condition("priority == high AND env == staging2", ctx) is False

    def test_and_both_false(self) -> None:
        assert evaluate_condition("a == 1 AND b == 2", {}) is False

    # ── OR ────────────────────────────────────────────────────────

    def test_or_both_true(self) -> None:
        ctx = {"a": "1", "b": "2"}
        assert evaluate_condition("a == 1 OR b == 2", ctx) is True

    def test_or_left_true(self) -> None:
        ctx = {"a": "1"}
        assert evaluate_condition("a == 1 OR b == 2", ctx) is True

    def test_or_right_true(self) -> None:
        ctx = {"b": "2"}
        assert evaluate_condition("a == 1 OR b == 2", ctx) is True

    def test_or_both_false(self) -> None:
        assert evaluate_condition("a == 1 OR b == 2", {}) is False

    # ── NOT ───────────────────────────────────────────────────────

    def test_not_true_becomes_false(self) -> None:
        assert evaluate_condition("NOT true", {}) is False

    def test_not_false_becomes_true(self) -> None:
        assert evaluate_condition("NOT false", {}) is True

    def test_not_key_truthy(self) -> None:
        assert evaluate_condition("NOT enabled", {"enabled": True}) is False

    def test_not_key_falsy(self) -> None:
        assert evaluate_condition("NOT enabled", {"enabled": False}) is True

    def test_not_comparison_true(self) -> None:
        ctx = {"priority": "high"}
        assert evaluate_condition("NOT priority == low", ctx) is True

    def test_not_comparison_false(self) -> None:
        ctx = {"priority": "low"}
        assert evaluate_condition("NOT priority == low", ctx) is False

    # ── Precedence (AND binds tighter than OR) ────────────────────

    def test_and_binds_tighter_than_or(self) -> None:
        # "a OR b AND c" is "a OR (b AND c)"
        ctx = {"a": "1"}
        assert evaluate_condition("a == 1 OR b == 2 AND c == 3", ctx) is True

    def test_and_binds_tighter_both_false(self) -> None:
        # "a OR b AND c" -- a=false, b=true, c=false -> false OR false = false
        ctx = {"b": "2"}
        assert evaluate_condition("a == 1 OR b == 2 AND c == 3", ctx) is False

    # ── Parenthesized groups ──────────────────────────────────────

    def test_parens_override_precedence(self) -> None:
        # "(a OR b) AND c" -- a=true, c=false -> true AND false = false
        ctx = {"a": "1"}
        assert evaluate_condition("(a == 1 OR b == 2) AND c == 3", ctx) is False

    def test_parens_group_true(self) -> None:
        ctx = {"a": "1", "c": "3"}
        assert evaluate_condition("(a == 1 OR b == 2) AND c == 3", ctx) is True

    def test_nested_parens(self) -> None:
        ctx = {"a": "1", "b": "2", "c": "3"}
        result = evaluate_condition("NOT (a == 1 AND (b == 2 OR c == 99))", ctx)
        # a==1 AND (b==2 OR c==99) -> True AND True -> True; NOT True -> False
        assert result is False

    def test_nested_parens_inner_false(self) -> None:
        ctx = {"a": "1"}
        result = evaluate_condition("NOT (a == 1 AND (b == 2 OR c == 99))", ctx)
        # a==1 AND (False OR False) -> True AND False -> False; NOT False -> True
        assert result is True

    # ── Case insensitivity of operators ───────────────────────────

    def test_lowercase_operators(self) -> None:
        ctx = {"a": "1", "b": "2"}
        assert evaluate_condition("a == 1 and b == 2", ctx) is True

    def test_mixed_case_operators(self) -> None:
        ctx = {"a": "1"}
        assert evaluate_condition("a == 1 Or not b", ctx) is True

    # ── Keyword in value (must not split) ─────────────────────────

    def test_keyword_in_value_and(self) -> None:
        ctx = {"brand": "ORLANDO"}
        assert evaluate_condition("brand == ORLANDO", ctx) is True

    def test_keyword_in_value_or(self) -> None:
        ctx = {"city": "YORK"}
        assert evaluate_condition("city == YORK", ctx) is True

    def test_keyword_in_value_not(self) -> None:
        ctx = {"tag": "NOTICE"}
        assert evaluate_condition("tag == NOTICE", ctx) is True

    # ── Edge cases ────────────────────────────────────────────────

    def test_empty_parens_returns_false(self) -> None:
        assert evaluate_condition("() AND true", {}) is False

    def test_malformed_double_operator(self) -> None:
        assert evaluate_condition("AND AND", {}) is False

    def test_trailing_operator(self) -> None:
        assert evaluate_condition("true AND", {}) is False

    def test_leading_operator(self) -> None:
        assert evaluate_condition("AND true", {}) is False

    # ── Complex real-world expression ─────────────────────────────

    def test_complex_expression(self) -> None:
        ctx = {"has_budget": "yes", "priority": "critical", "env": "staging"}
        result = evaluate_condition(
            "has_budget AND (priority == high OR priority == critical)"
            " AND NOT env == prod",
            ctx,
        )
        assert result is True

    def test_complex_expression_fails(self) -> None:
        ctx = {"has_budget": "yes", "priority": "low", "env": "staging"}
        result = evaluate_condition(
            "has_budget AND (priority == high OR priority == critical)"
            " AND NOT env == prod",
            ctx,
        )
        assert result is False

    # ── Backward compatibility ────────────────────────────────────

    def test_simple_expressions_still_work(self) -> None:
        """Ensure the quick-path for simple expressions is intact."""
        assert evaluate_condition("true", {}) is True
        assert evaluate_condition("false", {}) is False
        assert evaluate_condition("x == 1", {"x": "1"}) is True
        assert evaluate_condition("missing", {}) is False
        assert evaluate_condition("", {}) is False
