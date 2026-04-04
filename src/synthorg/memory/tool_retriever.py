"""Tool-based memory injection strategy.

Provides ``search_memory`` and ``recall_memory`` tool definitions
that agents invoke on-demand during execution.  Implements the
``MemoryInjectionStrategy`` protocol with tool-based retrieval.
"""

import builtins
import copy
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from synthorg.core.enums import MemoryCategory
from synthorg.core.types import NotBlankStr
from synthorg.memory.errors import MemoryError as DomainMemoryError
from synthorg.memory.models import MemoryEntry, MemoryQuery
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_REFORMULATION_ROUND,
    MEMORY_REFORMULATION_SUFFICIENT,
    MEMORY_RETRIEVAL_COMPLETE,
    MEMORY_RETRIEVAL_DEGRADED,
    MEMORY_RETRIEVAL_START,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage, ToolDefinition

if TYPE_CHECKING:
    from synthorg.memory.protocol import MemoryBackend
    from synthorg.memory.reformulation import (
        QueryReformulator,
        SufficiencyChecker,
    )
    from synthorg.memory.retrieval_config import MemoryRetrievalConfig

logger = get_logger(__name__)

SEARCH_MEMORY_TOOL_NAME = "search_memory"
RECALL_MEMORY_TOOL_NAME = "recall_memory"

# Error message constants -- imported by memory/tools.py for error detection.
ERROR_PREFIX = "Error:"
SEARCH_UNAVAILABLE = "Memory search is temporarily unavailable."
SEARCH_UNEXPECTED = "Memory search encountered an unexpected error."
RECALL_UNAVAILABLE = "Memory recall is temporarily unavailable."
RECALL_UNEXPECTED = "Memory recall encountered an unexpected error."
RECALL_NOT_FOUND_PREFIX = "Memory not found:"

_INSTRUCTION = (
    "You have access to memory recall tools. Use search_memory "
    "when you need to recall past context, decisions, or learned "
    "information. Use recall_memory to fetch a specific memory by ID."
)

SEARCH_MEMORY_SCHEMA: Final[MappingProxyType[str, Any]] = MappingProxyType(
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query.",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional category filter "
                    "(working, episodic, semantic, procedural, social)."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default 10).",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["query"],
    }
)

_MAX_MEMORY_ID_LEN: Final[int] = 256

RECALL_MEMORY_SCHEMA: Final[MappingProxyType[str, Any]] = MappingProxyType(
    {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "Exact memory ID to recall.",
                "maxLength": _MAX_MEMORY_ID_LEN,
            },
        },
        "required": ["memory_id"],
    }
)


def _format_entries(entries: tuple[MemoryEntry, ...]) -> str:
    """Format memory entries as human-readable text."""
    if not entries:
        return "No memories found."
    parts: list[str] = []
    for entry in entries:
        score = (
            f" (relevance: {entry.relevance_score:.2f})"
            if entry.relevance_score is not None
            else ""
        )
        parts.append(f"[{entry.category.value}]{score} {entry.content}")
    return "\n".join(parts)


def _parse_categories(
    raw: Any,
) -> frozenset[MemoryCategory] | None:
    """Parse category filter from LLM arguments.

    Invalid category values are skipped with a debug log.
    """
    if not raw or not isinstance(raw, list):
        return None
    categories: list[MemoryCategory] = []
    for val in raw:
        try:
            categories.append(MemoryCategory(val))
        except ValueError:
            logger.debug(
                MEMORY_RETRIEVAL_DEGRADED,
                source="category_parse",
                invalid_category=str(val),
                reason="unknown category value, skipped",
            )
    return frozenset(categories) if categories else None


def _merge_results(
    existing: tuple[MemoryEntry, ...],
    new: tuple[MemoryEntry, ...],
) -> tuple[MemoryEntry, ...]:
    """Merge two entry tuples by ID, keeping higher-relevance entries.

    Preserves the order of *existing* and appends unseen entries from
    *new* at the end.  When the same ID appears in both, the entry
    with the higher ``relevance_score`` is kept (treating ``None`` as
    ``0.0``).

    Args:
        existing: Current entries (order preserved).
        new: New entries to merge in.

    Returns:
        Merged tuple with stable ordering.
    """
    merged: dict[str, MemoryEntry] = {}
    order: list[str] = []
    for entry in existing:
        merged[entry.id] = entry
        order.append(entry.id)

    for entry in new:
        if entry.id in merged:
            current = merged[entry.id]
            current_rel = current.relevance_score or 0.0
            new_rel = entry.relevance_score or 0.0
            if new_rel > current_rel:
                merged[entry.id] = entry
        else:
            merged[entry.id] = entry
            order.append(entry.id)

    return tuple(merged[eid] for eid in order)


