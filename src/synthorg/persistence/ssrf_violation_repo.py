"""SSRF violation repository protocol."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic import AwareDatetime

    from synthorg.core.types import NotBlankStr
    from synthorg.security.ssrf_violation import SsrfViolation, SsrfViolationStatus


@runtime_checkable
class SsrfViolationRepository(Protocol):
    """CRUD for SSRF violation records.

    Provides persistence for ``SsrfViolation`` instances with
    query support by status and status updates for allow/deny.
    """

    async def save(self, violation: SsrfViolation) -> None:
        """Persist a new SSRF violation.

        Args:
            violation: The violation to save.

        Raises:
            DuplicateRecordError: If a violation with the same ID exists.
        """
        ...

    async def get(
        self,
        violation_id: NotBlankStr,
    ) -> SsrfViolation | None:
        """Retrieve a violation by ID.

        Args:
            violation_id: The violation identifier.

        Returns:
            The violation, or None if not found.
        """
        ...

    async def list_violations(
        self,
        *,
        status: SsrfViolationStatus | None = None,
        limit: int = 100,
    ) -> tuple[SsrfViolation, ...]:
        """List violations, optionally filtered by status.

        Args:
            status: Filter by status (None for all).
            limit: Maximum number of results.

        Returns:
            Tuple of violations, ordered by timestamp DESC.
        """
        ...

    async def update_status(
        self,
        violation_id: NotBlankStr,
        *,
        status: SsrfViolationStatus,
        resolved_by: NotBlankStr,
        resolved_at: AwareDatetime,
    ) -> bool:
        """Update a violation's status (allow or deny).

        Args:
            violation_id: The violation to update.
            status: New status (ALLOWED or DENIED).
            resolved_by: User who resolved it.
            resolved_at: When it was resolved.

        Returns:
            True if the violation was found and updated.
        """
        ...
