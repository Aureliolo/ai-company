"""Tool pattern content extractor.

Queries the tool invocation tracker for usage history from source
agents, aggregates by tool name, and produces summary items.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from synthorg.hr.training.models import ContentType, TrainingItem
from synthorg.observability import get_logger
from synthorg.observability.events.training import (
    HR_TRAINING_ITEMS_EXTRACTED,
)

if TYPE_CHECKING:
    from synthorg.core.enums import SeniorityLevel
    from synthorg.core.types import NotBlankStr
    from synthorg.tools.invocation_tracker import ToolInvocationTracker

logger = get_logger(__name__)

_DEFAULT_LOOKBACK_DAYS = 90


class ToolPatternExtractor:
    """Extract tool usage patterns from senior agents.

    Queries the invocation tracker for tool usage history,
    aggregates by tool name, computes success rates, and
    produces summary training items.

    Args:
        tracker: Tool invocation tracker.
        lookback_days: Number of days to look back.
    """

    def __init__(
        self,
        *,
        tracker: ToolInvocationTracker,
        lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
    ) -> None:
        self._tracker = tracker
        self._lookback_days = lookback_days

    @property
    def content_type(self) -> ContentType:
        """The content type this extractor produces."""
        return ContentType.TOOL_PATTERNS

    async def extract(
        self,
        *,
        source_agent_ids: tuple[NotBlankStr, ...],
        new_agent_role: NotBlankStr,  # noqa: ARG002
        new_agent_level: SeniorityLevel,  # noqa: ARG002
    ) -> tuple[TrainingItem, ...]:
        """Extract tool usage patterns from source agents.

        Args:
            source_agent_ids: Senior agents to extract from.
            new_agent_role: Role of the new hire (unused).
            new_agent_level: Seniority level (unused).

        Returns:
            Aggregated tool pattern training items.
        """
        if not source_agent_ids:
            return ()

        now = datetime.now(UTC)
        start = now - timedelta(days=self._lookback_days)

        # Aggregate across all source agents.
        tool_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "success": 0},
        )
        source_agents_by_tool: dict[str, set[str]] = defaultdict(set)

        for agent_id in source_agent_ids:
            records = await self._tracker.get_records(
                agent_id=str(agent_id),
                start=start,
                end=now,
            )
            for record in records:
                tool_name = str(record.tool_name)
                tool_stats[tool_name]["total"] += 1
                if record.is_success:
                    tool_stats[tool_name]["success"] += 1
                source_agents_by_tool[tool_name].add(str(agent_id))

        items: list[TrainingItem] = []
        for tool_name, stats in sorted(tool_stats.items()):
            total = stats["total"]
            success = stats["success"]
            rate = success / total if total > 0 else 0.0
            rate_pct = round(rate * 100)
            agents = source_agents_by_tool[tool_name]

            content = (
                f"Tool: {tool_name} | "
                f"Usage: {total} invocations | "
                f"Success rate: {rate_pct}% ({success}/{total}) | "
                f"Used by {len(agents)} senior agent(s)"
            )

            items.append(
                TrainingItem(
                    source_agent_id=str(
                        next(iter(agents)),
                    ),
                    content_type=ContentType.TOOL_PATTERNS,
                    content=content,
                    created_at=datetime.now(UTC),
                ),
            )

        logger.debug(
            HR_TRAINING_ITEMS_EXTRACTED,
            content_type="tool_patterns",
            agent_count=len(source_agent_ids),
            item_count=len(items),
        )
        return tuple(items)
