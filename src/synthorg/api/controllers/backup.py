"""Backup controller -- admin endpoints for backup/restore operations.

All endpoints require write access.
"""

from litestar import Controller, delete, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
)
from litestar.status_codes import HTTP_204_NO_CONTENT

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_write_access
from synthorg.api.path_params import PathId  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.backup.errors import (
    BackupError,
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
from synthorg.observability.events.backup import (
    BACKUP_FAILED,
    BACKUP_NOT_FOUND,
    BACKUP_RESTORE_FAILED,
)

logger = get_logger(__name__)


class BackupController(Controller):
    """Admin endpoints for backup and restore operations.

    All endpoints require write access.
    """

    path = "/admin/backups"
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
            logger.warning(
                BACKUP_FAILED,
                error=str(exc),
            )
            raise ClientException(
                str(exc),
                status_code=409,
            ) from exc
        except BackupError as exc:
            logger.error(
                BACKUP_FAILED,
                error=str(exc),
                exc_info=True,
            )
            msg = "Backup operation failed"
            raise InternalServerException(msg) from exc
        return ApiResponse(data=manifest)

    @get()
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
        try:
            backups = await app_state.backup_service.list_backups()
        except BackupError as exc:
            logger.error(
                BACKUP_FAILED,
                error=str(exc),
                exc_info=True,
            )
            msg = "Failed to list backups"
            raise InternalServerException(msg) from exc
        return ApiResponse(data=backups)

    @get("/{backup_id:str}")
    async def get_backup(
        self,
        state: State,
        backup_id: PathId,
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
            logger.warning(
                BACKUP_NOT_FOUND,
                backup_id=backup_id,
            )
            raise NotFoundException(str(exc)) from exc
        return ApiResponse(data=manifest)

    @delete("/{backup_id:str}", status_code=HTTP_204_NO_CONTENT)
    async def delete_backup(
        self,
        state: State,
        backup_id: PathId,
    ) -> None:
        """Delete a backup.

        Args:
            state: Application state.
            backup_id: Backup identifier.
        """
        app_state: AppState = state.app_state
        try:
            await app_state.backup_service.delete_backup(backup_id)
        except BackupNotFoundError as exc:
            logger.warning(
                BACKUP_NOT_FOUND,
                backup_id=backup_id,
            )
            raise NotFoundException(str(exc)) from exc

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

        Raises:
            ClientException: If confirm is false (400), backup in
                progress (409), or manifest invalid (422).
            NotFoundException: If the backup does not exist.
            InternalServerException: If the restore fails.
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
            logger.warning(
                BACKUP_NOT_FOUND,
                backup_id=data.backup_id,
            )
            raise NotFoundException(str(exc)) from exc
        except ManifestError as exc:
            logger.warning(
                BACKUP_RESTORE_FAILED,
                backup_id=data.backup_id,
                error=str(exc),
            )
            raise ClientException(str(exc), status_code=422) from exc
        except BackupInProgressError as exc:
            logger.warning(
                BACKUP_FAILED,
                backup_id=data.backup_id,
                error=str(exc),
            )
            raise ClientException(str(exc), status_code=409) from exc
        except RestoreError as exc:
            logger.error(
                BACKUP_RESTORE_FAILED,
                backup_id=data.backup_id,
                error=str(exc),
                exc_info=True,
            )
            msg = "Restore operation failed"
            raise InternalServerException(msg) from exc
        return ApiResponse(data=response)
