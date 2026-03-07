"""Tests for ancestry cycle detection check."""

import pytest

from ai_company.communication.loop_prevention.ancestry import (
    check_ancestry,
)

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestCheckAncestry:
    def test_empty_chain_passes(self) -> None:
        result = check_ancestry((), "agent-a")
        assert result.passed is True
        assert result.mechanism == "ancestry"

    def test_delegatee_not_in_chain_passes(self) -> None:
        result = check_ancestry(("a", "b", "c"), "d")
        assert result.passed is True

    def test_delegatee_in_chain_fails(self) -> None:
        result = check_ancestry(("a", "b", "c"), "b")
        assert result.passed is False
        assert result.mechanism == "ancestry"
        assert "'b'" in result.message

    def test_delegatee_is_root_fails(self) -> None:
        result = check_ancestry(("root", "mid"), "root")
        assert result.passed is False

    def test_delegatee_is_last_in_chain_fails(self) -> None:
        result = check_ancestry(("a", "b"), "b")
        assert result.passed is False

    def test_single_element_chain_match_fails(self) -> None:
        result = check_ancestry(("x",), "x")
        assert result.passed is False

    def test_single_element_chain_no_match_passes(self) -> None:
        result = check_ancestry(("x",), "y")
        assert result.passed is True
