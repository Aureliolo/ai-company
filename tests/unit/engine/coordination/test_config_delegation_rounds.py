"""Tests for max_delegation_rounds on CoordinationConfig."""

import pytest
from pydantic import ValidationError

from synthorg.engine.coordination.config import CoordinationConfig


@pytest.mark.unit
class TestMaxDelegationRounds:
    def test_default_is_3(self) -> None:
        config = CoordinationConfig()
        assert config.max_delegation_rounds == 3

    def test_custom_value(self) -> None:
        config = CoordinationConfig(max_delegation_rounds=5)
        assert config.max_delegation_rounds == 5

    def test_minimum_is_1(self) -> None:
        config = CoordinationConfig(max_delegation_rounds=1)
        assert config.max_delegation_rounds == 1

    def test_below_minimum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CoordinationConfig(max_delegation_rounds=0)

    def test_maximum_is_20(self) -> None:
        config = CoordinationConfig(max_delegation_rounds=20)
        assert config.max_delegation_rounds == 20

    def test_above_maximum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CoordinationConfig(max_delegation_rounds=21)

    def test_frozen(self) -> None:
        config = CoordinationConfig()
        with pytest.raises(ValidationError):
            config.max_delegation_rounds = 5  # type: ignore[misc]
