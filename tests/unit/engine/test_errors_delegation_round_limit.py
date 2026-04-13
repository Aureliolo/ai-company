"""Tests for DelegationRoundLimitError."""

import pytest

from synthorg.engine.errors import DelegationRoundLimitError, EngineError


@pytest.mark.unit
class TestDelegationRoundLimitError:
    def test_is_engine_error(self) -> None:
        err = DelegationRoundLimitError(current_round=7, soft_limit=3)
        assert isinstance(err, EngineError)

    def test_attributes(self) -> None:
        err = DelegationRoundLimitError(current_round=7, soft_limit=3)
        assert err.current_round == 7
        assert err.soft_limit == 3

    def test_message_includes_limits(self) -> None:
        err = DelegationRoundLimitError(current_round=7, soft_limit=3)
        msg = str(err)
        assert "7" in msg
        assert "6" in msg  # hard limit = 2 * soft
        assert "3" in msg  # soft limit

    def test_default_soft_limit(self) -> None:
        err = DelegationRoundLimitError(current_round=6, soft_limit=3)
        assert err.soft_limit == 3
