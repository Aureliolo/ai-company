"""Memory tool wrappers for ToolRegistry integration.

Provides ``SearchMemoryTool`` and ``RecallMemoryTool`` for
``ToolBasedInjectionStrategy``, six self-editing tools
(``CoreMemoryReadTool``, ``CoreMemoryWriteTool``,
``ArchivalMemorySearchTool``, ``ArchivalMemoryWriteTool``,
``RecallMemoryReadTool``, ``RecallMemoryWriteTool``) for
``SelfEditingMemoryStrategy``, and six ``KnowledgeArchitect*Tool``
classes for the Knowledge Architect role.

All tool classes are thin ``BaseTool`` subclasses that delegate
execution to ``strategy.handle_tool_call()``, bridging the memory
injection system into the standard tool dispatch pipeline
(``ToolInvoker`` -> ``ToolRegistry`` -> ``BaseTool.execute``).
"""

from typing import TYPE_CHECKING, Any

from synthorg.core.enums import (
    AutonomyLevel,
    OrgFactCategory,
    SeniorityLevel,
    ToolCategory,
)
from synthorg.memory.org.models import (
    OrgFactAuthor,
    OrgFactWriteRequest,
    OrgMemoryQuery,
)
from synthorg.memory.self_editing import (
    _ARCHIVAL_MEMORY_SEARCH_SCHEMA,
    _ARCHIVAL_MEMORY_WRITE_SCHEMA,
    _CORE_MEMORY_READ_SCHEMA,
    _CORE_MEMORY_WRITE_SCHEMA,
    _RECALL_MEMORY_READ_SCHEMA,
    _RECALL_MEMORY_WRITE_SCHEMA,
    ARCHIVAL_MEMORY_SEARCH_TOOL,
    ARCHIVAL_MEMORY_WRITE_TOOL,
    CORE_MEMORY_READ_TOOL,
    CORE_MEMORY_WRITE_TOOL,
    RECALL_MEMORY_READ_TOOL,
    RECALL_MEMORY_WRITE_TOOL,
    SelfEditingMemoryStrategy,
)
from synthorg.memory.tool_retriever import (
    ERROR_PREFIX,
    RECALL_MEMORY_SCHEMA,
    RECALL_MEMORY_TOOL_NAME,
    SEARCH_MEMORY_SCHEMA,
    SEARCH_MEMORY_TOOL_NAME,
    ToolBasedInjectionStrategy,
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    KNOWLEDGE_ARCHITECT_DELETE,
    KNOWLEDGE_ARCHITECT_WRITE,
    KNOWLEDGE_ARCHITECT_WRITE_DENIED,
)
from synthorg.observability.events.tool import (
    TOOL_FACTORY_BUILT,
    TOOL_MEMORY_AUGMENTATION_FAILED,
    TOOL_REGISTRY_BUILT,
)
from synthorg.tools.base import BaseTool, ToolExecutionResult

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.memory.consolidation.wiki_export import WikiExporter
    from synthorg.memory.injection import MemoryInjectionStrategy
    from synthorg.memory.org.protocol import OrgMemoryBackend
    from synthorg.memory.org.store import OrgFactStore
    from synthorg.tools.registry import ToolRegistry

logger = get_logger(__name__)


def _is_error_response(text: str) -> bool:
    """Check whether the strategy response indicates an error.

    All user-facing error return values in ``tool_retriever`` are
    prefixed with :data:`ERROR_PREFIX` (the single source of truth), so
    a direct ``startswith`` check is both sufficient and cheaper than
    iterating a redundant tuple of specific prefixes.
    """
    return text.startswith(ERROR_PREFIX)


