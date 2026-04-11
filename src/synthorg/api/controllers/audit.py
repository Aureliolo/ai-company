"""Audit log query controller.

Exposes ``GET /security/audit`` for querying the security
evaluation audit trail with filtering and pagination.

JSONB-native queries (containment, key existence, path extraction)
are available when the Postgres persistence backend is active.
"""

import json
from datetime import datetime  # noqa: TC003
from typing import Annotated

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from litestar.exceptions import ClientException
from litestar.params import Parameter

from synthorg.api.dto import PaginatedResponse, PaginationMeta
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
from synthorg.persistence.jsonb_capability import (
    JsonbQueryCapability,
    validate_jsonb_path,
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
        jsonb_contains: Annotated[str, Parameter(max_length=2048)] | None = None,
        jsonb_key_exists: Annotated[str, Parameter(max_length=256)] | None = None,
        jsonb_path: Annotated[str, Parameter(max_length=128)] | None = None,
        jsonb_value: Annotated[str, Parameter(max_length=512)] | None = None,
    ) -> PaginatedResponse[AuditEntry]:
        """Query audit entries with optional filters.

        All filters are AND-combined.  Results are newest-first.

        JSONB filters (``jsonb_contains``, ``jsonb_key_exists``,
        ``jsonb_path`` + ``jsonb_value``) query the
        ``matched_rules`` column and require a Postgres backend.
        Returns 422 if JSONB params are used with a non-Postgres
        backend.

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
            jsonb_contains: JSON string for ``@>`` containment on
                ``matched_rules`` (Postgres only).
            jsonb_key_exists: Top-level key for ``?`` existence on
                ``matched_rules`` (Postgres only).
            jsonb_path: Dot-separated path for ``->>`` extraction
                on ``matched_rules`` (requires ``jsonb_value``).
            jsonb_value: Expected value at ``jsonb_path``.

        Returns:
            Paginated audit entries.

        Raises:
            ClientException: If *since* > *until*, JSONB params on
                non-Postgres backend, or invalid JSONB path.
        """
        self._validate_timestamps(since, until)

        has_jsonb = any((jsonb_contains, jsonb_key_exists, jsonb_path))

        if has_jsonb:
            return await self._jsonb_query(
                state=state,
                since=since,
                until=until,
                offset=offset,
                limit=limit,
                jsonb_contains=jsonb_contains,
                jsonb_key_exists=jsonb_key_exists,
                jsonb_path=jsonb_path,
                jsonb_value=jsonb_value,
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

    @staticmethod
    def _validate_timestamps(
        since: datetime | None,
        until: datetime | None,
    ) -> None:
        """Validate timezone and ordering of timestamp filters."""
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

    @staticmethod
    async def _jsonb_query(  # noqa: PLR0913
        *,
        state: State,
        since: datetime | None,
        until: datetime | None,
        offset: int,
        limit: int,
        jsonb_contains: str | None,
        jsonb_key_exists: str | None,
        jsonb_path: str | None,
        jsonb_value: str | None,
    ) -> PaginatedResponse[AuditEntry]:
        """Delegate JSONB-native queries to the persistence backend."""
        app_state = state.app_state
        repo = app_state.persistence.audit_entries

        if not isinstance(repo, JsonbQueryCapability):
            raise ClientException(
                status_code=422,
                detail="JSONB queries require the Postgres backend",
            )

        column = "matched_rules"

        if jsonb_contains is not None:
            try:
                value = json.loads(jsonb_contains)
            except json.JSONDecodeError as exc:
                raise ClientException(
                    detail=f"Invalid JSON in jsonb_contains: {exc}",
                ) from exc
            entries, total = await repo.query_jsonb_contains(
                column,
                value,
                since=since,
                until=until,
                limit=limit,
                offset=offset,
            )
        elif jsonb_key_exists is not None:
            entries, total = await repo.query_jsonb_key_exists(
                column,
                jsonb_key_exists,
                since=since,
                until=until,
                limit=limit,
                offset=offset,
            )
        elif jsonb_path is not None:
            if jsonb_value is None:
                raise ClientException(
                    detail="jsonb_path requires jsonb_value",
                )
            try:
                validate_jsonb_path(jsonb_path)
            except ValueError as exc:
                raise ClientException(
                    detail=str(exc),
                ) from exc
            entries, total = await repo.query_jsonb_path_equals(
                column,
                jsonb_path,
                jsonb_value,
                since=since,
                until=until,
                limit=limit,
                offset=offset,
            )
        else:
            msg = "No JSONB filter provided"
            raise ClientException(detail=msg)

        meta = PaginationMeta(total=total, offset=offset, limit=limit)
        logger.info(
            API_AUDIT_QUERIED,
            total=total,
            offset=offset,
            limit=limit,
            jsonb_query=True,
        )
        return PaginatedResponse[AuditEntry](
            data=entries,
            pagination=meta,
        )
