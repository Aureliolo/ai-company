"""Bridge between ToolInvoker and invocation tracking.

Separates activity-tracking concerns from tool execution logic in
``invoker.py``.  Best-effort: failures here never affect tool results.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.tool import TOOL_INVOCATION_RECORD_FAILED
from synthorg.tools.invocation_record import ToolInvocationRecord

if TYPE_CHECKING:
    from synthorg.providers.models import ToolCall, ToolResult
    from synthorg.tools.invoker import ToolInvoker

logger = get_logger(__name__)


async def record_tool_invocation(
    invoker: ToolInvoker,
    tool_call: ToolCall,
    result: ToolResult,
) -> None:
    """Record a tool invocation for activity tracking (best-effort).

    Silently degrades on failure so tool execution is never affected.

    Args:
        invoker: The invoker instance (provides agent/task context).
        tool_call: The tool call that was executed.
        result: The tool result.
    """
    tracker = invoker._invocation_tracker  # noqa: SLF001
    agent_id = invoker._agent_id  # noqa: SLF001
    if tracker is None or agent_id is None:
        return
    try:
        record = ToolInvocationRecord(
            agent_id=agent_id,
            task_id=invoker._task_id,  # noqa: SLF001
            tool_name=tool_call.name,
            is_success=not result.is_error,
            timestamp=datetime.now(UTC),
            error_message=(result.content[:2048] if result.is_error else None),
        )
        await tracker.record(record)
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            TOOL_INVOCATION_RECORD_FAILED,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            exc_info=True,
        )