class SearchMemoryTool(BaseTool):
    """``search_memory`` tool for ToolRegistry integration.

    Delegates execution to ``ToolBasedInjectionStrategy.handle_tool_call``,
    wrapping the string result in a ``ToolExecutionResult``.  The
    ``agent_id`` is bound at construction time (tools are per-agent).

    Args:
        strategy: The tool-based injection strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    def __init__(
        self,
        *,
        strategy: ToolBasedInjectionStrategy,
        agent_id: NotBlankStr,
    ) -> None:
        # dict() converts MappingProxyType (not deepcopy-able) to a
        # plain dict; BaseTool.__init__ handles the defensive deepcopy.
        super().__init__(
            name=SEARCH_MEMORY_TOOL_NAME,
            description=(
                "Search agent memory for relevant past context, "
                "decisions, or learned information."
            ),
            parameters_schema=dict(SEARCH_MEMORY_SCHEMA),
            category=ToolCategory.MEMORY,
        )
        self._strategy = strategy
        self._agent_id = agent_id

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a memory search via the injection strategy.

        Args:
            arguments: Tool arguments from the LLM, validated
                against ``SEARCH_MEMORY_SCHEMA``.

        Returns:
            ``ToolExecutionResult`` with formatted memory entries or error.
        """
        result = await self._strategy.handle_tool_call(
            SEARCH_MEMORY_TOOL_NAME,
            arguments,
            self._agent_id,
        )
        return ToolExecutionResult(
            content=result,
            is_error=_is_error_response(result),
        )


class RecallMemoryTool(BaseTool):
    """``recall_memory`` tool for ToolRegistry integration.

    Delegates execution to ``ToolBasedInjectionStrategy.handle_tool_call``,
    wrapping the string result in a ``ToolExecutionResult``.  The
    ``agent_id`` is bound at construction time (tools are per-agent).

    Args:
        strategy: The tool-based injection strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    def __init__(
        self,
        *,
        strategy: ToolBasedInjectionStrategy,
        agent_id: NotBlankStr,
    ) -> None:
        # dict() converts MappingProxyType (not deepcopy-able) to a
        # plain dict; BaseTool.__init__ handles the defensive deepcopy.
        super().__init__(
            name=RECALL_MEMORY_TOOL_NAME,
            description="Recall a specific memory entry by its ID.",
            parameters_schema=dict(RECALL_MEMORY_SCHEMA),
            category=ToolCategory.MEMORY,
        )
        self._strategy = strategy
        self._agent_id = agent_id

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a memory recall by ID via the injection strategy.

        Args:
            arguments: Tool arguments from the LLM (memory_id).

        Returns:
            ``ToolExecutionResult`` with the memory entry or error.
        """
        result = await self._strategy.handle_tool_call(
            RECALL_MEMORY_TOOL_NAME,
            arguments,
            self._agent_id,
        )
        return ToolExecutionResult(
            content=result,
            is_error=_is_error_response(result),
        )


class CoreMemoryReadTool(BaseTool):
    """``core_memory_read`` tool for ToolRegistry integration.

    Args:
        strategy: Self-editing strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    def __init__(
        self,
        *,
        strategy: SelfEditingMemoryStrategy,
        agent_id: NotBlankStr,
    ) -> None:
        super().__init__(
            name=CORE_MEMORY_READ_TOOL,
            description=(
                "Read the current core memory block (persona, goals, "
                "key knowledge stored as SEMANTIC memories)."
            ),
            parameters_schema=dict(_CORE_MEMORY_READ_SCHEMA),
            category=ToolCategory.MEMORY,
        )
        self._strategy = strategy
        self._agent_id = agent_id

    async def execute(self, *, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Execute a core memory read via the self-editing strategy.

        Args:
            arguments: Tool arguments from the LLM.

        Returns:
            ``ToolExecutionResult`` with formatted core entries or error.
        """
        result = await self._strategy.handle_tool_call(
            CORE_MEMORY_READ_TOOL, arguments, self._agent_id
        )
        return ToolExecutionResult(content=result, is_error=_is_error_response(result))


class CoreMemoryWriteTool(BaseTool):
    """``core_memory_write`` tool for ToolRegistry integration.

    Args:
        strategy: Self-editing strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    def __init__(
        self,
        *,
        strategy: SelfEditingMemoryStrategy,
        agent_id: NotBlankStr,
    ) -> None:
        super().__init__(
            name=CORE_MEMORY_WRITE_TOOL,
            description=(
                "Append an entry to core memory.  Core memory persists "
                "across sessions and is always injected into context."
            ),
            parameters_schema=dict(_CORE_MEMORY_WRITE_SCHEMA),
            category=ToolCategory.MEMORY,
        )
        self._strategy = strategy
        self._agent_id = agent_id

    async def execute(self, *, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Execute a core memory write via the self-editing strategy.

        Args:
            arguments: Tool arguments from the LLM (content).

        Returns:
            ``ToolExecutionResult`` with confirmation or error.
        """
        result = await self._strategy.handle_tool_call(
            CORE_MEMORY_WRITE_TOOL, arguments, self._agent_id
        )
        return ToolExecutionResult(content=result, is_error=_is_error_response(result))


