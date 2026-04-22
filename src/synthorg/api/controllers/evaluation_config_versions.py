"""Evaluation config version history controller -- list, get."""

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
from synthorg.hr.evaluation.config import EvaluationConfig
from synthorg.observability import get_logger
from synthorg.observability.events.versioning import (
    VERSION_LISTED,
    VERSION_NOT_FOUND,
)
from synthorg.versioning import VersionSnapshot

logger = get_logger(__name__)

SnapshotT = VersionSnapshot[EvaluationConfig]

#: Entity ID for the singleton evaluation configuration.
_ENTITY_ID = "default"


class EvaluationConfigVersionController(Controller):
    """Version history for evaluation configuration."""

    path = "/evaluation/config"
    tags = ("evaluation",)

    @get("/versions", guards=[require_read_access])
    async def list_versions(
        self,
        state: State,
        cursor: CursorParam = None,
        limit: CursorLimit = 20,
    ) -> Response[PaginatedResponse[SnapshotT]]:
        """List version history for evaluation configuration."""
        secret = state.app_state.cursor_secret
        offset = 0 if cursor is None else decode_cursor(cursor, secret=secret)
        repo = state.app_state.persistence.evaluation_config_versions
        versions, total = await asyncio.gather(
            repo.list_versions(_ENTITY_ID, limit=limit, offset=offset),
            repo.count_versions(_ENTITY_ID),
        )
        logger.debug(
            VERSION_LISTED,
            entity_type="EvaluationConfig",
            entity_id=_ENTITY_ID,
            count=len(versions),
        )
        next_offset = offset + len(versions)

        has_more = next_offset < total

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
        """Get a specific evaluation config version snapshot."""
        repo = state.app_state.persistence.evaluation_config_versions
        version = await repo.get_version(_ENTITY_ID, version_num)
        if version is None:
            logger.warning(
                VERSION_NOT_FOUND,
                entity_type="EvaluationConfig",
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
