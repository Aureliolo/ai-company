"""Budget config version history controller -- list, get."""

import asyncio
from typing import Annotated

from litestar import Controller, Response, get
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.cursor import decode_cursor, encode_cursor
from synthorg.api.dto import (
    ApiResponse,
    PaginatedResponse,
    PaginationMeta,
)
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import CursorLimit, CursorParam  # noqa: TC001
from synthorg.budget.config import BudgetConfig
from synthorg.observability import get_logger
from synthorg.observability.events.versioning import (
    VERSION_LISTED,
    VERSION_NOT_FOUND,
)
from synthorg.versioning import VersionSnapshot

logger = get_logger(__name__)

SnapshotT = VersionSnapshot[BudgetConfig]

#: Entity ID for the singleton budget configuration.
_ENTITY_ID = "default"


class BudgetConfigVersionController(Controller):
    """Version history for budget configuration."""

    path = "/budget/config"
    tags = ("budget",)

    @get("/versions", guards=[require_read_access])
    async def list_versions(
        self,
        state: State,
        cursor: CursorParam = None,
        limit: CursorLimit = 20,
    ) -> Response[PaginatedResponse[SnapshotT]]:
        """List version history for budget configuration."""
        secret = state.app_state.cursor_secret
        offset = 0 if cursor is None else decode_cursor(cursor, secret=secret)
        repo = state.app_state.persistence.budget_config_versions
        versions, total = await asyncio.gather(
            repo.list_versions(_ENTITY_ID, limit=limit, offset=offset),
            repo.count_versions(_ENTITY_ID),
        )
        logger.debug(
            VERSION_LISTED,
            entity_type="BudgetConfig",
            entity_id=_ENTITY_ID,
            count=len(versions),
        )
        next_offset = offset + len(versions)

        # Snapshot-drift guard (see role_versions.py for the full
        # rationale): short / empty pages cannot advance the cursor.
        has_more = len(versions) > 0 and next_offset > offset and next_offset < total

        next_cursor = encode_cursor(next_offset, secret=secret) if has_more else None

        meta = PaginationMeta(
            limit=limit,
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            offset=offset,
        )
        return Response(
            content=PaginatedResponse[SnapshotT](
                data=versions,
                pagination=meta,
            ),
        )

    @get(
        "/versions/{version_num:int}",
        guards=[require_read_access],
    )
    async def get_version(
        self,
        state: State,
        version_num: Annotated[int, Parameter(ge=1)],
    ) -> Response[ApiResponse[SnapshotT]]:
        """Get a specific budget config version snapshot."""
        repo = state.app_state.persistence.budget_config_versions
        version = await repo.get_version(_ENTITY_ID, version_num)
        if version is None:
            logger.warning(
                VERSION_NOT_FOUND,
                entity_type="BudgetConfig",
                entity_id=_ENTITY_ID,
                version=version_num,
            )
            return Response(
                content=ApiResponse[SnapshotT](
                    error=f"Version {version_num} not found",
                ),
                status_code=404,
            )
        return Response(
            content=ApiResponse[SnapshotT](data=version),
        )
