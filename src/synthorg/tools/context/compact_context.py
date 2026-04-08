"""Agent-controlled context compaction tool.

Allows agents to explicitly request context compaction when context
fill is high and reasoning clarity is critical.  The tool signals
intent via metadata -- it does NOT mutate the frozen AgentContext
directly.  The execution loop detects the directive and invokes
compaction at the turn boundary.
"""

from copy import deepcopy
from types import MappingProxyType
from typing import Any

from synthorg.core.enums import ToolCategory
from synthorg.engine.sanitization import sanitize_message
from synthorg.observability import get_logger
from synthorg.observability.events.context_budget import (
    CONTEXT_BUDGET_AGENT_COMPACTION_REQUESTED,
)
from synthorg.tools.base import BaseTool, ToolExecutionResult

logger = get_logger(__name__)

# Raw dict kept private for deepcopy at construction (MappingProxyType
# is not picklable).  Public read-only view below.
_RAW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "strategy": {
            "type": "string",
            "enum": ["summarize"],
            "description": (
                "Compaction strategy. Currently only 'summarize' is supported."
            ),
        },
        "preserve_markers": {
            "type": "boolean",
            "default": True,
            "description": (
                "Whether to preserve epistemic markers (wait, hmm, "
                "actually, etc.) in the compaction summary."
            ),
        },
        "reason": {
            "type": "string",
            "minLength": 10,
            "maxLength": 256,
            "description": (
                "Brief explanation for why compaction is needed "
                "now (e.g., 'context fill at 92 percent, need to "
                "preserve reasoning clarity')."
            ),
        },
    },
    "required": ["strategy", "reason"],
    "additionalProperties": False,
}
_COMPACT_CONTEXT_SCHEMA: MappingProxyType[str, Any] = MappingProxyType(_RAW_SCHEMA)


class CompactContextTool(BaseTool):
    """Signal context compaction to the execution loop.

    The tool validates arguments and returns a compaction directive
    in ``ToolExecutionResult.metadata``.  The execution loop detects
    the directive and performs actual compaction at the turn boundary.

    This tool is stateless and safe to register unconditionally.
    Compaction only triggers when ``CompactionConfig.agent_controlled``
    is enabled in the engine configuration.
    """

    def __init__(self) -> None:
        super().__init__(
            name="compact_context",
            description=(
                "Request context compaction when conversation has "
                "grown large. Preserves recent turns and creates a "
                "summary of older exchanges. Use when context fill "
                "is high and accuracy on complex reasoning is "
                "critical."
            ),
            parameters_schema=deepcopy(_RAW_SCHEMA),
            category=ToolCategory.MEMORY,
        )

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Signal compaction directive via metadata.

        Args:
            arguments: Validated tool arguments (strategy, reason,
                optionally preserve_markers).

        Returns:
            Result with ``compaction_directive`` metadata key.
        """
        strategy = arguments.get("strategy", "summarize")
        reason = arguments.get("reason", "")
        preserve_markers = arguments.get("preserve_markers", True)
        sanitized_reason = sanitize_message(reason, max_length=256)

        logger.info(
            CONTEXT_BUDGET_AGENT_COMPACTION_REQUESTED,
            strategy=strategy,
            preserve_markers=preserve_markers,
            reason=sanitized_reason,
        )

        return ToolExecutionResult(
            content=("Compaction directive accepted. Will execute at turn boundary."),
            metadata={
                "compaction_directive": True,
                "strategy": strategy,
                "preserve_markers": preserve_markers,
                "reason": sanitized_reason,
            },
        )
