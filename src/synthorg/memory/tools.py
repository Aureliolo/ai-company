"""Memory tool wrappers for ToolRegistry integration.

Provides ``SearchMemoryTool`` and ``RecallMemoryTool`` -- thin
``BaseTool`` subclasses that delegate execution to the existing
``ToolBasedInjectionStrategy.handle_tool_call()`` method.  This
bridges the memory injection system into the standard tool dispatch
pipeline (``ToolInvoker`` -> ``ToolRegistry`` -> ``BaseTool.execute``).
"""

import copy
from typing import TYPE_CHECKING, Any

from synthorg.core.enums import ToolCategory
from synthorg.memory.tool_retriever import (
    RECALL_MEMORY_SCHEMA,
    RECALL_MEMORY_TOOL_NAME,
    SEARCH_MEMORY_SCHEMA,
    SEARCH_MEMORY_TOOL_NAME,
    ToolBasedInjectionStrategy,
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import MEMORY_RETRIEVAL_START
from synthorg.tools.base import BaseTool, ToolExecutionResult

if TYPE_CHECKING:
    from synthorg.memory.injection import MemoryInjectionStrategy
    from synthorg.tools.registry import ToolRegistry

logger = get_logger(__name__)

# Prefixes that indicate an error response from the strategy's handler.
_ERROR_PREFIXES = (
    "Error:",
    "Memory search is temporarily unavailable.",
    "Memory recall is temporarily unavailable.",
    "Memory search encountered an unexpected error.",
    "Memory recall encountered an unexpected error.",
    "Memory not found:",
)


def _is_error_response(text: str) -> bool:
    """Check whether the strategy response indicates an error."""
    return any(text.startswith(prefix) for prefix in _ERROR_PREFIXES)


class SearchMemoryTool(BaseTool):
    """``search_memory`` tool for ToolRegistry integration.

    Delegates execution to ``ToolBasedInjectionStrategy.handle_tool_call``,
    wrapping the string result in a ``ToolExecutionResult``.  The
    ``agent_id`` is bound at construction time (tools are per-agent).

    Args:
        strategy: The tool-based injection strategy holding the backend.
        agent_id: Agent ID bound to this tool instance.
    """

    __slots__ = ("_agent_id", "_strategy")

    def __init__(
        self,
        *,
        strategy: ToolBasedInjectionStrategy,
        agent_id: str,
    ) -> None:
        super().__init__(
            name=SEARCH_MEMORY_TOOL_NAME,
            description=(
                "Search agent memory for relevant past context, "
                "decisions, or learned information."
            ),
            parameters_schema=copy.deepcopy(SEARCH_MEMORY_SCHEMA),
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
            arguments: Tool arguments from the LLM (query, categories, limit).

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

    __slots__ = ("_agent_id", "_strategy")

    def __init__(
        self,
        *,
        strategy: ToolBasedInjectionStrategy,
        agent_id: str,
    ) -> None:
        super().__init__(
            name=RECALL_MEMORY_TOOL_NAME,
            description="Recall a specific memory entry by its ID.",
            parameters_schema=copy.deepcopy(RECALL_MEMORY_SCHEMA),
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


def create_memory_tools(
    *,
    strategy: ToolBasedInjectionStrategy,
    agent_id: str,
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
    return (
        SearchMemoryTool(strategy=strategy, agent_id=agent_id),
        RecallMemoryTool(strategy=strategy, agent_id=agent_id),
    )


def registry_with_memory_tools(
    tool_registry: ToolRegistry,
    strategy: MemoryInjectionStrategy | None,
    agent_id: str,
) -> ToolRegistry:
    """Build a registry with memory tools added if applicable.

    Returns the original registry unchanged when the strategy is
    ``None`` or is not a ``ToolBasedInjectionStrategy``.

    Follows the ``registry_with_approval_tool`` pattern in
    ``engine/_security_factory.py``.

    Args:
        tool_registry: Base tool registry.
        strategy: Memory injection strategy (may be any type or None).
        agent_id: Agent ID to bind to the memory tools.

    Returns:
        Augmented registry with memory tools, or original if not applicable.
    """
    if not isinstance(strategy, ToolBasedInjectionStrategy):
        return tool_registry

    from synthorg.tools.registry import (  # noqa: PLC0415
        ToolRegistry as _ToolRegistry,
    )

    logger.info(
        MEMORY_RETRIEVAL_START,
        agent_id=agent_id,
        tool="registry_augmentation",
        query_length=0,
    )
    memory_tools = create_memory_tools(strategy=strategy, agent_id=agent_id)
    existing = list(tool_registry.all_tools())
    return _ToolRegistry([*existing, *memory_tools])
