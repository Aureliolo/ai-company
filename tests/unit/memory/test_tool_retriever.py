"""Tests for ToolBasedInjectionStrategy."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from synthorg.core.enums import MemoryCategory
from synthorg.memory.injection import InjectionStrategy, MemoryInjectionStrategy
from synthorg.memory.models import MemoryEntry, MemoryMetadata
from synthorg.memory.retrieval_config import MemoryRetrievalConfig
from synthorg.memory.tool_retriever import ToolBasedInjectionStrategy


def _make_entry(
    *,
    entry_id: str = "mem-1",
    agent_id: str = "agent-1",
    content: str = "test memory",
    relevance_score: float | None = 0.8,
) -> MemoryEntry:
    return MemoryEntry(
        id=entry_id,
        agent_id=agent_id,
        category=MemoryCategory.EPISODIC,
        content=content,
        metadata=MemoryMetadata(),
        created_at=datetime.now(UTC),
        relevance_score=relevance_score,
    )


def _make_backend(
    entries: tuple[MemoryEntry, ...] = (),
) -> AsyncMock:
    backend = AsyncMock()
    backend.retrieve = AsyncMock(return_value=entries)
    backend.get = AsyncMock(return_value=entries[0] if entries else None)
    return backend


def _tool_config() -> MemoryRetrievalConfig:
    return MemoryRetrievalConfig(
        strategy=InjectionStrategy.TOOL_BASED,
        min_relevance=0.0,
    )


# -- Protocol compliance ---------------------------------------------------


@pytest.mark.unit
class TestToolBasedProtocol:
    def test_satisfies_protocol(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        assert isinstance(strategy, MemoryInjectionStrategy)

    def test_strategy_name(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        assert strategy.strategy_name == "tool_based"


# -- prepare_messages -------------------------------------------------------


@pytest.mark.unit
class TestPrepareMessages:
    async def test_returns_instruction_message(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        result = await strategy.prepare_messages(
            agent_id="agent-1",
            query_text="query",
            token_budget=1000,
        )
        assert len(result) == 1
        assert result[0].content is not None
        assert "memory" in result[0].content.lower()

    async def test_zero_budget_returns_empty(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        result = await strategy.prepare_messages(
            agent_id="agent-1",
            query_text="query",
            token_budget=0,
        )
        assert result == ()


# -- get_tool_definitions ---------------------------------------------------


@pytest.mark.unit
class TestToolDefinitions:
    def test_returns_two_tools(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        tools = strategy.get_tool_definitions()
        assert len(tools) == 2

    def test_tool_names(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        tools = strategy.get_tool_definitions()
        names = {t.name for t in tools}
        assert "search_memory" in names
        assert "recall_memory" in names

    def test_tools_have_schemas(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        tools = strategy.get_tool_definitions()
        for tool in tools:
            assert tool.parameters_schema
            assert "type" in tool.parameters_schema

    def test_search_memory_schema(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        tools = strategy.get_tool_definitions()
        search = next(t for t in tools if t.name == "search_memory")
        props = search.parameters_schema.get("properties", {})
        assert "query" in props
        assert "limit" in props

    def test_recall_memory_schema(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        tools = strategy.get_tool_definitions()
        recall = next(t for t in tools if t.name == "recall_memory")
        props = recall.parameters_schema.get("properties", {})
        assert "memory_id" in props


# -- handle_tool_call -------------------------------------------------------


@pytest.mark.unit
class TestHandleToolCall:
    async def test_search_memory_returns_results(self) -> None:
        entry = _make_entry(content="found memory")
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend((entry,)),
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="search_memory",
            arguments={"query": "test search"},
            agent_id="agent-1",
        )
        assert "found memory" in result

    async def test_recall_memory_returns_entry(self) -> None:
        entry = _make_entry(content="recalled memory")
        backend = _make_backend((entry,))
        backend.get = AsyncMock(return_value=entry)
        strategy = ToolBasedInjectionStrategy(
            backend=backend,
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="recall_memory",
            arguments={"memory_id": "mem-1"},
            agent_id="agent-1",
        )
        assert "recalled memory" in result

    async def test_recall_memory_not_found(self) -> None:
        backend = _make_backend()
        backend.get = AsyncMock(return_value=None)
        strategy = ToolBasedInjectionStrategy(
            backend=backend,
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="recall_memory",
            arguments={"memory_id": "nonexistent"},
            agent_id="agent-1",
        )
        assert "not found" in result.lower()

    async def test_unknown_tool_raises(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        with pytest.raises(ValueError, match="Unknown tool"):
            await strategy.handle_tool_call(
                tool_name="unknown_tool",
                arguments={},
                agent_id="agent-1",
            )

    async def test_search_with_limit(self) -> None:
        entry = _make_entry(content="limited result")
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend((entry,)),
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="search_memory",
            arguments={"query": "test", "limit": 5},
            agent_id="agent-1",
        )
        assert isinstance(result, str)

    async def test_search_empty_results(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="search_memory",
            arguments={"query": "nothing here"},
            agent_id="agent-1",
        )
        assert "no memories found" in result.lower()

    async def test_search_error_returns_generic_message(self) -> None:
        from synthorg.memory.errors import MemoryRetrievalError

        backend = _make_backend()
        backend.retrieve = AsyncMock(
            side_effect=MemoryRetrievalError("db down"),
        )
        strategy = ToolBasedInjectionStrategy(
            backend=backend,
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="search_memory",
            arguments={"query": "will fail"},
            agent_id="agent-1",
        )
        assert "unavailable" in result.lower()
        # Must NOT leak internal error details
        assert "db down" not in result

    async def test_search_empty_query_returns_error(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="search_memory",
            arguments={"query": ""},
            agent_id="agent-1",
        )
        assert "non-empty" in result.lower()

    async def test_search_with_categories(self) -> None:
        entry = _make_entry(content="categorized memory")
        backend = _make_backend((entry,))
        strategy = ToolBasedInjectionStrategy(
            backend=backend,
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="search_memory",
            arguments={
                "query": "test",
                "categories": ["episodic", "semantic"],
            },
            agent_id="agent-1",
        )
        assert isinstance(result, str)
        # Verify categories were passed to the query
        call_args = backend.retrieve.call_args
        query = call_args[0][1]
        assert query.categories is not None
        assert MemoryCategory.EPISODIC in query.categories

    async def test_recall_empty_memory_id_returns_error(self) -> None:
        strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=_tool_config(),
        )
        result = await strategy.handle_tool_call(
            tool_name="recall_memory",
            arguments={"memory_id": ""},
            agent_id="agent-1",
        )
        assert "memory_id is required" in result.lower()

    async def test_search_system_error_propagates(self) -> None:
        backend = _make_backend()
        # builtins.MemoryError (not synthorg domain MemoryError)
        backend.retrieve = AsyncMock(side_effect=MemoryError)
        strategy = ToolBasedInjectionStrategy(
            backend=backend,
            config=_tool_config(),
        )
        with pytest.raises(MemoryError):
            await strategy.handle_tool_call(
                tool_name="search_memory",
                arguments={"query": "test"},
                agent_id="agent-1",
            )

    async def test_recall_system_error_propagates(self) -> None:
        backend = _make_backend()
        backend.get = AsyncMock(side_effect=RecursionError)
        strategy = ToolBasedInjectionStrategy(
            backend=backend,
            config=_tool_config(),
        )
        with pytest.raises(RecursionError):
            await strategy.handle_tool_call(
                tool_name="recall_memory",
                arguments={"memory_id": "mem-1"},
                agent_id="agent-1",
            )
