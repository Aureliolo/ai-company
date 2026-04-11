"""Tests for scaling protocol runtime checkability."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.models import ScalingContext, ScalingDecision, ScalingSignal
from synthorg.hr.scaling.protocols import (
    ScalingGuard,
    ScalingSignalSource,
    ScalingStrategy,
    ScalingTrigger,
)

# -- Concrete test implementations ------------------------------------------


class _StubStrategy:
    """Minimal implementation satisfying ScalingStrategy protocol."""

    @property
    def name(self) -> NotBlankStr:
        return NotBlankStr("stub")

    @property
    def action_types(self) -> frozenset[ScalingActionType]:
        return frozenset({ScalingActionType.HIRE})

    async def evaluate(
        self,
        context: ScalingContext,
    ) -> tuple[ScalingDecision, ...]:
        return ()


class _StubSignalSource:
    """Minimal implementation satisfying ScalingSignalSource protocol."""

    @property
    def name(self) -> NotBlankStr:
        return NotBlankStr("stub")

    async def collect(
        self,
        agent_ids: tuple[NotBlankStr, ...],
    ) -> tuple[ScalingSignal, ...]:
        return ()


class _StubTrigger:
    """Minimal implementation satisfying ScalingTrigger protocol."""

    @property
    def name(self) -> NotBlankStr:
        return NotBlankStr("stub")

    async def should_trigger(self) -> bool:
        return True


class _StubGuard:
    """Minimal implementation satisfying ScalingGuard protocol."""

    @property
    def name(self) -> NotBlankStr:
        return NotBlankStr("stub")

    async def filter(
        self,
        decisions: tuple[ScalingDecision, ...],
    ) -> tuple[ScalingDecision, ...]:
        return decisions


class _NotAStrategy:
    """Does NOT satisfy ScalingStrategy protocol."""

    def some_method(self) -> None:
        pass


# -- Tests -------------------------------------------------------------------


@pytest.mark.unit
class TestScalingStrategyProtocol:
    """ScalingStrategy runtime checkability."""

    def test_valid_implementation_is_instance(self) -> None:
        assert isinstance(_StubStrategy(), ScalingStrategy)

    def test_non_implementation_is_not_instance(self) -> None:
        assert not isinstance(_NotAStrategy(), ScalingStrategy)


@pytest.mark.unit
class TestScalingSignalSourceProtocol:
    """ScalingSignalSource runtime checkability."""

    def test_valid_implementation_is_instance(self) -> None:
        assert isinstance(_StubSignalSource(), ScalingSignalSource)

    def test_non_implementation_is_not_instance(self) -> None:
        assert not isinstance(_NotAStrategy(), ScalingSignalSource)


@pytest.mark.unit
class TestScalingTriggerProtocol:
    """ScalingTrigger runtime checkability."""

    def test_valid_implementation_is_instance(self) -> None:
        assert isinstance(_StubTrigger(), ScalingTrigger)

    def test_non_implementation_is_not_instance(self) -> None:
        assert not isinstance(_NotAStrategy(), ScalingTrigger)


@pytest.mark.unit
class TestScalingGuardProtocol:
    """ScalingGuard runtime checkability."""

    def test_valid_implementation_is_instance(self) -> None:
        assert isinstance(_StubGuard(), ScalingGuard)

    def test_non_implementation_is_not_instance(self) -> None:
        assert not isinstance(_NotAStrategy(), ScalingGuard)
