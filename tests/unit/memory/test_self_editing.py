"""Tests for SelfEditingMemoryStrategy and self-editing tool wrappers."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from synthorg.core.enums import MemoryCategory, ToolCategory
from synthorg.memory.injection import InjectionStrategy
from synthorg.memory.models import MemoryEntry, MemoryMetadata
from synthorg.memory.protocol import MemoryBackend
from synthorg.memory.self_editing import (
    _MAX_CONTENT_LEN,
    _MAX_MEMORY_ID_LEN,
    ARCHIVAL_MEMORY_SEARCH_TOOL,
    ARCHIVAL_MEMORY_WRITE_TOOL,
    CORE_MEMORY_READ_TOOL,
    CORE_MEMORY_WRITE_TOOL,
    RECALL_MEMORY_READ_TOOL,
    RECALL_MEMORY_WRITE_TOOL,
    SelfEditingMemoryConfig,
    SelfEditingMemoryStrategy,
    _extract_str,
)
from synthorg.memory.tool_retriever import ToolBasedInjectionStrategy
from synthorg.memory.tools import (
    ArchivalMemorySearchTool,
    ArchivalMemoryWriteTool,
    CoreMemoryReadTool,
    CoreMemoryWriteTool,
    RecallMemoryReadTool,
    RecallMemoryWriteTool,
    create_self_editing_tools,
    registry_with_memory_tools,
)
from synthorg.tools.base import BaseTool, ToolExecutionResult
from synthorg.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    *,
    entry_id: str = "mem-1",
    agent_id: str = "agent-1",
    content: str = "test memory content",
    category: MemoryCategory = MemoryCategory.SEMANTIC,
    tags: tuple[str, ...] = ("core",),
) -> MemoryEntry:
    return MemoryEntry(
        id=entry_id,
        agent_id=agent_id,
        category=category,
        content=content,
        metadata=MemoryMetadata(tags=tags),
        created_at=datetime.now(UTC),
    )


def _make_backend(
    *,
    entries: tuple[MemoryEntry, ...] = (),
    store_return: str = "new-mem-id",
) -> AsyncMock:
    backend = AsyncMock(spec=MemoryBackend)
    backend.retrieve = AsyncMock(return_value=entries)
    backend.get = AsyncMock(return_value=entries[0] if entries else None)
    backend.store = AsyncMock(return_value=store_return)
    return backend


def _make_config(**kwargs: Any) -> SelfEditingMemoryConfig:
    return SelfEditingMemoryConfig(**kwargs)


def _make_strategy(
    *,
    backend: AsyncMock | None = None,
    config: SelfEditingMemoryConfig | None = None,
    entries: tuple[MemoryEntry, ...] = (),
) -> SelfEditingMemoryStrategy:
    if backend is None:
        backend = _make_backend(entries=entries)
    if config is None:
        config = _make_config()
    return SelfEditingMemoryStrategy(backend=backend, config=config)


def _make_empty_registry() -> ToolRegistry:
    return ToolRegistry([])


class _DummyTool(BaseTool):
    """Minimal concrete tool for testing registry augmentation."""

    def __init__(self, name: str = "dummy_tool") -> None:
        super().__init__(
            name=name,
            category=ToolCategory.OTHER,
        )

    async def execute(self, *, arguments: dict[str, Any]) -> ToolExecutionResult:
        return ToolExecutionResult(content="dummy")


# ---------------------------------------------------------------------------
# TestSelfEditingMemoryConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSelfEditingMemoryConfig:
    def test_default_values(self) -> None:
        config = SelfEditingMemoryConfig()

        assert config.core_memory_token_budget == 1024
        assert config.core_memory_tag == "core"
        assert config.allow_core_writes is True
        assert config.core_max_entries == 20
        assert config.archival_search_limit == 10
        assert MemoryCategory.WORKING not in config.archival_categories
        assert MemoryCategory.EPISODIC in config.archival_categories
        assert MemoryCategory.SEMANTIC in config.archival_categories
        assert MemoryCategory.PROCEDURAL in config.archival_categories
        assert MemoryCategory.SOCIAL in config.archival_categories
        assert config.write_auto_tag is True

    @pytest.mark.parametrize(
        ("budget", "valid"),
        [
            (256, True),
            (1024, True),
            (8192, True),
            (255, False),
            (8193, False),
        ],
    )
    def test_core_token_budget_bounds(self, budget: int, valid: bool) -> None:
        if valid:
            config = SelfEditingMemoryConfig(core_memory_token_budget=budget)
            assert config.core_memory_token_budget == budget
        else:
            with pytest.raises(ValidationError):
                SelfEditingMemoryConfig(core_memory_token_budget=budget)

    def test_working_rejected_in_archival_categories(self) -> None:
        """WORKING category must not be accepted in archival_categories."""
        with pytest.raises(ValidationError):
            SelfEditingMemoryConfig(
                archival_categories=frozenset({MemoryCategory.WORKING}),
            )

    def test_working_mixed_with_valid_categories_still_rejected(self) -> None:
        """Even one WORKING entry in an otherwise valid set must be rejected."""
        with pytest.raises(ValidationError):
            SelfEditingMemoryConfig(
                archival_categories=frozenset(
                    {
                        MemoryCategory.WORKING,
                        MemoryCategory.EPISODIC,
                    }
                ),
            )

    def test_frozen_prevents_mutation(self) -> None:
        config = SelfEditingMemoryConfig()
        with pytest.raises(ValidationError):
            config.allow_core_writes = False  # type: ignore[misc]

    def test_allow_core_writes_flag(self) -> None:
        enabled = SelfEditingMemoryConfig(allow_core_writes=True)
        disabled = SelfEditingMemoryConfig(allow_core_writes=False)

        assert enabled.allow_core_writes is True
        assert disabled.allow_core_writes is False

    def test_empty_archival_categories_rejected(self) -> None:
        """Empty archival_categories must be rejected.

        An empty set blocks all archival writes.
        """
        with pytest.raises(ValidationError):
            SelfEditingMemoryConfig(archival_categories=frozenset())


# ---------------------------------------------------------------------------
# TestSelfEditingMemoryStrategyInit
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSelfEditingMemoryStrategyInit:
    def test_requires_durable_backend(self) -> None:
        """Constructor must reject backend=None."""
        with pytest.raises(TypeError):
            SelfEditingMemoryStrategy(
                backend=None,  # type: ignore[arg-type]
                config=SelfEditingMemoryConfig(),
            )

    def test_strategy_name_is_self_editing(self) -> None:
        strategy = _make_strategy()

        assert strategy.strategy_name == "self_editing"
        assert strategy.strategy_name == InjectionStrategy.SELF_EDITING.value


# ---------------------------------------------------------------------------
# TestSelfEditingMemoryStrategyPrepareMessages
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSelfEditingMemoryStrategyPrepareMessages:
    async def test_returns_system_message_with_core_entries(self) -> None:
        entry = _make_entry(
            content="I am a customer support agent",
            category=MemoryCategory.SEMANTIC,
            tags=("core",),
        )
        backend = _make_backend(entries=(entry,))
        strategy = _make_strategy(backend=backend)

        messages = await strategy.prepare_messages(
            agent_id="agent-1",
            query_text="current task",
            token_budget=2048,
        )

        assert len(messages) == 1
        assert messages[0].content is not None
        assert "customer support agent" in messages[0].content

    async def test_respects_token_budget(self) -> None:
        """token_budget=0 must return an empty tuple."""
        entry = _make_entry(content="x" * 500)
        backend = _make_backend(entries=(entry,))
        strategy = _make_strategy(backend=backend)

        messages = await strategy.prepare_messages(
            agent_id="agent-1",
            query_text="task",
            token_budget=0,
        )

        assert messages == ()

    async def test_empty_core_memory_returns_empty_tuple(self) -> None:
        backend = _make_backend(entries=())
        strategy = _make_strategy(backend=backend)

        messages = await strategy.prepare_messages(
            agent_id="agent-1",
            query_text="anything",
            token_budget=1024,
        )

        assert messages == ()

    async def test_only_fetches_semantic_core_tagged_entries(self) -> None:
        """retrieve() must use text=None, SEMANTIC category, core tag."""
        backend = _make_backend(entries=())
        config = _make_config(core_memory_tag="core")
        strategy = _make_strategy(backend=backend, config=config)

        await strategy.prepare_messages(
            agent_id="agent-1",
            query_text="anything",
            token_budget=1024,
        )

        call_args = backend.retrieve.call_args
        query = call_args.args[1]
        assert query.text is None
        assert MemoryCategory.SEMANTIC in (query.categories or frozenset())
        assert "core" in query.tags

    async def test_backend_error_returns_empty_not_raise(self) -> None:
        """Non-system backend errors in prepare_messages must return () -- not raise."""
        backend = _make_backend()
        backend.retrieve = AsyncMock(side_effect=RuntimeError("backend down"))
        strategy = _make_strategy(backend=backend)

        result = await strategy.prepare_messages(
            agent_id="agent-1",
            query_text="anything",
            token_budget=1024,
        )

        assert result == ()


# ---------------------------------------------------------------------------
# TestSelfEditingMemoryStrategyToolDefinitions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSelfEditingMemoryStrategyToolDefinitions:
    def test_returns_six_definitions(self) -> None:
        strategy = _make_strategy()

        assert len(strategy.get_tool_definitions()) == 6

    def test_tool_names_match_constants(self) -> None:
        strategy = _make_strategy()
        names = {d.name for d in strategy.get_tool_definitions()}

        assert names == {
            CORE_MEMORY_READ_TOOL,
            CORE_MEMORY_WRITE_TOOL,
            ARCHIVAL_MEMORY_SEARCH_TOOL,
            ARCHIVAL_MEMORY_WRITE_TOOL,
            RECALL_MEMORY_READ_TOOL,
            RECALL_MEMORY_WRITE_TOOL,
        }

    def test_all_definitions_have_schemas(self) -> None:
        strategy = _make_strategy()

        for defn in strategy.get_tool_definitions():
            assert defn.parameters_schema is not None, f"{defn.name} missing schema"
            assert "type" in defn.parameters_schema


# ---------------------------------------------------------------------------
# TestCoreMemoryReadTool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoreMemoryReadTool:
    async def test_execute_returns_formatted_core_memories(self) -> None:
        entry = _make_entry(content="I am an expert researcher")
        backend = _make_backend(entries=(entry,))
        strategy = _make_strategy(backend=backend)
        tool = CoreMemoryReadTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={})

        assert isinstance(result, ToolExecutionResult)
        assert "expert researcher" in result.content
        assert not result.is_error

    async def test_execute_empty_returns_non_error(self) -> None:
        """Empty core memory should return a success result, not an error."""
        backend = _make_backend(entries=())
        strategy = _make_strategy(backend=backend)
        tool = CoreMemoryReadTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={})

        assert isinstance(result, ToolExecutionResult)
        assert not result.is_error

    def test_is_not_error_on_success(self) -> None:
        """Tool must use ToolCategory.MEMORY."""
        strategy = _make_strategy()
        tool = CoreMemoryReadTool(strategy=strategy, agent_id="agent-1")

        assert tool.category == ToolCategory.MEMORY


# ---------------------------------------------------------------------------
# TestCoreMemoryWriteTool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoreMemoryWriteTool:
    async def test_execute_stores_semantic_with_core_tag(self) -> None:
        backend = _make_backend()
        strategy = _make_strategy(backend=backend)
        tool = CoreMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "I am an expert in Go programming"},
        )

        assert not result.is_error
        assert backend.store.called
        request = backend.store.call_args.args[1]
        assert request.category == MemoryCategory.SEMANTIC
        assert "core" in request.metadata.tags

    async def test_execute_rejected_when_allow_core_writes_false(self) -> None:
        config = _make_config(allow_core_writes=False)
        backend = _make_backend()
        strategy = _make_strategy(backend=backend, config=config)
        tool = CoreMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "This should be rejected"},
        )

        assert result.is_error
        assert not backend.store.called

    async def test_execute_rejected_when_max_entries_exceeded(self) -> None:
        max_entries = 3
        config = _make_config(core_max_entries=max_entries)
        entries = tuple(
            _make_entry(entry_id=f"core-{i}", content=f"core memory {i}")
            for i in range(max_entries)
        )
        backend = _make_backend(entries=entries)
        strategy = _make_strategy(backend=backend, config=config)
        tool = CoreMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={"content": "one too many"})

        assert result.is_error
        assert not backend.store.called

    async def test_execute_content_required(self) -> None:
        strategy = _make_strategy()
        tool = CoreMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={"content": "   "})

        assert result.is_error

    async def test_execute_oversized_content_returns_error(self) -> None:
        backend = _make_backend()
        strategy = _make_strategy(backend=backend)
        tool = CoreMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "x" * (_MAX_CONTENT_LEN + 1)},
        )

        assert result.is_error
        assert not backend.store.called


# ---------------------------------------------------------------------------
# TestArchivalMemorySearchTool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestArchivalMemorySearchTool:
    async def test_execute_searches_by_query(self) -> None:
        entry = _make_entry(
            content="design decision from 2025",
            category=MemoryCategory.EPISODIC,
            tags=("self_edited",),
        )
        backend = _make_backend(entries=(entry,))
        strategy = _make_strategy(backend=backend)
        tool = ArchivalMemorySearchTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={"query": "design decision"})

        assert isinstance(result, ToolExecutionResult)
        assert "design decision from 2025" in result.content
        assert not result.is_error

    async def test_execute_category_filter_applied(self) -> None:
        backend = _make_backend(entries=())
        strategy = _make_strategy(backend=backend)
        tool = ArchivalMemorySearchTool(strategy=strategy, agent_id="agent-1")

        await tool.execute(arguments={"query": "some query", "category": "semantic"})

        query = backend.retrieve.call_args.args[1]
        assert MemoryCategory.SEMANTIC in (query.categories or frozenset())

    async def test_execute_limit_clamped_to_config(self) -> None:
        config = _make_config(archival_search_limit=5)
        backend = _make_backend(entries=())
        strategy = _make_strategy(backend=backend, config=config)
        tool = ArchivalMemorySearchTool(strategy=strategy, agent_id="agent-1")

        await tool.execute(arguments={"query": "anything", "limit": 100})

        query = backend.retrieve.call_args.args[1]
        assert query.limit <= 5

    async def test_execute_invalid_category_returns_error(self) -> None:
        strategy = _make_strategy()
        tool = ArchivalMemorySearchTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"query": "test", "category": "not_a_real_category"},
        )

        assert result.is_error

    async def test_execute_blank_query_returns_error(self) -> None:
        strategy = _make_strategy()
        tool = ArchivalMemorySearchTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={"query": "   "})

        assert result.is_error


# ---------------------------------------------------------------------------
# TestArchivalMemoryWriteTool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestArchivalMemoryWriteTool:
    async def test_execute_stores_with_auto_tag(self) -> None:
        backend = _make_backend()
        config = _make_config(write_auto_tag=True)
        strategy = _make_strategy(backend=backend, config=config)
        tool = ArchivalMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "learned something", "category": "episodic"},
        )

        assert not result.is_error
        assert backend.store.called
        request = backend.store.call_args.args[1]
        assert "self_edited" in request.metadata.tags

    async def test_execute_stores_without_auto_tag_when_disabled(self) -> None:
        backend = _make_backend()
        config = _make_config(write_auto_tag=False)
        strategy = _make_strategy(backend=backend, config=config)
        tool = ArchivalMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        await tool.execute(
            arguments={"content": "no auto tag", "category": "episodic"},
        )

        request = backend.store.call_args.args[1]
        assert "self_edited" not in request.metadata.tags

    async def test_execute_rejects_working_category(self) -> None:
        strategy = _make_strategy()
        tool = ArchivalMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "some content", "category": "working"},
        )

        assert result.is_error

    async def test_execute_blank_content_returns_error(self) -> None:
        strategy = _make_strategy()
        tool = ArchivalMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "   ", "category": "episodic"},
        )

        assert result.is_error

    async def test_execute_returns_memory_id(self) -> None:
        backend = _make_backend(store_return="archival-id-123")
        strategy = _make_strategy(backend=backend)
        tool = ArchivalMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "something meaningful", "category": "semantic"},
        )

        assert not result.is_error
        assert "archival-id-123" in result.content

    async def test_execute_oversized_content_returns_error(self) -> None:
        backend = _make_backend()
        strategy = _make_strategy(backend=backend)
        tool = ArchivalMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={
                "content": "y" * (_MAX_CONTENT_LEN + 1),
                "category": "episodic",
            },
        )

        assert result.is_error
        assert not backend.store.called


# ---------------------------------------------------------------------------
# TestRecallMemoryReadTool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRecallMemoryReadTool:
    async def test_execute_retrieves_by_id(self) -> None:
        entry = _make_entry(
            entry_id="recall-42",
            content="remembered event",
            category=MemoryCategory.EPISODIC,
            tags=("self_edited",),
        )
        backend = _make_backend()
        backend.get = AsyncMock(return_value=entry)
        strategy = _make_strategy(backend=backend)
        tool = RecallMemoryReadTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={"memory_id": "recall-42"})

        assert isinstance(result, ToolExecutionResult)
        assert "remembered event" in result.content
        assert not result.is_error

    async def test_execute_not_found_returns_error_string(self) -> None:
        backend = _make_backend()
        backend.get = AsyncMock(return_value=None)
        strategy = _make_strategy(backend=backend)
        tool = RecallMemoryReadTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={"memory_id": "does-not-exist"})

        assert result.is_error

    async def test_execute_blank_id_returns_error(self) -> None:
        strategy = _make_strategy()
        tool = RecallMemoryReadTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={"memory_id": "  "})

        assert result.is_error

    async def test_execute_oversized_memory_id_returns_error(self) -> None:
        backend = _make_backend()
        strategy = _make_strategy(backend=backend)
        tool = RecallMemoryReadTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"memory_id": "z" * (_MAX_MEMORY_ID_LEN + 1)},
        )

        assert result.is_error
        assert not backend.get.called


# ---------------------------------------------------------------------------
# TestRecallMemoryWriteTool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRecallMemoryWriteTool:
    async def test_execute_forces_episodic_category(self) -> None:
        backend = _make_backend()
        strategy = _make_strategy(backend=backend)
        tool = RecallMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        await tool.execute(
            arguments={"content": "I attended the planning meeting"},
        )

        request = backend.store.call_args.args[1]
        assert request.category == MemoryCategory.EPISODIC

    async def test_execute_returns_stored_id(self) -> None:
        backend = _make_backend(store_return="episodic-id-99")
        strategy = _make_strategy(backend=backend)
        tool = RecallMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "completed task on 2026-04-07"},
        )

        assert not result.is_error
        assert "episodic-id-99" in result.content

    async def test_execute_auto_tags_self_edited(self) -> None:
        backend = _make_backend()
        config = _make_config(write_auto_tag=True)
        strategy = _make_strategy(backend=backend, config=config)
        tool = RecallMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        await tool.execute(arguments={"content": "attended sprint review"})

        request = backend.store.call_args.args[1]
        assert "self_edited" in request.metadata.tags

    async def test_execute_blank_content_returns_error(self) -> None:
        strategy = _make_strategy()
        tool = RecallMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(arguments={"content": ""})

        assert result.is_error

    async def test_execute_oversized_content_returns_error(self) -> None:
        backend = _make_backend()
        strategy = _make_strategy(backend=backend)
        tool = RecallMemoryWriteTool(strategy=strategy, agent_id="agent-1")

        result = await tool.execute(
            arguments={"content": "z" * (_MAX_CONTENT_LEN + 1)},
        )

        assert result.is_error
        assert not backend.store.called


# ---------------------------------------------------------------------------
# TestRegistryWithSelfEditingTools
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegistryWithSelfEditingTools:
    def test_registry_augmented_with_six_tools(self) -> None:
        base_registry = _make_empty_registry()
        strategy = _make_strategy()

        augmented = registry_with_memory_tools(
            base_registry, strategy, agent_id="agent-1"
        )

        assert len(augmented) == 6
        assert CORE_MEMORY_READ_TOOL in augmented
        assert CORE_MEMORY_WRITE_TOOL in augmented
        assert ARCHIVAL_MEMORY_SEARCH_TOOL in augmented
        assert ARCHIVAL_MEMORY_WRITE_TOOL in augmented
        assert RECALL_MEMORY_READ_TOOL in augmented
        assert RECALL_MEMORY_WRITE_TOOL in augmented

    def test_registry_preserves_existing_tools(self) -> None:
        base_registry = ToolRegistry([_DummyTool("pre_existing")])
        strategy = _make_strategy()

        augmented = registry_with_memory_tools(
            base_registry, strategy, agent_id="agent-1"
        )

        assert "pre_existing" in augmented
        assert CORE_MEMORY_READ_TOOL in augmented
        assert len(augmented) == 7

    def test_none_strategy_returns_original_registry(self) -> None:
        base_registry = ToolRegistry([_DummyTool()])

        result = registry_with_memory_tools(base_registry, None, agent_id="agent-1")

        assert result is base_registry

    def test_tool_based_strategy_still_adds_two_tools(self) -> None:
        """Regression: ToolBasedInjectionStrategy path must still add 2 tools."""
        from synthorg.memory.retrieval_config import MemoryRetrievalConfig

        tool_strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=MemoryRetrievalConfig(
                strategy=InjectionStrategy.TOOL_BASED,
                min_relevance=0.0,
            ),
        )
        base_registry = _make_empty_registry()

        augmented = registry_with_memory_tools(
            base_registry, tool_strategy, agent_id="agent-1"
        )

        assert len(augmented) == 2
        assert "search_memory" in augmented
        assert "recall_memory" in augmented

    def test_self_editing_generic_exception_falls_back_to_original(self) -> None:
        """Generic exception in _build_self_editing_registry falls back."""
        base_registry = ToolRegistry([_DummyTool()])
        strategy = _make_strategy()

        with patch(
            "synthorg.memory.tools._build_self_editing_registry",
            side_effect=RuntimeError("build failed"),
        ):
            result = registry_with_memory_tools(
                base_registry, strategy, agent_id="agent-1"
            )

        assert result is base_registry

    def test_tool_based_generic_exception_falls_back_to_original(self) -> None:
        """Generic exception in _build_augmented_registry returns original registry."""
        from synthorg.memory.retrieval_config import MemoryRetrievalConfig

        tool_strategy = ToolBasedInjectionStrategy(
            backend=_make_backend(),
            config=MemoryRetrievalConfig(
                strategy=InjectionStrategy.TOOL_BASED,
                min_relevance=0.0,
            ),
        )
        base_registry = ToolRegistry([_DummyTool()])

        with patch(
            "synthorg.memory.tools._build_augmented_registry",
            side_effect=RuntimeError("build failed"),
        ):
            result = registry_with_memory_tools(
                base_registry, tool_strategy, agent_id="agent-1"
            )

        assert result is base_registry


# ---------------------------------------------------------------------------
# TestCreateSelfEditingTools
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateSelfEditingTools:
    def test_returns_six_tools(self) -> None:
        strategy = _make_strategy()
        tools = create_self_editing_tools(strategy=strategy, agent_id="agent-1")

        assert len(tools) == 6

    def test_all_tools_are_base_tool_instances(self) -> None:
        strategy = _make_strategy()
        for tool in create_self_editing_tools(strategy=strategy, agent_id="agent-1"):
            assert isinstance(tool, BaseTool)

    def test_all_tools_have_memory_category(self) -> None:
        strategy = _make_strategy()
        for tool in create_self_editing_tools(strategy=strategy, agent_id="agent-1"):
            assert tool.category == ToolCategory.MEMORY

    def test_tool_names_match_constants(self) -> None:
        strategy = _make_strategy()
        names = {
            t.name
            for t in create_self_editing_tools(strategy=strategy, agent_id="agent-1")
        }

        assert names == {
            CORE_MEMORY_READ_TOOL,
            CORE_MEMORY_WRITE_TOOL,
            ARCHIVAL_MEMORY_SEARCH_TOOL,
            ARCHIVAL_MEMORY_WRITE_TOOL,
            RECALL_MEMORY_READ_TOOL,
            RECALL_MEMORY_WRITE_TOOL,
        }

    async def test_agent_id_bound_to_tools(self) -> None:
        """Tools use the agent_id they were created with."""
        backend = _make_backend()
        strategy = _make_strategy(backend=backend)
        tools = create_self_editing_tools(strategy=strategy, agent_id="agent-77")
        read_tool = next(t for t in tools if t.name == CORE_MEMORY_READ_TOOL)

        await read_tool.execute(arguments={})

        assert backend.retrieve.call_args.args[0] == "agent-77"


# ---------------------------------------------------------------------------
# TestHandleToolCallDispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleToolCallDispatch:
    async def test_unknown_tool_name_returns_error_string(self) -> None:
        """Unknown tool names must return an error string, not raise."""
        strategy = _make_strategy()

        result = await strategy.handle_tool_call("no_such_tool", {}, "agent-1")

        assert result.startswith("Error:")

    async def test_memory_error_is_reraised(self) -> None:
        """MemoryError from a handler must propagate through handle_tool_call."""
        backend = _make_backend()
        backend.retrieve = AsyncMock(side_effect=MemoryError("out of memory"))
        strategy = _make_strategy(backend=backend)

        with pytest.raises(MemoryError):
            await strategy.handle_tool_call(CORE_MEMORY_READ_TOOL, {}, "agent-1")

    async def test_recursion_error_is_reraised(self) -> None:
        """RecursionError from a handler must propagate through handle_tool_call."""
        backend = _make_backend()
        backend.retrieve = AsyncMock(side_effect=RecursionError("max recursion"))
        strategy = _make_strategy(backend=backend)

        with pytest.raises(RecursionError):
            await strategy.handle_tool_call(CORE_MEMORY_READ_TOOL, {}, "agent-1")

    async def test_generic_exception_returns_error_prefix(self) -> None:
        """Generic exceptions from handlers must be caught and returned as errors."""
        backend = _make_backend()
        backend.retrieve = AsyncMock(side_effect=RuntimeError("backend exploded"))
        strategy = _make_strategy(backend=backend)

        result = await strategy.handle_tool_call(CORE_MEMORY_READ_TOOL, {}, "agent-1")

        assert result.startswith("Error:")
        assert "Memory operation failed." in result

    async def test_generic_exception_does_not_expose_backend_details(self) -> None:
        """Error message must not leak the original exception text to the LLM."""
        backend = _make_backend()
        backend.retrieve = AsyncMock(
            side_effect=RuntimeError("SQLite UNIQUE constraint failed: entries.id")
        )
        strategy = _make_strategy(backend=backend)

        result = await strategy.handle_tool_call(CORE_MEMORY_READ_TOOL, {}, "agent-1")

        assert "SQLite" not in result
        assert "UNIQUE constraint" not in result


# ---------------------------------------------------------------------------
# TestExtractStr
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractStr:
    @pytest.mark.parametrize(
        "value",
        [42, None, {}, [], 3.14, True],
    )
    def test_non_string_value_returns_none(self, value: object) -> None:
        """_extract_str must return None for any non-string value."""
        result = _extract_str({"key": value}, "key")
        assert result is None

    def test_blank_string_returns_none(self) -> None:
        result = _extract_str({"key": "   "}, "key")
        assert result is None

    def test_missing_key_returns_none(self) -> None:
        result = _extract_str({}, "key")
        assert result is None

    def test_valid_string_is_stripped(self) -> None:
        result = _extract_str({"key": "  hello world  "}, "key")
        assert result == "hello world"

    def test_non_blank_string_returned_as_is_after_strip(self) -> None:
        result = _extract_str({"key": "no whitespace"}, "key")
        assert result == "no whitespace"