class ArchivalMemorySearchTool(BaseTool):
    """``archival_memory_search`` tool for ToolRegistry integration.

    Args:
        strategy: Self-editing strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    def __init__(
        self,
        *,
        strategy: SelfEditingMemoryStrategy,
        agent_id: NotBlankStr,
    ) -> None:
        super().__init__(
            name=ARCHIVAL_MEMORY_SEARCH_TOOL,
            description=(
                "Search archival memory by natural language query.  "
                "Archival memory is never auto-injected; use this tool "
                "to retrieve relevant past context on demand."
            ),
            parameters_schema=dict(_ARCHIVAL_MEMORY_SEARCH_SCHEMA),
            category=ToolCategory.MEMORY,
        )
        self._strategy = strategy
        self._agent_id = agent_id

    async def execute(self, *, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Execute an archival memory search via the self-editing strategy.

        Args:
            arguments: Tool arguments from the LLM (query, category, limit).

        Returns:
            ``ToolExecutionResult`` with formatted entries or error.
        """
        result = await self._strategy.handle_tool_call(
            ARCHIVAL_MEMORY_SEARCH_TOOL, arguments, self._agent_id
        )
        return ToolExecutionResult(content=result, is_error=_is_error_response(result))


class ArchivalMemoryWriteTool(BaseTool):
    """``archival_memory_write`` tool for ToolRegistry integration.

    Args:
        strategy: Self-editing strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    def __init__(
        self,
        *,
        strategy: SelfEditingMemoryStrategy,
        agent_id: NotBlankStr,
    ) -> None:
        super().__init__(
            name=ARCHIVAL_MEMORY_WRITE_TOOL,
            description=(
                "Store a new entry in archival memory.  Use for facts, "
                "decisions, or events to retain for future retrieval."
            ),
            parameters_schema=dict(_ARCHIVAL_MEMORY_WRITE_SCHEMA),
            category=ToolCategory.MEMORY,
        )
        self._strategy = strategy
        self._agent_id = agent_id

    async def execute(self, *, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Execute an archival memory write via the self-editing strategy.

        Args:
            arguments: Tool arguments from the LLM (content, category).

        Returns:
            ``ToolExecutionResult`` with confirmation or error.
        """
        result = await self._strategy.handle_tool_call(
            ARCHIVAL_MEMORY_WRITE_TOOL, arguments, self._agent_id
        )
        return ToolExecutionResult(content=result, is_error=_is_error_response(result))


class RecallMemoryReadTool(BaseTool):
    """``recall_memory_read`` tool for ToolRegistry integration.

    Args:
        strategy: Self-editing strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    def __init__(
        self,
        *,
        strategy: SelfEditingMemoryStrategy,
        agent_id: NotBlankStr,
    ) -> None:
        super().__init__(
            name=RECALL_MEMORY_READ_TOOL,
            description=(
                "Retrieve a specific episodic memory by its ID.  "
                "Use the ID returned by recall_memory_write."
            ),
            parameters_schema=dict(_RECALL_MEMORY_READ_SCHEMA),
            category=ToolCategory.MEMORY,
        )
        self._strategy = strategy
        self._agent_id = agent_id

    async def execute(self, *, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Execute a recall memory read via the self-editing strategy.

        Args:
            arguments: Tool arguments from the LLM (memory_id).

        Returns:
            ``ToolExecutionResult`` with the entry or error.
        """
        result = await self._strategy.handle_tool_call(
            RECALL_MEMORY_READ_TOOL, arguments, self._agent_id
        )
        return ToolExecutionResult(content=result, is_error=_is_error_response(result))


