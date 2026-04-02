"""Tool-based memory injection strategy.

Provides ``search_memory`` and ``recall_memory`` tool definitions
that agents invoke on-demand during execution.  Implements the
``MemoryInjectionStrategy`` protocol with tool-based retrieval.
"""

import builtins
from typing import TYPE_CHECKING, Any

from synthorg.core.enums import MemoryCategory
from synthorg.core.types import NotBlankStr
from synthorg.memory.errors import MemoryError as DomainMemoryError
from synthorg.memory.models import MemoryEntry, MemoryQuery
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_RETRIEVAL_COMPLETE,
    MEMORY_RETRIEVAL_DEGRADED,
    MEMORY_RETRIEVAL_START,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage, ToolDefinition

if TYPE_CHECKING:
    from synthorg.memory.protocol import MemoryBackend
    from synthorg.memory.retrieval_config import MemoryRetrievalConfig

logger = get_logger(__name__)

_SEARCH_TOOL = "search_memory"
_RECALL_TOOL = "recall_memory"

_INSTRUCTION = (
    "You have access to memory recall tools. Use search_memory "
    "when you need to recall past context, decisions, or learned "
    "information. Use recall_memory to fetch a specific memory by ID."
)

_SEARCH_MEMORY_SCHEMA: dict[str, Any] = {
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
                "Optional category filter (episodic, semantic, procedural, social)."
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

_RECALL_MEMORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "memory_id": {
            "type": "string",
            "description": "Exact memory ID to recall.",
        },
    },
    "required": ["memory_id"],
}


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
    """Parse category filter from LLM arguments."""
    if not raw or not isinstance(raw, list):
        return None
    categories: list[MemoryCategory] = []
    for val in raw:
        try:
            categories.append(MemoryCategory(val))
        except ValueError:
            continue
    return frozenset(categories) if categories else None


class ToolBasedInjectionStrategy:
    """Tool-based memory injection -- on-demand retrieval via agent tools.

    Implements ``MemoryInjectionStrategy`` protocol.  Instead of
    pre-loading memories, exposes ``search_memory`` and
    ``recall_memory`` tools for the agent to invoke during execution.

    Args:
        backend: Memory backend for personal memories.
        config: Retrieval pipeline configuration.
        shared_store: Optional shared knowledge store.
        token_estimator: Unused (protocol conformance).
        memory_filter: Unused (protocol conformance).
    """

    def __init__(
        self,
        *,
        backend: MemoryBackend,
        config: MemoryRetrievalConfig,
        shared_store: Any | None = None,
        token_estimator: Any | None = None,  # noqa: ARG002
        memory_filter: Any | None = None,  # noqa: ARG002
    ) -> None:
        self._backend = backend
        self._config = config
        self._shared_store = shared_store

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
        return (
            ToolDefinition(
                name=NotBlankStr(_SEARCH_TOOL),
                description=(
                    "Search agent memory for relevant past context, "
                    "decisions, or learned information."
                ),
                parameters_schema=_SEARCH_MEMORY_SCHEMA,
            ),
            ToolDefinition(
                name=NotBlankStr(_RECALL_TOOL),
                description="Recall a specific memory entry by its ID.",
                parameters_schema=_RECALL_MEMORY_SCHEMA,
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
        if tool_name == _SEARCH_TOOL:
            return await self._handle_search(arguments, agent_id)
        if tool_name == _RECALL_TOOL:
            return await self._handle_recall(arguments, agent_id)
        msg = f"Unknown tool: {tool_name!r}"
        raise ValueError(msg)

    async def _handle_search(
        self,
        arguments: dict[str, Any],
        agent_id: str,
    ) -> str:
        """Handle a search_memory tool call."""
        query_text = arguments.get("query", "")
        if not query_text or not str(query_text).strip():
            return "Error: query must be a non-empty string."

        limit_raw = arguments.get("limit", 10)
        limit = int(limit_raw) if isinstance(limit_raw, int | float) else 10
        categories = _parse_categories(arguments.get("categories"))

        logger.info(
            MEMORY_RETRIEVAL_START,
            agent_id=agent_id,
            tool=_SEARCH_TOOL,
            query_length=len(query_text),
        )

        try:
            query = MemoryQuery(
                text=query_text,
                limit=min(max(limit, 1), 50),
                categories=categories,
            )
            entries = await self._backend.retrieve(
                NotBlankStr(agent_id),
                query,
            )
        except builtins.MemoryError, RecursionError:
            raise
        except DomainMemoryError as exc:
            logger.warning(
                MEMORY_RETRIEVAL_DEGRADED,
                source=_SEARCH_TOOL,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return "Memory search is temporarily unavailable."
        except Exception as exc:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source=_SEARCH_TOOL,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return "Memory search encountered an unexpected error."

        logger.info(
            MEMORY_RETRIEVAL_COMPLETE,
            agent_id=agent_id,
            tool=_SEARCH_TOOL,
            ranked_count=len(entries),
        )

        return _format_entries(entries)

    async def _handle_recall(
        self,
        arguments: dict[str, Any],
        agent_id: str,
    ) -> str:
        """Handle a recall_memory tool call."""
        memory_id = arguments.get("memory_id", "")
        if not memory_id:
            return "Error: memory_id is required."

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
                source=_RECALL_TOOL,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return "Memory recall is temporarily unavailable."
        except Exception as exc:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source=_RECALL_TOOL,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return "Memory recall encountered an unexpected error."

        if entry is None:
            return f"Memory not found: {memory_id}"

        return _format_entries((entry,))

    @property
    def strategy_name(self) -> str:
        """Human-readable strategy identifier.

        Returns:
            ``"tool_based"``.
        """
        return "tool_based"
