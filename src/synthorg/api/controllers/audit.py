"""Audit log query controller.

Exposes ``GET /security/audit`` for querying the security
evaluation audit trail with filtering and pagination.

JSONB-native queries (containment, key existence) are available
when the Postgres persistence backend is active.
"""

import asyncio
import json
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
from synthorg.persistence.jsonb_capability import JsonbQueryCapability
from synthorg.security.models import AuditEntry
from synthorg.settings.enums import SettingNamespace

logger = get_logger(__name__)

_MAX_AUDIT_QUERY = 10_000
"""Fallback cap applied when no settings resolver is wired in."""

# Module-level log-once guard for the settings-resolution fallback;
# see ``activities._resolve_lifecycle_cap`` for the rationale.
_audit_cap_fallback_logged: bool = False


async def _resolve_audit_cap(state: State) -> int:
    """Resolve the active audit-query cap, falling back to the constant.

    A settings outage or malformed value must not fail the endpoint;
    the fallback constant keeps the DB-side ``LIMIT`` bounded. Warnings
    are log-once per run of failures (cleared on recovery).
    """
    global _audit_cap_fallback_logged  # noqa: PLW0603
    app_state = state.app_state
    if not app_state.has_config_resolver:
        return _MAX_AUDIT_QUERY
    try:
        result: int = await app_state.config_resolver.get_int(
            SettingNamespace.API.value, "max_audit_records_per_query"
        )
    except asyncio.CancelledError:
        raise
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        if not _audit_cap_fallback_logged:
            logger.warning(
                API_VALIDATION_FAILED,
                error=(
                    "failed to resolve max_audit_records_per_query;"
                    f" using fallback ({type(exc).__name__})"
                ),
                cap=_MAX_AUDIT_QUERY,
            )
            _audit_cap_fallback_logged = True
        return _MAX_AUDIT_QUERY
    _audit_cap_fallback_logged = False
    return result


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
    ) -> PaginatedResponse[AuditEntry]:
        """Query audit entries with optional filters.

        All filters are AND-combined.  Results are newest-first.

        JSONB filters (``jsonb_contains``, ``jsonb_key_exists``)
        query the ``matched_rules`` column and require a Postgres
        backend.  Returns 422 if JSONB params are used with a
        non-Postgres backend.  When both JSONB and standard filters
        are provided, JSONB results are post-filtered by standard
        criteria.

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

        Returns:
            Paginated audit entries.

        Raises:
            ClientException: If *since* > *until* or JSONB params
                on non-Postgres backend.
        """
        self._validate_timestamps(since, until)

        has_jsonb = any(p is not None for p in (jsonb_contains, jsonb_key_exists))

        if has_jsonb:
            return await self._jsonb_query(
                state=state,
                agent_id=agent_id,
                tool_name=tool_name,
                action_type=action_type,
                verdict=verdict,
                since=since,
                until=until,
                offset=offset,
                limit=limit,
                jsonb_contains=jsonb_contains,
                jsonb_key_exists=jsonb_key_exists,
            )

        app_state = state.app_state
        audit_cap = await _resolve_audit_cap(state)
        entries = app_state.audit_log.query(
            agent_id=agent_id,
            tool_name=tool_name,
            action_type=action_type,
            verdict=verdict,
            since=since,
            until=until,
            limit=audit_cap,
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
        agent_id: str | None,
        tool_name: str | None,
        action_type: str | None,
        verdict: str | None,
        since: datetime | None,
        until: datetime | None,
        offset: int,
        limit: int,
        jsonb_contains: str | None,
        jsonb_key_exists: str | None,
    ) -> PaginatedResponse[AuditEntry]:
        """Delegate JSONB-native queries to the persistence backend.

        Standard filters (agent_id, tool_name, etc.) are applied as
        post-filters on the JSONB result set so all filters remain
        AND-combined.
        """
        app_state = state.app_state
        repo = app_state.persistence.audit_entries

        if not isinstance(repo, JsonbQueryCapability):
            logger.warning(
                API_VALIDATION_FAILED,
                reason="jsonb_query_unsupported_backend",
            )
            raise ClientException(
                status_code=422,
                detail="JSONB queries require the Postgres backend",
            )

        if jsonb_contains is not None and jsonb_key_exists is not None:
            logger.warning(
                API_VALIDATION_FAILED,
                reason="multiple_jsonb_predicates",
            )
            raise ClientException(
                status_code=422,
                detail="Provide only one of jsonb_contains or jsonb_key_exists",
            )

        column = "matched_rules"
        audit_cap = await _resolve_audit_cap(state)

        if jsonb_contains is not None:
            try:
                value = json.loads(jsonb_contains)
            except json.JSONDecodeError as exc:
                preview = jsonb_contains[:256]
                logger.warning(
                    API_VALIDATION_FAILED,
                    reason="invalid_jsonb_contains_json",
                    input_length=len(jsonb_contains),
                    input_preview=preview,
                )
                raise ClientException(
                    detail="Invalid JSON in jsonb_contains parameter",
                ) from exc
            if not isinstance(value, (list, dict)):
                logger.warning(
                    API_VALIDATION_FAILED,
                    reason="jsonb_contains_not_collection",
                )
                raise ClientException(
                    detail="jsonb_contains must be a JSON array or object",
                )
            entries, _ = await repo.query_jsonb_contains(
                column,
                value,
                since=since,
                until=until,
                limit=audit_cap,
                offset=0,
            )
        elif jsonb_key_exists is not None:
            entries, _ = await repo.query_jsonb_key_exists(
                column,
                jsonb_key_exists,
                since=since,
                until=until,
                limit=audit_cap,
                offset=0,
            )
        else:
            logger.warning(
                API_VALIDATION_FAILED,
                reason="no_jsonb_filter",
            )
            raise ClientException(detail="No JSONB filter provided")

        filtered = _apply_standard_filters(
            entries,
            agent_id=agent_id,
            tool_name=tool_name,
            action_type=action_type,
            verdict=verdict,
        )
        page, meta = paginate(filtered, offset=offset, limit=limit)
        logger.info(
            API_AUDIT_QUERIED,
            total=meta.total,
            offset=meta.offset,
            limit=meta.limit,
            jsonb_query=True,
        )
        return PaginatedResponse[AuditEntry](
            data=page,
            pagination=meta,
        )


def _apply_standard_filters(
    entries: tuple[AuditEntry, ...],
    *,
    agent_id: str | None,
    tool_name: str | None,
    action_type: str | None,
    verdict: str | None,
) -> tuple[AuditEntry, ...]:
    """Post-filter JSONB results by standard audit criteria."""
    if all(f is None for f in (agent_id, tool_name, action_type, verdict)):
        return entries
    result: list[AuditEntry] = []
    for e in entries:
        if agent_id is not None and e.agent_id != agent_id:
            continue
        if tool_name is not None and e.tool_name != tool_name:
            continue
        if action_type is not None and e.action_type != action_type:
            continue
        if verdict is not None and e.verdict != verdict:
            continue
        result.append(e)
    return tuple(result)