class RecallMemoryWriteTool(BaseTool):
    """``recall_memory_write`` tool for ToolRegistry integration.

    Args:
        strategy: Self-editing strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    def __init__(
        self,
        *,
        strategy: SelfEditingMemoryStrategy,
        agent_id: NotBlankStr,
    ) -> None:
        super().__init__(
            name=RECALL_MEMORY_WRITE_TOOL,
            description=(
                "Record an episodic event or experience.  Returns the "
                "memory ID for future retrieval via recall_memory_read."
            ),
            parameters_schema=dict(_RECALL_MEMORY_WRITE_SCHEMA),
            category=ToolCategory.MEMORY,
        )
        self._strategy = strategy
        self._agent_id = agent_id

    async def execute(self, *, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Execute a recall memory write via the self-editing strategy.

        Args:
            arguments: Tool arguments from the LLM (content).

        Returns:
            ``ToolExecutionResult`` with the new memory ID or error.
        """
        result = await self._strategy.handle_tool_call(
            RECALL_MEMORY_WRITE_TOOL, arguments, self._agent_id
        )
        return ToolExecutionResult(content=result, is_error=_is_error_response(result))


def create_self_editing_tools(
    *,
    strategy: SelfEditingMemoryStrategy,
    agent_id: NotBlankStr,
) -> tuple[BaseTool, ...]:
    """Create self-editing memory tools for a specific agent.

    Returns all six self-editing tools bound to the given ``agent_id``
    and sharing the provided strategy instance.

    Args:
        strategy: Self-editing memory strategy with backend access.
        agent_id: Agent ID to bind to the tools.

    Returns:
        Tuple of six ``BaseTool`` instances.
    """
    tools = (
        CoreMemoryReadTool(strategy=strategy, agent_id=agent_id),
        CoreMemoryWriteTool(strategy=strategy, agent_id=agent_id),
        ArchivalMemorySearchTool(strategy=strategy, agent_id=agent_id),
        ArchivalMemoryWriteTool(strategy=strategy, agent_id=agent_id),
        RecallMemoryReadTool(strategy=strategy, agent_id=agent_id),
        RecallMemoryWriteTool(strategy=strategy, agent_id=agent_id),
    )
    logger.debug(
        TOOL_FACTORY_BUILT,
        agent_id=agent_id,
        tools=[t.name for t in tools],
    )
    return tools


def create_memory_tools(
    *,
    strategy: ToolBasedInjectionStrategy,
    agent_id: NotBlankStr,
) -> tuple[BaseTool, ...]:
    """Create memory tools for a specific agent.

    Returns ``SearchMemoryTool`` and ``RecallMemoryTool`` bound to the
    given ``agent_id`` and sharing the provided strategy instance.

    Args:
        strategy: Tool-based injection strategy with backend access.
        agent_id: Agent ID to bind to the tools.

    Returns:
        Tuple of two ``BaseTool`` instances (search and recall).
    """
    tools = (
        SearchMemoryTool(strategy=strategy, agent_id=agent_id),
        RecallMemoryTool(strategy=strategy, agent_id=agent_id),
    )
    logger.debug(
        TOOL_FACTORY_BUILT,
        agent_id=agent_id,
        tools=[t.name for t in tools],
    )
    return tools


def _build_augmented_registry(
    tool_registry: ToolRegistry,
    strategy: ToolBasedInjectionStrategy,
    agent_id: NotBlankStr,
) -> ToolRegistry:
    """Construct a new registry with memory tools appended."""
    from synthorg.tools.registry import (  # noqa: PLC0415
        ToolRegistry as _ToolRegistry,
    )

    memory_tools = create_memory_tools(
        strategy=strategy,
        agent_id=agent_id,
    )
    existing = list(tool_registry.all_tools())
    return _ToolRegistry([*existing, *memory_tools])


def _build_self_editing_registry(
    tool_registry: ToolRegistry,
    strategy: SelfEditingMemoryStrategy,
    agent_id: NotBlankStr,
) -> ToolRegistry:
    """Construct a new registry with self-editing tools appended."""
    from synthorg.tools.registry import (  # noqa: PLC0415
        ToolRegistry as _ToolRegistry,
    )

    self_editing_tools = create_self_editing_tools(
        strategy=strategy,
        agent_id=agent_id,
    )
    existing = list(tool_registry.all_tools())
    return _ToolRegistry([*existing, *self_editing_tools])


