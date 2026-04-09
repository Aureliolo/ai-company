"""Tests for HybridInjectionStrategy."""

from unittest.mock import AsyncMock

import pytest

from synthorg.ontology.injection.hybrid import HybridInjectionStrategy
from synthorg.ontology.injection.tool import LOOKUP_ENTITY_TOOL_NAME
from synthorg.providers.enums import MessageRole


@pytest.mark.unit
class TestHybridInjectionStrategy:
    """Tests for HybridInjectionStrategy."""

    async def test_prepare_messages_injects_core_entities(
        self,
        mock_backend: AsyncMock,
    ) -> None:
        """Returns system message with core entity definitions."""
        strategy = HybridInjectionStrategy(backend=mock_backend)
        messages = await strategy.prepare_messages(
            agent_id="agent-1",
            task_context="Do work",
            token_budget=5000,
        )
        assert len(messages) == 1
        assert messages[0].role == MessageRole.SYSTEM
        assert messages[0].content is not None
        assert "Task" in messages[0].content

    async def test_user_entities_not_in_prompt(
        self,
        mock_backend: AsyncMock,
    ) -> None:
        """USER entities are not injected in the prompt."""
        strategy = HybridInjectionStrategy(backend=mock_backend)
        messages = await strategy.prepare_messages(
            agent_id="agent-1",
            task_context="Do work",
            token_budget=5000,
        )
        assert messages[0].content is not None
        assert "Invoice" not in messages[0].content

    def test_provides_lookup_tool(
        self,
        mock_backend: AsyncMock,
    ) -> None:
        """Returns the lookup_entity tool for extended access."""
        strategy = HybridInjectionStrategy(backend=mock_backend)
        tools = strategy.get_tool_definitions()
        assert len(tools) == 1
        assert tools[0].name == LOOKUP_ENTITY_TOOL_NAME

    def test_strategy_name(
        self,
        mock_backend: AsyncMock,
    ) -> None:
        """Strategy name is 'hybrid'."""
        strategy = HybridInjectionStrategy(backend=mock_backend)
        assert strategy.strategy_name == "hybrid"

    def test_tool_property(
        self,
        mock_backend: AsyncMock,
    ) -> None:
        """tool property returns the LookupEntityTool."""
        strategy = HybridInjectionStrategy(backend=mock_backend)
        from synthorg.ontology.injection.tool import LookupEntityTool

        assert isinstance(strategy.tool, LookupEntityTool)

    async def test_empty_when_no_core_entities(
        self,
        mock_backend: AsyncMock,
    ) -> None:
        """Returns empty messages when no CORE entities exist."""
        mock_backend.list_entities = AsyncMock(return_value=())
        strategy = HybridInjectionStrategy(backend=mock_backend)
        messages = await strategy.prepare_messages(
            agent_id="agent-1",
            task_context="Do work",
            token_budget=5000,
        )
        assert messages == ()
