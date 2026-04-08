"""Audit log query controller.

Exposes ``GET /security/audit`` for querying the security
evaluation audit trail with filtering and pagination.
"""

from datetime import datetime  # noqa: TC003
from typing import Annotated

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from litestar.exceptions import ClientException
from litestar.params import Parameter

from synthorg.api.dto import PaginatedResponse
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import (
    PaginationLimit,
    PaginationOffset,
    paginate,
)
from synthorg.api.path_params import QUERY_MAX_LENGTH
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_AUDIT_QUERIED,
    API_VALIDATION_FAILED,
)
from synthorg.security.models import AuditEntry

logger = get_logger(__name__)

_MAX_AUDIT_QUERY = 10_000
"""Safety cap on audit entries fetched per request."""


class AuditController(Controller):
    """Query the security evaluation audit trail."""

    path = "/security/audit"
    tags = ("security",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_audit_entries(  # noqa: PLR0913
        self,
        state: State,
        agent_id: Annotated[str, Parameter(max_length=QUERY_MAX_LENGTH)] | None = None,
        tool_name: Annotated[str, Parameter(max_length=QUERY_MAX_LENGTH)] | None = None,
        action_type: Annotated[str, Parameter(max_length=QUERY_MAX_LENGTH)]
        | None = None,
        verdict: Annotated[str, Parameter(max_length=50)] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[AuditEntry]:
        """Query audit entries with optional filters.

        All filters are AND-combined.  Results are newest-first.
        Up to :data:`_MAX_AUDIT_QUERY` entries are fetched from the
        underlying store; pagination is applied afterwards.

        Args:
            state: Application state with audit_log service.
            agent_id: Filter by agent identifier.
            tool_name: Filter by tool name.
            action_type: Filter by action type string.
            verdict: Filter by verdict string.
            since: Exclude entries before this datetime (timezone-aware).
            until: Exclude entries after this datetime (timezone-aware).
            offset: Pagination offset.
            limit: Page size.

        Returns:
            Paginated audit entries.

        Raises:
            ClientException: If *since* > *until*.
        """
        if (since is not None and since.tzinfo is None) or (
            until is not None and until.tzinfo is None
        ):
            logger.warning(
                API_VALIDATION_FAILED,
                reason="naive datetime",
                since=str(since),
                until=str(until),
            )
            raise ClientException(
                detail="'since' and 'until' must be timezone-aware",
            )
        if since is not None and until is not None and since > until:
            logger.warning(
                API_VALIDATION_FAILED,
                reason="inverted time window",
                since=str(since),
                until=str(until),
            )
            raise ClientException(
                detail="'since' must not be after 'until'",
            )
        app_state = state.app_state
        entries = app_state.audit_log.query(
            agent_id=agent_id,
            tool_name=tool_name,
            action_type=action_type,
            verdict=verdict,
            since=since,
            until=until,
            limit=_MAX_AUDIT_QUERY,
        )
        page, meta = paginate(entries, offset=offset, limit=limit)
        logger.info(
            API_AUDIT_QUERIED,
            total=meta.total,
            offset=meta.offset,
            limit=meta.limit,
        )
        return PaginatedResponse[AuditEntry](
            data=page,
            pagination=meta,
        )
