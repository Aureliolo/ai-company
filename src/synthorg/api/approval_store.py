"""Approval store with optional SQLite persistence.

Provides async CRUD operations for ``ApprovalItem`` instances.
Designed to be attached to ``AppState``.  When a
``SQLiteApprovalRepository`` is provided, mutations are persisted
to the database while the in-memory dict serves as a read cache.
"""

from collections.abc import Callable  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.api.errors import ConflictError
from synthorg.core.approval import ApprovalItem  # noqa: TC001
from synthorg.core.enums import (
    ApprovalRiskLevel,
    ApprovalStatus,
)
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_APPROVAL_CONFLICT,
    API_APPROVAL_EXPIRED,
    API_APPROVAL_STORE_CLEARED,
    API_RESOURCE_NOT_FOUND,
)

if TYPE_CHECKING:
    from synthorg.persistence.sqlite.approval_repo import (
        SQLiteApprovalRepository,
    )

logger = get_logger(__name__)


class ApprovalStore:
    """Approval store with in-memory cache and optional SQLite persistence.

    Uses a plain ``dict`` for O(1) lookups by ID.  Thread-safety is
    not needed because Litestar runs on a single event loop.

    When ``repo`` is provided, all mutations are persisted to the
    database.  The in-memory dict serves as a read-through cache.

    Args:
        on_expire: Optional callback for expired items.
        repo: Optional SQLite repository for persistence.
    """

    def __init__(
        self,
        *,
        on_expire: Callable[[ApprovalItem], None] | None = None,
        repo: SQLiteApprovalRepository | None = None,
    ) -> None:
        self._items: dict[str, ApprovalItem] = {}
        self._on_expire = on_expire
        self._repo = repo

    def clear(self) -> None:
        """Reset all approval items for test isolation."""
        cleared_count = len(self._items)
        self._items.clear()
        logger.info(API_APPROVAL_STORE_CLEARED, cleared_count=cleared_count)

    async def add(self, item: ApprovalItem) -> None:
        """Add a new approval item.

        Args:
            item: The approval item to store.

        Raises:
            ConflictError: If an item with the same ID already exists.
        """
        if item.id in self._items:
            msg = f"Approval {item.id!r} already exists"
            logger.warning(
                API_APPROVAL_CONFLICT,
                error="duplicate",
                approval_id=item.id,
            )
            raise ConflictError(msg)
        if self._repo is not None:
            await self._repo.save(item)
        self._items[item.id] = item

    async def get(self, approval_id: str) -> ApprovalItem | None:
        """Get an approval item by ID, applying lazy expiration.

        Falls through to the repository on cache miss when a repo is
        configured, ensuring persisted items survive restarts.

        Args:
            approval_id: The approval identifier.

        Returns:
            The approval item, or ``None`` if not found.
        """
        item = self._items.get(approval_id)
        if item is None and self._repo is not None:
            item = await self._repo.get(approval_id)
            if item is not None:
                self._items[item.id] = item
        if item is None:
            return None
        return self._check_expiration(item)

    async def list_items(
        self,
        *,
        status: ApprovalStatus | None = None,
        risk_level: ApprovalRiskLevel | None = None,
        action_type: str | None = None,
    ) -> tuple[ApprovalItem, ...]:
        """List approval items with optional filters.

        When a repository is configured, queries the repo (source of
        truth) and refreshes the in-memory cache.  Otherwise falls
        back to the cache alone.

        Applies lazy expiration to all items before filtering.

        Args:
            status: Filter by approval status.
            risk_level: Filter by risk level.
            action_type: Filter by action type.

        Returns:
            Tuple of matching approval items.
        """
        if self._repo is not None:
            repo_items = await self._repo.list_items(
                status=status,
                risk_level=risk_level,
                action_type=action_type,
            )
            for item in repo_items:
                self._items[item.id] = item
            return tuple(self._check_expiration(item) for item in repo_items)
        result = []
        for stored in list(self._items.values()):
            checked = self._check_expiration(stored)
            if status is not None and checked.status != status:
                continue
            if risk_level is not None and checked.risk_level != risk_level:
                continue
            if action_type is not None and checked.action_type != action_type:
                continue
            result.append(checked)
        return tuple(result)

    async def save(self, item: ApprovalItem) -> ApprovalItem | None:
        """Update an existing approval item.

        Args:
            item: The updated approval item.

        Returns:
            The saved item, or ``None`` if the ID was not found.
        """
        if item.id not in self._items:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="approval",
                approval_id=item.id,
            )
            return None
        if self._repo is not None:
            await self._repo.save(item)
        self._items[item.id] = item
        return item

    async def save_if_pending(
        self,
        item: ApprovalItem,
    ) -> ApprovalItem | None:
        """Conditionally update an approval item if it is still pending.

        A lazy expiration check is applied before comparing status.

        Args:
            item: The updated approval item (must have an existing ID).

        Returns:
            The saved item on success, or ``None`` if:

            * no item with the given ID exists in the store,
            * the stored item has expired, or
            * the stored item is no longer ``PENDING`` (e.g. a
              concurrent decision was made).
        """
        current = self._items.get(item.id)
        if current is None:
            return None
        # Apply lazy expiration check before comparing status.
        current = self._check_expiration(current)
        if current.status != ApprovalStatus.PENDING:
            return None
        if self._repo is not None:
            await self._repo.save(item)
        self._items[item.id] = item
        return item

    def _check_expiration(self, item: ApprovalItem) -> ApprovalItem:
        """Lazily expire a pending item past its ``expires_at``.

        If the item is PENDING and has expired, it is transitioned to
        EXPIRED in the store and the updated item is returned.

        Args:
            item: The item to check.

        Returns:
            The original or expired item.
        """
        if (
            item.status == ApprovalStatus.PENDING
            and item.expires_at is not None
            and datetime.now(UTC) >= item.expires_at
        ):
            expired = item.model_copy(
                update={"status": ApprovalStatus.EXPIRED},
            )
            self._items[item.id] = expired
            logger.info(
                API_APPROVAL_EXPIRED,
                approval_id=item.id,
            )
            if self._on_expire is not None:
                try:
                    self._on_expire(expired)
                except MemoryError, RecursionError:
                    raise
                except Exception:
                    logger.exception(
                        API_APPROVAL_EXPIRED,
                        approval_id=item.id,
                        note="on_expire callback failed",
                    )
            return expired
        return item
