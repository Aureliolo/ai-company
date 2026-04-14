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

    def test_per_agent(self) -> None:
        config = SandboxLifecycleConfig(strategy="per-agent")
        strategy = create_lifecycle_strategy(config)
        assert isinstance(strategy, PerAgentStrategy)

    def test_per_task(self) -> None:
        config = SandboxLifecycleConfig(strategy="per-task")
        strategy = create_lifecycle_strategy(config)
        assert isinstance(strategy, PerTaskStrategy)

    def test_per_call(self) -> None:
        config = SandboxLifecycleConfig(strategy="per-call")
        strategy = create_lifecycle_strategy(config)
        assert isinstance(strategy, PerCallStrategy)
