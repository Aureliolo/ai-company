"""Role version history controller -- list, get."""

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
from synthorg.core.role import Role
from synthorg.observability import get_logger
from synthorg.observability.events.versioning import (
    VERSION_LISTED,
    VERSION_NOT_FOUND,
)
from synthorg.versioning import VersionSnapshot

logger = get_logger(__name__)

SnapshotT = VersionSnapshot[Role]


class RoleVersionController(Controller):
    """Version history for role definitions (per-role granularity)."""

    path = "/roles"
    tags = ("roles",)

    @get("/{role_name:str}/versions", guards=[require_read_access])
    async def list_versions(
        self,
        state: State,
        role_name: str,
        cursor: CursorParam = None,
        limit: CursorLimit = 20,
    ) -> Response[PaginatedResponse[SnapshotT]]:
        """List version history for a specific role definition."""
        secret = state.app_state.cursor_secret
        offset = 0 if cursor is None else decode_cursor(cursor, secret=secret)
        repo = state.app_state.persistence.role_versions
        versions, total = await asyncio.gather(
            repo.list_versions(role_name, limit=limit, offset=offset),
            repo.count_versions(role_name),
        )
        logger.debug(
            VERSION_LISTED,
            entity_type="Role",
            entity_id=role_name,
            count=len(versions),
        )
        next_offset = offset + len(versions)

        # Guard against snapshot drift between ``list_versions`` and
        # ``count_versions``: if the list read came back short of the
        # requested page but the count still claims more items exist,
        # ``next_offset`` would point at the same row the current
        # cursor already decodes to, and the client would loop on
        # that page forever.  Require the page to have at least one
        # row AND the offset to have advanced before claiming more
        # pages exist.
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
        "/{role_name:str}/versions/{version_num:int}",
        guards=[require_read_access],
    )
    async def get_version(
        self,
        state: State,
        role_name: str,
        version_num: Annotated[int, Parameter(ge=1)],
    ) -> Response[ApiResponse[SnapshotT]]:
        """Get a specific role version snapshot."""
        repo = state.app_state.persistence.role_versions
        version = await repo.get_version(role_name, version_num)
        if version is None:
            logger.warning(
                VERSION_NOT_FOUND,
                entity_type="Role",
                entity_id=role_name,
                version=version_num,
            )
            return Response(
                content=ApiResponse[SnapshotT](
                    error=f"Version {version_num} not found for role {role_name!r}",
                ),
                status_code=404,
            )
        return Response(
            content=ApiResponse[SnapshotT](data=version),
        )