def registry_with_memory_tools(
    tool_registry: ToolRegistry,
    strategy: MemoryInjectionStrategy | None,
    agent_id: NotBlankStr,
) -> ToolRegistry:
    """Build a registry with memory tools added if applicable.

    Returns the original registry unchanged when the strategy is
    ``None`` or is not a memory tool strategy.  Handles both
    ``ToolBasedInjectionStrategy`` (adds 2 tools) and
    ``SelfEditingMemoryStrategy`` (adds 6 tools).  Follows the
    ``registry_with_approval_tool`` pattern in
    ``engine/_security_factory.py``.

    Args:
        tool_registry: Base tool registry.
        strategy: Memory injection strategy (may be any type or None).
        agent_id: Agent ID to bind to the memory tools.

    Returns:
        Augmented registry with memory tools, or original if not
        applicable.
    """
    if isinstance(strategy, SelfEditingMemoryStrategy):
        try:
            augmented = _build_self_editing_registry(tool_registry, strategy, agent_id)
        except MemoryError, RecursionError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            logger.warning(
                TOOL_MEMORY_AUGMENTATION_FAILED,
                source="registry_augmentation",
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return tool_registry
        logger.debug(
            TOOL_REGISTRY_BUILT,
            tool_count=len(augmented),
            tools=augmented.list_tools(),
        )
        return augmented

    if not isinstance(strategy, ToolBasedInjectionStrategy):
        return tool_registry

    try:
        augmented = _build_augmented_registry(
            tool_registry,
            strategy,
            agent_id,
        )
    except MemoryError, RecursionError:
        raise
    except ValueError:
        # Configuration errors (duplicate names, reserved collisions)
        # are programming bugs -- let them propagate.
        raise
    except Exception as exc:
        logger.warning(
            TOOL_MEMORY_AUGMENTATION_FAILED,
            source="registry_augmentation",
            agent_id=agent_id,
            error=str(exc),
            exc_info=True,
        )
        return tool_registry

    logger.debug(
        TOOL_REGISTRY_BUILT,
        tool_count=len(augmented),
        tools=augmented.list_tools(),
    )
    return augmented


# ── Knowledge Architect Tools ─────────────────────────────────────

_GUIDE_TEXT = (
    "Knowledge Architect Memory Tools:\n"
    "- memory.guide: This help text\n"
    "- memory.search: Search org memory by query + category\n"
    "- memory.read: Read a specific entry by ID\n"
    "- memory.write: Create/update extended knowledge (ADRs, "
    "procedures, style guides)\n"
    "- memory.delete: Archive an entry (soft delete via MVCC)\n"
    "- memory.browse_wiki: Export and browse memory as wiki\n\n"
    "Core policy writes always require human approval."
)


class KnowledgeArchitectGuideTool(BaseTool):
    """``memory.guide`` -- returns mechanics doc for the architect."""

    def __init__(self) -> None:
        super().__init__(
            name="memory.guide",
            description="Returns memory tools guide for the architect",
            parameters_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            category=ToolCategory.MEMORY,
        )

    async def execute(
        self,
        *,
        arguments: dict[str, Any],  # noqa: ARG002
    ) -> ToolExecutionResult:
        """Return the mechanics guide."""
        return ToolExecutionResult(content=_GUIDE_TEXT, is_error=False)


class KnowledgeArchitectSearchTool(BaseTool):
    """``memory.search`` -- search org memory."""

    def __init__(
        self,
        *,
        org_backend: OrgMemoryBackend,
    ) -> None:
        super().__init__(
            name="memory.search",
            description="Search organizational memory",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            category=ToolCategory.MEMORY,
        )
        self._org_backend = org_backend

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute org memory search."""
        try:
            category_str = arguments.get("category")
            categories = None
            if category_str:
                try:
                    categories = frozenset({OrgFactCategory(category_str)})
                except ValueError:
                    return ToolExecutionResult(
                        content=f"Invalid category: {category_str!r}",
                        is_error=True,
                    )
            query = OrgMemoryQuery(
                context=arguments["query"],
                limit=arguments.get("limit", 10),
                categories=categories,
            )
            facts = await self._org_backend.query(query)
        except Exception as exc:
            return ToolExecutionResult(
                content=f"Search failed: {exc}",
                is_error=True,
            )
        if not facts:
            return ToolExecutionResult(
                content="No results found.",
                is_error=False,
            )
        lines = [f"[{f.id}] ({f.category.value}) {f.content}" for f in facts]
        return ToolExecutionResult(
            content="\n".join(lines),
            is_error=False,
        )


class KnowledgeArchitectReadTool(BaseTool):
    """``memory.read`` -- read a specific org memory entry."""

    def __init__(
        self,
        *,
        org_backend: OrgMemoryBackend,
    ) -> None:
        super().__init__(
            name="memory.read",
            description="Read a specific organizational memory entry",
            parameters_schema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                },
                "required": ["entry_id"],
                "additionalProperties": False,
            },
            category=ToolCategory.MEMORY,
        )
        self._org_backend = org_backend

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Read an org memory entry by ID."""
        entry_id = arguments["entry_id"]
        try:
            query = OrgMemoryQuery(
                context=entry_id,
                limit=100,
            )
            facts = await self._org_backend.query(query)
            match = next(
                (f for f in facts if f.id == entry_id),
                None,
            )
        except Exception as exc:
            return ToolExecutionResult(
                content=f"Read failed: {exc}",
                is_error=True,
            )
        if match is None:
            return ToolExecutionResult(
                content=f"Entry {entry_id!r} not found.",
                is_error=True,
            )
        return ToolExecutionResult(
            content=(
                f"ID: {match.id}\n"
                f"Category: {match.category.value}\n"
                f"Content: {match.content}"
            ),
            is_error=False,
        )


class KnowledgeArchitectWriteTool(BaseTool):
    """``memory.write`` -- write to org memory with autonomy gating."""

    def __init__(
        self,
        *,
        org_backend: OrgMemoryBackend,
        agent_id: NotBlankStr,
        autonomy_level: AutonomyLevel,
    ) -> None:
        super().__init__(
            name="memory.write",
            description="Write to organizational memory",
            parameters_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "maxLength": 100000,
                    },
                    "category": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 50,
                    },
                },
                "required": ["content", "category"],
                "additionalProperties": False,
            },
            category=ToolCategory.MEMORY,
        )
        self._org_backend = org_backend
        self._agent_id = agent_id
        self._autonomy_level = autonomy_level

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Write to org memory with autonomy gating.

        Gated by autonomy level: FULL autonomy disables writes.
        SUPERVISED and LOCKED levels allow writes (plan review gate
        handles approval upstream).
        """
        if self._autonomy_level == AutonomyLevel.FULL:
            logger.warning(
                KNOWLEDGE_ARCHITECT_WRITE_DENIED,
                agent_id=self._agent_id,
                autonomy=self._autonomy_level.value,
                reason="FULL autonomy disables architect writes",
            )
            return ToolExecutionResult(
                content=(
                    "Write denied: FULL autonomy level "
                    "disables architect writes to org memory"
                ),
                is_error=True,
            )

        try:
            category_str = arguments["category"]
            try:
                OrgFactCategory(category_str)
            except ValueError:
                return ToolExecutionResult(
                    content=f"Invalid category: {category_str!r}",
                    is_error=True,
                )
            request = OrgFactWriteRequest(
                content=arguments["content"],
                category=category_str,
                tags=tuple(arguments.get("tags", ())),
            )
            author = OrgFactAuthor(
                agent_id=self._agent_id,
                seniority=SeniorityLevel.SENIOR,
                is_human=False,
                autonomy_level=self._autonomy_level,
            )
            fact_id = await self._org_backend.write(
                request,
                author=author,
            )
        except Exception as exc:
            return ToolExecutionResult(
                content=f"Write failed: {exc}",
                is_error=True,
            )
        logger.info(
            KNOWLEDGE_ARCHITECT_WRITE,
            agent_id=self._agent_id,
            entry_id=fact_id,
            category=arguments["category"],
            autonomy=self._autonomy_level.value,
        )
        return ToolExecutionResult(
            content=f"Written: {fact_id}",
            is_error=False,
        )


class KnowledgeArchitectDeleteTool(BaseTool):
    """``memory.delete`` -- archive an org memory entry."""

    def __init__(
        self,
        *,
        org_backend: OrgMemoryBackend,
        fact_store: OrgFactStore | None = None,
        agent_id: NotBlankStr,
        autonomy_level: AutonomyLevel,
    ) -> None:
        super().__init__(
            name="memory.delete",
            description="Archive an organizational memory entry",
            parameters_schema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                },
                "required": ["entry_id"],
                "additionalProperties": False,
            },
            category=ToolCategory.MEMORY,
        )
        self._org_backend = org_backend
        self._fact_store = fact_store
        self._agent_id = agent_id
        self._autonomy_level = autonomy_level

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Delete (archive) an org memory entry.

        Gated by autonomy level: FULL autonomy disables deletes.
        Requires ``fact_store`` to perform the actual retraction.
        """
        if self._autonomy_level == AutonomyLevel.FULL:
            logger.warning(
                KNOWLEDGE_ARCHITECT_WRITE_DENIED,
                agent_id=self._agent_id,
                autonomy=self._autonomy_level.value,
                reason="FULL autonomy disables architect deletes",
            )
            return ToolExecutionResult(
                content="Delete denied: FULL autonomy level",
                is_error=True,
            )
        if self._fact_store is None:
            return ToolExecutionResult(
                content="Delete not available: fact store not configured",
                is_error=True,
            )
        entry_id = arguments["entry_id"]
        try:
            author = OrgFactAuthor(
                agent_id=self._agent_id,
                seniority=SeniorityLevel.SENIOR,
                is_human=False,
            )
            deleted = await self._fact_store.delete(
                fact_id=entry_id,
                author=author,
            )
        except Exception as exc:
            logger.warning(
                KNOWLEDGE_ARCHITECT_DELETE,
                agent_id=self._agent_id,
                entry_id=entry_id,
                error=str(exc),
            )
            return ToolExecutionResult(
                content=f"Delete failed: {exc}",
                is_error=True,
            )
        if not deleted:
            return ToolExecutionResult(
                content=f"Entry {entry_id!r} not found or already archived.",
                is_error=True,
            )
        logger.info(
            KNOWLEDGE_ARCHITECT_DELETE,
            agent_id=self._agent_id,
            entry_id=entry_id,
            autonomy=self._autonomy_level.value,
        )
        return ToolExecutionResult(
            content=f"Archived: {entry_id}",
            is_error=False,
        )


