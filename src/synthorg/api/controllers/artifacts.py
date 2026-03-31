"""Artifact controller -- CRUD endpoints for artifact management."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from litestar import Controller, Response, get, post, put
from litestar.datastructures import State  # noqa: TC002
from litestar.enums import RequestEncodingType
from litestar.params import Body, Parameter

from synthorg.api.dto import ApiResponse, CreateArtifactRequest, PaginatedResponse
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.path_params import PathId  # noqa: TC001
from synthorg.core.artifact import Artifact
from synthorg.core.enums import ArtifactType
from synthorg.observability import get_logger
from synthorg.persistence.errors import (
    ArtifactStorageFullError,
    ArtifactTooLargeError,
    RecordNotFoundError,
)

logger = get_logger(__name__)

TaskIdFilter = Annotated[
    str | None,
    Parameter(
        required=False,
        description="Filter by originating task ID",
    ),
]

CreatedByFilter = Annotated[
    str | None,
    Parameter(
        required=False,
        description="Filter by creator agent ID",
    ),
]

TypeFilter = Annotated[
    str | None,
    Parameter(
        required=False,
        query="type",
        description="Filter by artifact type",
    ),
]


class ArtifactController(Controller):
    """CRUD controller for artifact management."""

    path = "/artifacts"
    tags = ("artifacts",)

    @get(guards=[require_read_access])
    async def list_artifacts(  # noqa: PLR0913
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
        task_id: TaskIdFilter = None,
        created_by: CreatedByFilter = None,
        type: TypeFilter = None,  # noqa: A002
    ) -> PaginatedResponse[Artifact]:
        """List artifacts with optional filters.

        Args:
            state: Application state.
            offset: Pagination offset.
            limit: Page size.
            task_id: Filter by originating task ID.
            created_by: Filter by creator agent ID.
            type: Filter by artifact type.

        Returns:
            Paginated list of artifacts.
        """
        parsed_type: ArtifactType | None = None
        if type is not None:
            parsed_type = ArtifactType(type)

        repo = state.app_state.persistence.artifacts
        artifacts = await repo.list_artifacts(
            task_id=task_id,
            created_by=created_by,
            artifact_type=parsed_type,
        )
        page, meta = paginate(artifacts, offset=offset, limit=limit)
        return PaginatedResponse[Artifact](data=page, pagination=meta)

    @get("/{artifact_id:str}", guards=[require_read_access])
    async def get_artifact(
        self,
        state: State,
        artifact_id: PathId,
    ) -> Response[ApiResponse[Artifact]]:
        """Get an artifact by ID.

        Args:
            state: Application state.
            artifact_id: Artifact identifier.

        Returns:
            The artifact metadata, or 404 if not found.
        """
        repo = state.app_state.persistence.artifacts
        artifact = await repo.get(artifact_id)
        if artifact is None:
            return Response(
                content=ApiResponse[Artifact](
                    error=f"Artifact {artifact_id!r} not found",
                ),
                status_code=404,
            )
        return Response(
            content=ApiResponse[Artifact](data=artifact),
            status_code=200,
        )

    @post(guards=[require_write_access])
    async def create_artifact(
        self,
        state: State,
        data: CreateArtifactRequest,
    ) -> Response[ApiResponse[Artifact]]:
        """Create a new artifact.

        Args:
            state: Application state.
            data: Artifact creation payload.

        Returns:
            The created artifact with generated ID.
        """
        artifact = Artifact(
            id=f"artifact-{uuid.uuid4().hex[:12]}",
            type=data.type,
            path=data.path,
            task_id=data.task_id,
            created_by=data.created_by,
            description=data.description,
            content_type=data.content_type,
            created_at=datetime.now(UTC),
        )
        repo = state.app_state.persistence.artifacts
        await repo.save(artifact)
        return Response(
            content=ApiResponse[Artifact](data=artifact),
            status_code=201,
        )

    @put(
        "/{artifact_id:str}/content",
        guards=[require_write_access],
        media_type="application/json",
    )
    async def upload_content(
        self,
        state: State,
        artifact_id: PathId,
        data: Annotated[
            bytes,
            Body(media_type=RequestEncodingType.MULTI_PART),
        ],
    ) -> Response[ApiResponse[Artifact]]:
        """Upload binary content for an artifact.

        Validates size limits before storing.

        Args:
            state: Application state.
            artifact_id: Artifact identifier.
            data: Binary content.

        Returns:
            Updated artifact metadata with size_bytes set.
        """
        repo = state.app_state.persistence.artifacts
        artifact = await repo.get(artifact_id)
        if artifact is None:
            return Response(
                content=ApiResponse[Artifact](
                    error=f"Artifact {artifact_id!r} not found",
                ),
                status_code=404,
            )

        storage = state.app_state.artifact_storage
        try:
            size = await storage.store(artifact_id, data)
        except ArtifactTooLargeError as exc:
            return Response(
                content=ApiResponse[Artifact](error=str(exc)),
                status_code=413,
            )
        except ArtifactStorageFullError as exc:
            return Response(
                content=ApiResponse[Artifact](error=str(exc)),
                status_code=507,
            )

        updated = artifact.model_copy(
            update={
                "size_bytes": size,
                "content_type": artifact.content_type or "application/octet-stream",
            },
        )
        await repo.save(updated)
        return Response(
            content=ApiResponse[Artifact](data=updated),
            status_code=200,
        )

    @get(
        "/{artifact_id:str}/content",
        guards=[require_read_access],
        media_type="application/octet-stream",
    )
    async def download_content(
        self,
        state: State,
        artifact_id: PathId,
    ) -> Response[bytes]:
        """Download binary content for an artifact.

        Args:
            state: Application state.
            artifact_id: Artifact identifier.

        Returns:
            Binary content with appropriate content type.
        """
        repo = state.app_state.persistence.artifacts
        artifact = await repo.get(artifact_id)
        if artifact is None:
            return Response(
                content=b"",
                status_code=404,
                media_type="application/octet-stream",
            )

        storage = state.app_state.artifact_storage
        try:
            content = await storage.retrieve(artifact_id)
        except RecordNotFoundError:
            return Response(
                content=b"",
                status_code=404,
                media_type="application/octet-stream",
            )

        return Response(
            content=content,
            status_code=200,
            media_type=artifact.content_type or "application/octet-stream",
        )