def _parse_search_args(
    arguments: dict[str, Any],
    config_max_memories: int,
) -> tuple[str | None, int, frozenset[MemoryCategory] | None]:
    """Extract and validate search_memory arguments.

    Args:
        arguments: Raw tool arguments from LLM.
        config_max_memories: System-configured max memories limit.

    Returns:
        Tuple of (query_text, limit, categories).  ``query_text``
        is ``None`` when the query is empty or whitespace-only.
    """
    query_text = arguments.get("query", "")
    if not query_text or not str(query_text).strip():
        return None, 0, None

    limit_raw = arguments.get("limit", 10)
    if isinstance(limit_raw, bool) or not isinstance(limit_raw, int | float):
        limit = 10
    else:
        limit = int(limit_raw)
    # Clamp to [1, min(50, config.max_memories)]
    effective_max = min(50, config_max_memories)
    limit = min(max(limit, 1), effective_max)

    categories = _parse_categories(arguments.get("categories"))
    return query_text, limit, categories


class ToolBasedInjectionStrategy:
    """Tool-based memory injection -- on-demand retrieval via agent tools.

    Implements ``MemoryInjectionStrategy`` protocol.  Instead of
    pre-loading memories, exposes ``search_memory`` and
    ``recall_memory`` tools for the agent to invoke during execution.

    Note: Tool-based strategies expose additional methods
    (``handle_tool_call``, ``get_tool_definitions``) beyond the
    base ``MemoryInjectionStrategy`` protocol.  Callers needing
    tool dispatch should type-narrow or check strategy type.

    Args:
        backend: Memory backend for personal memories.
        config: Retrieval pipeline configuration.
        shared_store: Optional shared knowledge store.
        token_estimator: Accepts for constructor parity with
            ``ContextInjectionStrategy`` (unused).
        memory_filter: Accepts for constructor parity with
            ``ContextInjectionStrategy`` (unused).
    """

    __slots__ = (
        "_backend",
        "_config",
        "_reformulator",
        "_shared_store",
        "_sufficiency_checker",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        backend: MemoryBackend,
        config: MemoryRetrievalConfig,
        shared_store: Any | None = None,
        token_estimator: Any | None = None,  # noqa: ARG002
        memory_filter: Any | None = None,  # noqa: ARG002
        reformulator: QueryReformulator | None = None,
        sufficiency_checker: SufficiencyChecker | None = None,
    ) -> None:
        self._backend = backend
        self._config = config
        self._shared_store = shared_store
        self._reformulator = reformulator
        self._sufficiency_checker = sufficiency_checker

    async def prepare_messages(
        self,
        agent_id: NotBlankStr,  # noqa: ARG002
        query_text: NotBlankStr,  # noqa: ARG002
        token_budget: int,
    ) -> tuple[ChatMessage, ...]:
        """Return a brief instruction message about available tools.

        Tool-based strategies inject minimal context up front --
        the agent retrieves memories on-demand via tool calls.

        Args:
            agent_id: The agent requesting memories.
            query_text: Text for semantic retrieval (unused).
            token_budget: Maximum tokens for memory content.

        Returns:
            Single instruction message, or empty if budget is zero.
        """
        if token_budget <= 0:
            return ()
        return (
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=_INSTRUCTION,
            ),
        )

    def get_tool_definitions(self) -> tuple[ToolDefinition, ...]:
        """Return search_memory and recall_memory tool definitions.

        Returns:
            Two tool definitions with JSON Schema parameters.
        """
        # dict() converts MappingProxyType (not deepcopy-able) to a
        # plain dict before deepcopy creates an independent schema copy.
        return (
            ToolDefinition(
                name=NotBlankStr(SEARCH_MEMORY_TOOL_NAME),
                description=(
                    "Search agent memory for relevant past context, "
                    "decisions, or learned information."
                ),
                parameters_schema=copy.deepcopy(dict(SEARCH_MEMORY_SCHEMA)),
            ),
            ToolDefinition(
                name=NotBlankStr(RECALL_MEMORY_TOOL_NAME),
                description="Recall a specific memory entry by its ID.",
                parameters_schema=copy.deepcopy(dict(RECALL_MEMORY_SCHEMA)),
            ),
        )

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str,
    ) -> str:
        """Dispatch a tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool being called.
            arguments: Tool arguments from the LLM.
            agent_id: Agent making the call.

        Returns:
            Formatted text result.

        Raises:
            ValueError: If ``tool_name`` is not recognized.
        """
        if tool_name == SEARCH_MEMORY_TOOL_NAME:
            return await self._handle_search(arguments, agent_id)
        if tool_name == RECALL_MEMORY_TOOL_NAME:
            return await self._handle_recall(arguments, agent_id)
        msg = f"Unknown tool: {tool_name!r}"
        logger.warning(
            MEMORY_RETRIEVAL_DEGRADED,
            source="handle_tool_call",
            agent_id=agent_id,
            tool_name=tool_name,
            error=msg,
        )
        raise ValueError(msg)

    async def _handle_search(
        self,
        arguments: dict[str, Any],
        agent_id: str,
    ) -> str:
        """Handle a search_memory tool call."""
        query_text, limit, categories = _parse_search_args(
            arguments,
            self._config.max_memories,
        )
        if query_text is None:
            return "Error: query must be a non-empty string."

        logger.info(
            MEMORY_RETRIEVAL_START,
            agent_id=agent_id,
            tool=SEARCH_MEMORY_TOOL_NAME,
            query_length=len(query_text),
        )

        try:
            entries = await self._retrieve_with_reformulation(
                query_text=query_text,
                limit=limit,
                categories=categories,
                agent_id=agent_id,
            )
        except builtins.MemoryError, RecursionError:
            raise
        except DomainMemoryError as exc:
            logger.warning(
                MEMORY_RETRIEVAL_DEGRADED,
                source=SEARCH_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return SEARCH_UNAVAILABLE
        except Exception as exc:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source=SEARCH_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return SEARCH_UNEXPECTED

        logger.info(
            MEMORY_RETRIEVAL_COMPLETE,
            agent_id=agent_id,
            tool=SEARCH_MEMORY_TOOL_NAME,
            ranked_count=len(entries),
        )

        return _format_entries(entries)

    async def _retrieve_with_reformulation(
        self,
        *,
        query_text: str,
        limit: int,
        categories: frozenset[MemoryCategory] | None,
        agent_id: str,
    ) -> tuple[MemoryEntry, ...]:
        """Retrieve memories, optionally with iterative reformulation.

        When ``query_reformulation_enabled`` is True and both the
        reformulator and sufficiency checker are configured, performs
        up to ``max_reformulation_rounds`` rounds of:
        search -> check sufficiency -> reformulate query.

        Returns the merged results from all rounds.
        """
        query = MemoryQuery(
            text=query_text,
            limit=limit,
            categories=categories,
        )
        entries = await self._backend.retrieve(
            NotBlankStr(agent_id),
            query,
        )

        if not self._should_reformulate():
            return entries

        return await self._reformulation_loop(
            initial_entries=entries,
            query_text=query_text,
            limit=limit,
            categories=categories,
            agent_id=agent_id,
        )

    def _should_reformulate(self) -> bool:
        """Check whether reformulation should be attempted."""
        return (
            self._config.query_reformulation_enabled
            and self._reformulator is not None
            and self._sufficiency_checker is not None
        )

    async def _reformulation_loop(
        self,
        *,
        initial_entries: tuple[MemoryEntry, ...],
        query_text: str,
        limit: int,
        categories: frozenset[MemoryCategory] | None,
        agent_id: str,
    ) -> tuple[MemoryEntry, ...]:
        """Run the iterative reformulation loop."""
        assert self._reformulator is not None  # noqa: S101
        assert self._sufficiency_checker is not None  # noqa: S101

        entries = initial_entries
        current_query = query_text
        max_rounds = self._config.max_reformulation_rounds

        for round_idx in range(max_rounds):
            is_sufficient = await self._sufficiency_checker.check_sufficiency(
                current_query,
                entries,
            )
            if is_sufficient:
                logger.info(
                    MEMORY_REFORMULATION_SUFFICIENT,
                    agent_id=agent_id,
                    round=round_idx,
                    result_count=len(entries),
                )
                return entries

            new_query = await self._reformulator.reformulate(
                current_query,
                entries,
            )
            if new_query is None or new_query == current_query:
                return entries

            logger.debug(
                MEMORY_REFORMULATION_ROUND,
                agent_id=agent_id,
                round=round_idx + 1,
                original_length=len(current_query),
                new_length=len(new_query),
            )

            next_query = MemoryQuery(
                text=new_query,
                limit=limit,
                categories=categories,
            )
            new_entries = await self._backend.retrieve(
                NotBlankStr(agent_id),
                next_query,
            )
            entries = _merge_results(entries, new_entries)
            current_query = new_query

        return entries

    async def _handle_recall(
        self,
        arguments: dict[str, Any],
        agent_id: str,
    ) -> str:
        """Handle a recall_memory tool call."""
        memory_id = arguments.get("memory_id", "")
        if not memory_id or not str(memory_id).strip():
            return "Error: memory_id is required."

        memory_id = str(memory_id).strip()
        if len(memory_id) > _MAX_MEMORY_ID_LEN:
            return "Error: memory_id exceeds maximum allowed length."

        logger.info(
            MEMORY_RETRIEVAL_START,
            agent_id=agent_id,
            tool=RECALL_MEMORY_TOOL_NAME,
            memory_id=memory_id,
        )

        try:
            entry = await self._backend.get(
                NotBlankStr(agent_id),
                NotBlankStr(memory_id),
            )
        except builtins.MemoryError, RecursionError:
            raise
        except DomainMemoryError as exc:
            logger.warning(
                MEMORY_RETRIEVAL_DEGRADED,
                source=RECALL_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return RECALL_UNAVAILABLE
        except Exception as exc:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source=RECALL_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return RECALL_UNEXPECTED

        logger.info(
            MEMORY_RETRIEVAL_COMPLETE,
            agent_id=agent_id,
            tool=RECALL_MEMORY_TOOL_NAME,
            found=entry is not None,
        )

        if entry is None:
            safe_id = memory_id[:64]
            return f"{RECALL_NOT_FOUND_PREFIX} {safe_id}"

        return _format_entries((entry,))

    @property
    def strategy_name(self) -> str:
        """Human-readable strategy identifier.

        Returns:
            ``"tool_based"``.
        """
        return "tool_based"
