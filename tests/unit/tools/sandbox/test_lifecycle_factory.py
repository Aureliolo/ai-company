"""Tests for lifecycle strategy factory."""

import pytest

from synthorg.tools.sandbox.lifecycle.config import SandboxLifecycleConfig
from synthorg.tools.sandbox.lifecycle.factory import create_lifecycle_strategy
from synthorg.tools.sandbox.lifecycle.per_agent import PerAgentStrategy
from synthorg.tools.sandbox.lifecycle.per_call import PerCallStrategy
from synthorg.tools.sandbox.lifecycle.per_task import PerTaskStrategy

pytestmark = pytest.mark.unit


class TestCreateLifecycleStrategy:
    """Factory dispatches to correct strategy implementation."""

    @pytest.mark.parametrize(
        ("strategy", "expected_cls"),
        [
            ("per-agent", PerAgentStrategy),
            ("per-task", PerTaskStrategy),
            ("per-call", PerCallStrategy),
        ],
    )
    def test_valid_strategies(
        self,
        strategy: str,
        expected_cls: type,
    ) -> None:
        config = SandboxLifecycleConfig(strategy=strategy)  # type: ignore[arg-type]
        result = create_lifecycle_strategy(config)
        assert isinstance(result, expected_cls)
