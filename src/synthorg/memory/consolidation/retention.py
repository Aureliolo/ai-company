"""Retention enforcer for memory lifecycle management.

Deletes memories that have exceeded their per-category retention
period.  Supports per-agent overrides that take priority over
company-level defaults.
"""

from collections.abc import Mapping  # noqa: TC003
from datetime import UTC, datetime, timedelta

from synthorg.core.enums import MemoryCategory
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.consolidation.config import RetentionConfig  # noqa: TC001
from synthorg.memory.models import MemoryQuery
from synthorg.memory.protocol import MemoryBackend  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.consolidation import (
    RETENTION_AGENT_OVERRIDE_APPLIED,
    RETENTION_CLEANUP_COMPLETE,
    RETENTION_CLEANUP_FAILED,
    RETENTION_CLEANUP_START,
    RETENTION_DELETE_SKIPPED,
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
        self._categories_to_check = self._build_categories_to_check(config)

    @staticmethod
    def _build_categories_to_check(
        config: RetentionConfig,
    ) -> tuple[tuple[MemoryCategory, int], ...]:
        """Pre-compute (category, retention_days) pairs at construction.

        Includes explicit per-category rules and fills in any remaining
        categories with the default retention (if set).

        Args:
            config: Retention configuration with per-category rules.

        Returns:
            Tuple of category/retention_days pairs.
        """
        category_days = {rule.category: rule.retention_days for rule in config.rules}
        result: list[tuple[MemoryCategory, int]] = []
        for category in MemoryCategory:
            days = category_days.get(category)
            if days is not None:
                result.append((category, days))
            elif config.default_retention_days is not None:
                result.append((category, config.default_retention_days))
        return tuple(result)

    @staticmethod
    def _resolve_categories(
        base: tuple[tuple[MemoryCategory, int], ...],
        agent_overrides: Mapping[MemoryCategory, int],
        agent_default_days: int | None,
        company_default_days: int | None,
    ) -> tuple[tuple[MemoryCategory, int], ...]:
        """Merge agent overrides with company-level retention config.

        Resolution per category (highest priority first):

        1. Agent per-category override
        2. Company per-category rule (from *base*)
        3. Agent global default (*agent_default_days*)
        4. Company global default (*company_default_days*)
        5. Skip (keep forever)

        Args:
            base: Pre-computed company (category, days) pairs.
            agent_overrides: Agent per-category retention overrides.
            agent_default_days: Agent-level default retention in days.
            company_default_days: Company-level default retention in
                days.

        Returns:
            Merged tuple of (category, days) pairs.
        """
        base_dict = dict(base)
        result: list[tuple[MemoryCategory, int]] = []
        for category in MemoryCategory:
            # 1. Agent per-category override
            agent_days = agent_overrides.get(category)
            if agent_days is not None:
                result.append((category, agent_days))
                continue
            # 2. Company per-category rule
            company_days = base_dict.get(category)
            if company_days is not None:
                result.append((category, company_days))
                continue
            # 3. Agent global default
            if agent_default_days is not None:
                result.append((category, agent_default_days))
                continue
            # 4. Company global default
            if company_default_days is not None:
                result.append((category, company_default_days))
                continue
            # 5. No retention -- skip
        return tuple(result)

    async def cleanup_expired(
        self,
        agent_id: NotBlankStr,
        now: datetime | None = None,
        *,
        agent_category_overrides: Mapping[MemoryCategory, int] | None = None,
        agent_default_retention_days: int | None = None,
    ) -> int:
        """Delete memories that have exceeded their retention period.

        Processes each category independently so that a failure in one
        category does not prevent cleanup of the remaining categories.

        Processes up to 1000 expired entries per category per
        invocation.  Multiple calls may be needed for categories
        with a large backlog.

        When *agent_category_overrides* or *agent_default_retention_days*
        is provided, per-agent retention rules are merged with company
        defaults using :meth:`_resolve_categories`.

        Args:
            agent_id: Agent whose memories to clean up.
            now: Current time (defaults to UTC now).
            agent_category_overrides: Per-category retention overrides
                for this agent (mapping of category to days).
            agent_default_retention_days: Agent-level default retention
                in days.

        Returns:
            Number of expired memories deleted.
        """
        if now is None:
            now = datetime.now(UTC)

        has_overrides = (
            agent_category_overrides is not None
            or agent_default_retention_days is not None
        )
        if has_overrides:
            categories_to_check = self._resolve_categories(
                self._categories_to_check,
                agent_overrides=agent_category_overrides or {},
                agent_default_days=agent_default_retention_days,
                company_default_days=self._config.default_retention_days,
            )
            logger.info(
                RETENTION_AGENT_OVERRIDE_APPLIED,
                agent_id=agent_id,
                overridden_count=len(categories_to_check),
            )
        else:
            categories_to_check = self._categories_to_check

        logger.info(RETENTION_CLEANUP_START, agent_id=agent_id)
        total_deleted = 0

        for category, retention_days in categories_to_check:
            try:
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
                    else:
                        logger.debug(
                            RETENTION_DELETE_SKIPPED,
                            agent_id=agent_id,
                            entry_id=entry.id,
                            category=category.value,
                        )
            except Exception as exc:
                logger.warning(
                    RETENTION_CLEANUP_FAILED,
                    agent_id=agent_id,
                    category=category.value,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue

        logger.info(
            RETENTION_CLEANUP_COMPLETE,
            agent_id=agent_id,
            deleted_count=total_deleted,
        )
        return total_deleted
