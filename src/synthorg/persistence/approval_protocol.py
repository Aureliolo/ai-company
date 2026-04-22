"""Repository protocol for approval item persistence.

Concrete implementation lives at
``synthorg.persistence.sqlite.approval_repo.SQLiteApprovalRepository``.
The :class:`ApprovalStore` (``synthorg.api.approval_store``) holds a
reference typed against this protocol so the storage implementation
can be swapped (e.g. a future Postgres backend) without changing the
store itself.

Mirrors the pattern of ``persistence/fine_tune_protocol.py`` and
``persistence/escalation_protocol.py``.
"""

from typing import Protocol, runtime_checkable

from synthorg.core.approval import ApprovalItem  # noqa: TC001
from synthorg.core.enums import (
    ApprovalRiskLevel,  # noqa: TC001
    ApprovalStatus,  # noqa: TC001
)
from synthorg.core.types import NotBlankStr  # noqa: TC001


@runtime_checkable
class ApprovalRepository(Protocol):
    """CRUD interface for durable approval-item storage.

    All methods are async; non-recoverable errors (``MemoryError``,
    ``RecursionError``) propagate to callers.  Constraint violations
    raise :class:`ConstraintViolationError`; other DB errors raise
    :class:`QueryError`.
    """

    async def save(self, item: ApprovalItem) -> None:
        """Upsert an approval item.

        Raises:
            ConstraintViolationError: On constraint violations.
            QueryError: On other database errors.
        """
        ...

    async def get(self, approval_id: NotBlankStr) -> ApprovalItem | None:
        """Get an approval item by ID, or ``None`` if not found.

        Raises:
            QueryError: If the database query fails.
        """
        ...

    async def list_items(
        self,
        *,
        status: ApprovalStatus | None = None,
        risk_level: ApprovalRiskLevel | None = None,
        action_type: NotBlankStr | None = None,
    ) -> tuple[ApprovalItem, ...]:
        """List approval items with optional filters.

        Raises:
            QueryError: If the database query fails.
        """
        ...

    async def delete(self, approval_id: NotBlankStr) -> bool:
        """Delete an approval item.

        Returns:
            ``True`` if a row was deleted, ``False`` if no match.

        Raises:
            QueryError: If the database query fails.
        """
        ...
