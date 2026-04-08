"""Role version history controller -- list, get."""

import asyncio
from typing import Annotated

from litestar import Controller, Response, get
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import (
    ApiResponse,
    PaginatedResponse,
    PaginationMeta,
)
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset  # noqa: TC001
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
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 20,
    ) -> Response[PaginatedResponse[SnapshotT]]:
        """List version history for a specific role definition."""
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
        meta = PaginationMeta(total=total, offset=offset, limit=limit)
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
