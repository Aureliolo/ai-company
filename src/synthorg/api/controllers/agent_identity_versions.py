"""Agent identity version history API -- list, get, diff, rollback."""

from typing import Annotated, Any

from litestar import Controller, Request, Response, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.controllers._workflow_helpers import get_auth_user_id
from synthorg.api.dto import (
    ApiResponse,
    PaginatedResponse,
    PaginationMeta,
    RollbackAgentIdentityRequest,
)
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset  # noqa: TC001
from synthorg.api.path_params import PathId  # noqa: TC001
from synthorg.core.agent import AgentIdentity
from synthorg.engine.identity.diff import AgentIdentityDiff, compute_diff
from synthorg.hr.errors import AgentNotFoundError
from synthorg.observability import get_logger
from synthorg.observability.events.agent_identity_version import (
    AGENT_IDENTITY_DIFF_COMPUTED,
    AGENT_IDENTITY_INVALID_REQUEST,
    AGENT_IDENTITY_ROLLBACK_FAILED,
    AGENT_IDENTITY_ROLLED_BACK,
    AGENT_IDENTITY_VERSION_FETCHED,
    AGENT_IDENTITY_VERSION_LISTED,
    AGENT_IDENTITY_VERSION_NOT_FOUND,
)
from synthorg.persistence.version_repo import VersionRepository  # noqa: TC001
from synthorg.versioning import VersionSnapshot

logger = get_logger(__name__)

SnapshotT = VersionSnapshot[AgentIdentity]


async def _fetch_version_pair(
    version_repo: VersionRepository[AgentIdentity],
    agent_id: str,
    from_version: int,
    to_version: int,
) -> tuple[SnapshotT, SnapshotT] | Response[ApiResponse[AgentIdentityDiff]]:
    """Fetch two snapshots or return a 404 response."""
    old = await version_repo.get_version(agent_id, from_version)
    if old is None:
        logger.warning(
            AGENT_IDENTITY_VERSION_NOT_FOUND,
            agent_id=agent_id,
            version=from_version,
        )
        return Response(
            content=ApiResponse[AgentIdentityDiff](
                error=f"Version {from_version} not found",
            ),
            status_code=404,
        )
    new = await version_repo.get_version(agent_id, to_version)
    if new is None:
        logger.warning(
            AGENT_IDENTITY_VERSION_NOT_FOUND,
            agent_id=agent_id,
            version=to_version,
        )
        return Response(
            content=ApiResponse[AgentIdentityDiff](
                error=f"Version {to_version} not found",
            ),
            status_code=404,
        )
    return old, new


