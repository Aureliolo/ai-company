"""Evaluation config version history controller -- list, get."""

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
from synthorg.hr.evaluation.config import EvaluationConfig
from synthorg.observability import get_logger
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
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 20,
    ) -> Response[PaginatedResponse[SnapshotT]]:
        """List version history for evaluation configuration."""
        repo = state.app_state.persistence.evaluation_config_versions
        versions = await repo.list_versions(
            _ENTITY_ID,
            limit=limit,
            offset=offset,
        )
        total = await repo.count_versions(_ENTITY_ID)
        meta = PaginationMeta(total=total, offset=offset, limit=limit)
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
            return Response(
                content=ApiResponse[SnapshotT](
                    error=f"Version {version_num} not found",
                ),
                status_code=404,
            )
        return Response(
            content=ApiResponse[SnapshotT](data=version),
        )
