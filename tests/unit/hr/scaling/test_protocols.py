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

    async def record_run(self) -> None:
        pass


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
class TestScalingProtocols:
    """Runtime checkability of scaling protocols."""

    @pytest.mark.parametrize(
        ("protocol", "good_cls", "bad_cls"),
        [
            (ScalingStrategy, _StubStrategy, _NotAStrategy),
            (ScalingSignalSource, _StubSignalSource, _NotAStrategy),
            (ScalingTrigger, _StubTrigger, _NotAStrategy),
            (ScalingGuard, _StubGuard, _NotAStrategy),
        ],
        ids=["strategy", "signal-source", "trigger", "guard"],
    )
    def test_protocol_isinstance_checks(
        self,
        protocol: type,
        good_cls: type,
        bad_cls: type,
    ) -> None:
        assert isinstance(good_cls(), protocol)
        assert not isinstance(bad_cls(), protocol)
