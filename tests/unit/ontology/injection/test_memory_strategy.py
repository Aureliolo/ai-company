"""Tests for MemoryBasedInjectionStrategy."""

import pytest

from synthorg.ontology.injection.memory import MemoryBasedInjectionStrategy


@pytest.mark.unit
class TestMemoryBasedInjectionStrategy:
    """Tests for MemoryBasedInjectionStrategy."""

    async def test_prepare_messages_returns_empty(self) -> None:
        """Memory strategy injects no messages."""
        strategy = MemoryBasedInjectionStrategy()
        messages = await strategy.prepare_messages(
            agent_id="agent-1",
            task_context="Do work",
            token_budget=5000,
        )
        assert messages == ()

    def test_get_tool_definitions_returns_empty(self) -> None:
        """Memory strategy provides no tools."""
        strategy = MemoryBasedInjectionStrategy()
        assert strategy.get_tool_definitions() == ()

    def test_strategy_name(self) -> None:
        """Strategy name is 'memory'."""
        strategy = MemoryBasedInjectionStrategy()
        assert strategy.strategy_name == "memory"