class AgentIdentityVersionController(Controller):
    """Version history, diff, and rollback for agent identities."""

    path = "/agents"
    tags = ("agents",)

    @get("/{agent_id:str}/versions", guards=[require_read_access])
    async def list_versions(
        self,
        state: State,
        agent_id: PathId,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 20,
    ) -> Response[PaginatedResponse[SnapshotT]]:
        """List version history for an agent identity."""
        version_repo = state.app_state.persistence.identity_versions
        versions = await version_repo.list_versions(
            agent_id,
            limit=limit,
            offset=offset,
        )
        total = await version_repo.count_versions(agent_id)
        logger.debug(
            AGENT_IDENTITY_VERSION_LISTED,
            agent_id=agent_id,
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
        "/{agent_id:str}/versions/diff",
        guards=[require_read_access],
    )
    async def get_diff(
        self,
        state: State,
        agent_id: PathId,
        from_version: Annotated[
            int,
            Parameter(
                required=True,
                ge=1,
                description="Source version",
            ),
        ],
        to_version: Annotated[
            int,
            Parameter(
                required=True,
                ge=1,
                description="Target version",
            ),
        ],
    ) -> Response[ApiResponse[AgentIdentityDiff]]:
        """Compute diff between two agent identity versions."""
        if from_version == to_version:
            logger.warning(
                AGENT_IDENTITY_INVALID_REQUEST,
                agent_id=agent_id,
                error="from_version and to_version must differ",
            )
            return Response(
                content=ApiResponse[AgentIdentityDiff](
                    error="from_version and to_version must differ",
                ),
                status_code=400,
            )
        if from_version >= to_version:
            logger.warning(
                AGENT_IDENTITY_INVALID_REQUEST,
                agent_id=agent_id,
                error="from_version must be less than to_version",
            )
            return Response(
                content=ApiResponse[AgentIdentityDiff](
                    error="from_version must be less than to_version",
                ),
                status_code=400,
            )

        version_repo = state.app_state.persistence.identity_versions
        result = await _fetch_version_pair(
            version_repo,
            agent_id,
            from_version,
            to_version,
        )
        if isinstance(result, Response):
            return result
        old, new = result

        diff = compute_diff(
            agent_id=agent_id,
            old_snapshot=old.snapshot,
            new_snapshot=new.snapshot,
            from_version=from_version,
            to_version=to_version,
        )
        logger.debug(
            AGENT_IDENTITY_DIFF_COMPUTED,
            agent_id=agent_id,
            from_version=from_version,
            to_version=to_version,
        )
        return Response(
            content=ApiResponse[AgentIdentityDiff](data=diff),
        )

    @get(
        "/{agent_id:str}/versions/{version_num:int}",
        guards=[require_read_access],
    )
    async def get_version(
        self,
        state: State,
        agent_id: PathId,
        version_num: Annotated[int, Parameter(ge=1)],
    ) -> Response[ApiResponse[SnapshotT]]:
        """Get a specific agent identity version snapshot."""
        version_repo = state.app_state.persistence.identity_versions
        version = await version_repo.get_version(agent_id, version_num)
        if version is None:
            logger.warning(
                AGENT_IDENTITY_VERSION_NOT_FOUND,
                agent_id=agent_id,
                version=version_num,
            )
            return Response(
                content=ApiResponse[SnapshotT](
                    error=f"Version {version_num} not found",
                ),
                status_code=404,
            )
        logger.debug(
            AGENT_IDENTITY_VERSION_FETCHED,
            agent_id=agent_id,
            version=version_num,
        )
        return Response(content=ApiResponse[SnapshotT](data=version))

    @post(
        "/{agent_id:str}/versions/rollback",
        guards=[require_write_access],
        status_code=200,
    )
    async def rollback_identity(
        self,
        request: Request[Any, Any, Any],
        state: State,
        agent_id: PathId,
        data: RollbackAgentIdentityRequest,
    ) -> Response[ApiResponse[AgentIdentity]]:
        """Roll the agent's identity back to ``target_version``.

        Produces a new version snapshot (N+1) whose content hash equals the
        restored snapshot's content hash, preserving the full audit trail.
        """
        version_repo = state.app_state.persistence.identity_versions
        target = await version_repo.get_version(agent_id, data.target_version)
        if target is None:
            logger.warning(
                AGENT_IDENTITY_VERSION_NOT_FOUND,
                agent_id=agent_id,
                version=data.target_version,
            )
            return Response(
                content=ApiResponse[AgentIdentity](
                    error=f"Target version {data.target_version} not found",
                ),
                status_code=404,
            )

        actor = get_auth_user_id(request)
        try:
            rolled_back = await state.app_state.agent_registry.evolve_identity(
                agent_id,
                target.snapshot,
                evolution_rationale=(f"rollback to v{data.target_version} by {actor}"),
            )
        except AgentNotFoundError:
            logger.warning(
                AGENT_IDENTITY_ROLLBACK_FAILED,
                agent_id=agent_id,
                error="agent not found",
            )
            return Response(
                content=ApiResponse[AgentIdentity](error="Agent not found"),
                status_code=404,
            )

        logger.info(
            AGENT_IDENTITY_ROLLED_BACK,
            agent_id=agent_id,
            target_version=data.target_version,
        )
        return Response(content=ApiResponse[AgentIdentity](data=rolled_back))
