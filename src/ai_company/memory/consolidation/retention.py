"""Retention enforcer for memory lifecycle management.

Deletes memories that have exceeded their per-category retention
period.
"""

from datetime import UTC, datetime, timedelta

from ai_company.core.enums import MemoryCategory
from ai_company.core.types import NotBlankStr  # noqa: TC001
from ai_company.memory.consolidation.config import RetentionConfig  # noqa: TC001
from ai_company.memory.models import MemoryQuery
from ai_company.memory.protocol import MemoryBackend  # noqa: TC001
from ai_company.observability import get_logger
from ai_company.observability.events.consolidation import (
    RETENTION_CLEANUP_COMPLETE,
    RETENTION_CLEANUP_START,
)

logger = get_logger(__name__)


class RetentionEnforcer:
    """Enforces per-category memory retention policies.

    Queries for memories older than the configured retention period
    and deletes them from the backend.

    Args:
        config: Retention configuration with per-category rules.
        backend: Memory backend for querying and deleting.
    """

    def __init__(
        self,
        *,
        config: RetentionConfig,
        backend: MemoryBackend,
    ) -> None:
        self._config = config
        self._backend = backend
        self._category_days: dict[MemoryCategory, int] = {
            rule.category: rule.retention_days for rule in config.rules
        }

    async def cleanup_expired(
        self,
        agent_id: NotBlankStr,
        now: datetime | None = None,
    ) -> int:
        """Delete memories that have exceeded their retention period.

        Args:
            agent_id: Agent whose memories to clean up.
            now: Current time (defaults to UTC now).

        Returns:
            Number of expired memories deleted.
        """
        if now is None:
            now = datetime.now(UTC)

        logger.info(RETENTION_CLEANUP_START, agent_id=agent_id)
        total_deleted = 0

        categories_to_check = self._get_categories_with_retention()

        for category, retention_days in categories_to_check:
            cutoff = now - timedelta(days=retention_days)
            query = MemoryQuery(
                categories=frozenset({category}),
                until=cutoff,
                limit=1000,
            )
            expired = await self._backend.retrieve(agent_id, query)
            for entry in expired:
                deleted = await self._backend.delete(agent_id, entry.id)
                if deleted:
                    total_deleted += 1

        logger.info(
            RETENTION_CLEANUP_COMPLETE,
            agent_id=agent_id,
            deleted_count=total_deleted,
        )
        return total_deleted

    def _get_categories_with_retention(
        self,
    ) -> list[tuple[MemoryCategory, int]]:
        """Build list of (category, retention_days) pairs.

        Includes explicit per-category rules and fills in any remaining
        categories with the default retention (if set).

        Returns:
            List of category/retention_days tuples.
        """
        result: list[tuple[MemoryCategory, int]] = []

        for category in MemoryCategory:
            days = self._category_days.get(category)
            if days is not None:
                result.append((category, days))
            elif self._config.default_retention_days is not None:
                result.append((category, self._config.default_retention_days))

        return result
