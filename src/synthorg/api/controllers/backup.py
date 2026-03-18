"""Backup controller -- admin endpoints for backup/restore operations."""

from litestar import Controller, delete, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
)

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_write_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.backup.errors import (
    BackupInProgressError,
    BackupNotFoundError,
    ManifestError,
    RestoreError,
)
from synthorg.backup.models import (
    BackupInfo,
    BackupManifest,
    BackupTrigger,
    RestoreRequest,
    RestoreResponse,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)


class BackupController(Controller):
    """Admin endpoints for backup and restore operations."""

    path = "/admin/backup"
    tags = ("admin", "backup")
    guards = [require_write_access]  # noqa: RUF012

    @post()
    async def create_backup(
        self,
        state: State,
    ) -> ApiResponse[BackupManifest]:
        """Trigger a manual backup.

        Args:
            state: Application state.

        Returns:
            Manifest of the created backup.
        """
        app_state: AppState = state.app_state
        try:
            manifest = await app_state.backup_service.create_backup(
                BackupTrigger.MANUAL,
            )
        except BackupInProgressError as exc:
            raise ClientException(
                str(exc),
                status_code=409,
            ) from exc
        return ApiResponse(data=manifest)

    @get("/list")
    async def list_backups(
        self,
        state: State,
    ) -> ApiResponse[tuple[BackupInfo, ...]]:
        """List all available backups.

        Args:
            state: Application state.

        Returns:
            List of backup info summaries.
        """
        app_state: AppState = state.app_state
        backups = await app_state.backup_service.list_backups()
        return ApiResponse(data=backups)

    @get("/{backup_id:str}")
    async def get_backup(
        self,
        state: State,
        backup_id: str,
    ) -> ApiResponse[BackupManifest]:
        """Get details of a specific backup.

        Args:
            state: Application state.
            backup_id: Backup identifier.

        Returns:
            Full backup manifest.
        """
        app_state: AppState = state.app_state
        try:
            manifest = await app_state.backup_service.get_backup(backup_id)
        except BackupNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc
        return ApiResponse(data=manifest)

    @delete("/{backup_id:str}", status_code=200)
    async def delete_backup(
        self,
        state: State,
        backup_id: str,
    ) -> ApiResponse[None]:
        """Delete a backup.

        Args:
            state: Application state.
            backup_id: Backup identifier.

        Returns:
            Empty success response.
        """
        app_state: AppState = state.app_state
        try:
            await app_state.backup_service.delete_backup(backup_id)
        except BackupNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc
        return ApiResponse(data=None)

    @post("/restore")
    async def restore_backup(
        self,
        state: State,
        data: RestoreRequest,
    ) -> ApiResponse[RestoreResponse]:
        """Restore from a backup.

        Requires ``confirm=true`` in the request body as a safety gate.

        Args:
            state: Application state.
            data: Restore request with backup_id and confirmation.

        Returns:
            Restore response with safety backup ID.
        """
        if not data.confirm:
            msg = "Restore requires confirm=true"
            raise ClientException(msg, status_code=400)

        app_state: AppState = state.app_state
        try:
            response = await app_state.backup_service.restore_from_backup(
                data.backup_id,
                components=data.components,
            )
        except BackupNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc
        except ManifestError as exc:
            raise ClientException(str(exc), status_code=422) from exc
        except BackupInProgressError as exc:
            raise ClientException(str(exc), status_code=409) from exc
        except RestoreError as exc:
            raise InternalServerException(str(exc)) from exc
        return ApiResponse(data=response)