class KnowledgeArchitectBrowseWikiTool(BaseTool):
    """``memory.browse_wiki`` -- export and browse wiki."""

    def __init__(
        self,
        *,
        wiki_exporter: WikiExporter | None = None,
        agent_id: NotBlankStr,
    ) -> None:
        super().__init__(
            name="memory.browse_wiki",
            description="Export and browse memory as wiki",
            parameters_schema={
                "type": "object",
                "properties": {
                    "include_raw": {
                        "type": "boolean",
                        "default": False,
                    },
                },
                "additionalProperties": False,
            },
            category=ToolCategory.MEMORY,
        )
        self._wiki_exporter = wiki_exporter
        self._agent_id = agent_id

    async def execute(
        self,
        *,
        arguments: dict[str, Any],  # noqa: ARG002
    ) -> ToolExecutionResult:
        """Trigger wiki export and return summary."""
        if self._wiki_exporter is None:
            return ToolExecutionResult(
                content="Wiki export is not configured.",
                is_error=True,
            )
        try:
            result = await self._wiki_exporter.export(self._agent_id)
        except Exception as exc:
            return ToolExecutionResult(
                content=f"Wiki export failed: {exc}",
                is_error=True,
            )
        return ToolExecutionResult(
            content=(
                f"Wiki exported:\n"
                f"- Raw entries: {result.raw_count}\n"
                f"- Compressed entries: {result.compressed_count}\n"
                f"- Location: {result.export_root}"
            ),
            is_error=False,
        )
