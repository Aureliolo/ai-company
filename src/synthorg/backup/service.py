"""Backup service -- central orchestrator for backup/restore operations."""

import asyncio
import hashlib
import json
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from synthorg import __version__
from synthorg.backup.errors import (
    BackupInProgressError,
    BackupNotFoundError,
    ManifestError,
    RestoreError,
)
from synthorg.backup.models import (
    BackupComponent,
    BackupInfo,
    BackupManifest,
    BackupTrigger,
    RestoreResponse,
)
from synthorg.backup.retention import RetentionManager
from synthorg.backup.scheduler import BackupScheduler
from synthorg.observability import get_logger
from synthorg.observability.events.backup import (
    BACKUP_COMPLETED,
    BACKUP_DELETED,
    BACKUP_FAILED,
    BACKUP_IN_PROGRESS,
    BACKUP_LISTED,
    BACKUP_MANIFEST_INVALID,
    BACKUP_MANIFEST_WRITTEN,
    BACKUP_NOT_FOUND,
    BACKUP_RESTORE_COMPLETED,
    BACKUP_RESTORE_FAILED,
    BACKUP_RESTORE_ROLLBACK,
    BACKUP_RESTORE_STARTED,
    BACKUP_STARTED,
)

if TYPE_CHECKING:
    from synthorg.backup.config import BackupConfig
    from synthorg.backup.handlers.protocol import ComponentHandler

logger = get_logger(__name__)


def _not_found_msg(backup_id: str) -> str:
    """Build a 'not found' error message for a backup ID."""
    return f"Backup not found: {backup_id}"


class BackupService:
    """Central orchestrator for backup and restore operations.

    Coordinates component handlers, manages manifests, handles
    compression, and delegates to the scheduler and retention
    manager.

    Args:
        config: Backup configuration.
        handlers: Component handlers keyed by component enum.
        schema_version: Current persistence DB schema version.
    """

    def __init__(
        self,
        config: BackupConfig,
        handlers: dict[BackupComponent, ComponentHandler],
        schema_version: int,
    ) -> None:
        self._config = config
        self._handlers = handlers
        self._schema_version = schema_version
        self._backup_lock = asyncio.Lock()
        self._backup_path = Path(config.path)
        self._retention = RetentionManager(config.retention, self._backup_path)
        self._scheduler = BackupScheduler(self, config.schedule_hours)

    @property
    def scheduler(self) -> BackupScheduler:
        """Return the backup scheduler instance."""
        return self._scheduler

    async def start(self) -> None:
        """Start the backup scheduler if backups are enabled."""
        if self._config.enabled:
            self._scheduler.start()

    async def stop(self) -> None:
        """Stop the backup scheduler."""
        await self._scheduler.stop()

    async def create_backup(
        self,
        trigger: BackupTrigger,
        components: tuple[BackupComponent, ...] | None = None,
        *,
        compress: bool | None = None,
    ) -> BackupManifest:
        """Create a new backup.

        Args:
            trigger: What initiated the backup.
            components: Components to back up (defaults to config.include).
            compress: Whether to compress (defaults to config.compression,
                forced ``False`` for shutdown backups).

        Returns:
            Manifest of the created backup.

        Raises:
            BackupInProgressError: If another backup is in progress.
        """
        if self._backup_lock.locked():
            logger.warning(BACKUP_IN_PROGRESS, trigger=trigger.value)
            msg = "A backup is already in progress"
            raise BackupInProgressError(msg)

        async with self._backup_lock:
            return await self._do_backup(trigger, components, compress=compress)

    async def _do_backup(
        self,
        trigger: BackupTrigger,
        components: tuple[BackupComponent, ...] | None = None,
        *,
        compress: bool | None = None,
    ) -> BackupManifest:
        """Execute the backup (called under lock)."""
        backup_id = uuid4().hex[:12]
        timestamp = datetime.now(UTC).isoformat()
        effective_components = components or tuple(
            BackupComponent(c) for c in self._config.include
        )

        # Shutdown backups skip compression for speed
        if compress is None:
            use_compression = (
                self._config.compression if trigger != BackupTrigger.SHUTDOWN else False
            )
        else:
            use_compression = compress

        dir_name = f"{backup_id}_{trigger.value}"
        backup_dir = self._backup_path / dir_name

        logger.info(
            BACKUP_STARTED,
            backup_id=backup_id,
            trigger=trigger.value,
            components=[c.value for c in effective_components],
        )

        try:
            manifest = await self._execute_backup(
                backup_id=backup_id,
                timestamp=timestamp,
                trigger=trigger,
                effective_components=effective_components,
                use_compression=use_compression,
                dir_name=dir_name,
                backup_dir=backup_dir,
            )
        except BackupInProgressError:
            raise
        except Exception as exc:
            logger.error(
                BACKUP_FAILED,
                backup_id=backup_id,
                error=str(exc),
                exc_info=True,
            )
            # Clean up partial backup
            if backup_dir.exists():
                shutil.rmtree(str(backup_dir))
            raise
        return manifest

    async def _execute_backup(  # noqa: PLR0913
        self,
        *,
        backup_id: str,
        timestamp: str,
        trigger: BackupTrigger,
        effective_components: tuple[BackupComponent, ...],
        use_compression: bool,
        dir_name: str,
        backup_dir: Path,
    ) -> BackupManifest:
        """Run the backup steps: create dirs, copy data, write manifest."""
        self._backup_path.mkdir(parents=True, exist_ok=True)
        backup_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240

        total_size = 0
        for comp in effective_components:
            handler = self._handlers.get(comp)
            if handler is None:
                logger.warning(
                    BACKUP_FAILED,
                    backup_id=backup_id,
                    component=comp.value,
                    error="No handler registered",
                )
                continue
            size = await handler.backup(backup_dir)
            total_size += size

        # Compute checksum of all files
        checksum = await asyncio.to_thread(
            self._compute_checksum,
            backup_dir,
        )

        manifest = BackupManifest(
            synthorg_version=__version__,
            timestamp=timestamp,
            trigger=trigger,
            components=effective_components,
            db_schema_version=self._schema_version,
            size_bytes=total_size,
            checksum=f"sha256:{checksum}",
            backup_id=backup_id,
        )

        # Write manifest
        manifest_path = backup_dir / "manifest.json"
        manifest_path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.debug(
            BACKUP_MANIFEST_WRITTEN,
            backup_id=backup_id,
            path=str(manifest_path),
        )

        # Compress if requested
        if use_compression:
            archive_path = self._backup_path / f"{dir_name}.tar.gz"
            await asyncio.to_thread(
                self._compress_dir,
                backup_dir,
                archive_path,
            )
            shutil.rmtree(str(backup_dir))

        logger.info(
            BACKUP_COMPLETED,
            backup_id=backup_id,
            trigger=trigger.value,
            size_bytes=total_size,
            compressed=use_compression,
        )

        # Run retention pruning (best-effort)
        try:
            await self._retention.prune()
        except Exception:
            logger.warning(
                BACKUP_FAILED,
                backup_id=backup_id,
                error="Retention pruning failed",
                exc_info=True,
            )

        return manifest

    async def restore_from_backup(
        self,
        backup_id: str,
        components: tuple[BackupComponent, ...] | None = None,
    ) -> RestoreResponse:
        """Restore data from a backup.

        Creates a safety backup before restoring.

        Args:
            backup_id: ID of the backup to restore from.
            components: Components to restore (None = all from manifest).

        Returns:
            Restore response with manifest and safety backup ID.

        Raises:
            BackupNotFoundError: If backup_id does not exist.
            RestoreError: If restore fails.
        """
        logger.info(
            BACKUP_RESTORE_STARTED,
            backup_id=backup_id,
        )

        # Load manifest
        manifest = await self._load_manifest(backup_id)
        restore_components = components or manifest.components

        # Extract compressed backup if needed
        backup_dir = self._find_backup_dir(backup_id)
        temp_extracted = False
        if backup_dir is None:
            # Try compressed archive
            backup_dir = await self._extract_archive(backup_id)
            if backup_dir is None:
                raise BackupNotFoundError(_not_found_msg(backup_id))
            temp_extracted = True

        try:
            # Validate source
            await self._validate_restore_components(restore_components, backup_dir)

            # Create safety backup before restore
            safety_manifest = await self.create_backup(
                BackupTrigger.PRE_MIGRATION,
                components=restore_components,
                compress=False,
            )

            # Perform restore
            try:
                for comp in restore_components:
                    handler = self._handlers[comp]
                    await handler.restore(backup_dir)
            except Exception as exc:
                logger.exception(
                    BACKUP_RESTORE_ROLLBACK,
                    backup_id=backup_id,
                    safety_backup_id=safety_manifest.backup_id,
                    error=str(exc),
                )
                msg = f"Restore failed for {backup_id}: {exc}"
                raise RestoreError(msg) from exc

            logger.info(
                BACKUP_RESTORE_COMPLETED,
                backup_id=backup_id,
                components=[c.value for c in restore_components],
                safety_backup_id=safety_manifest.backup_id,
            )

            return RestoreResponse(
                manifest=manifest,
                restored_components=restore_components,
                safety_backup_id=safety_manifest.backup_id,
            )

        except RestoreError:
            logger.error(
                BACKUP_RESTORE_FAILED,
                backup_id=backup_id,
                exc_info=True,
            )
            raise
        finally:
            if temp_extracted and backup_dir is not None and backup_dir.exists():
                shutil.rmtree(str(backup_dir))

    async def _validate_restore_components(
        self,
        restore_components: tuple[BackupComponent, ...],
        backup_dir: Path,
    ) -> None:
        """Validate all restore components have handlers and valid sources."""
        for comp in restore_components:
            handler = self._handlers.get(comp)
            if handler is None:
                msg = f"No handler for component: {comp.value}"
                raise RestoreError(msg)
            valid = await handler.validate_source(backup_dir)
            if not valid:
                msg = f"Invalid backup source for component: {comp.value}"
                raise RestoreError(msg)

    async def list_backups(self) -> tuple[BackupInfo, ...]:
        """List all available backups.

        Returns:
            Tuple of backup info summaries, sorted by timestamp descending.
        """
        if not self._backup_path.exists():
            logger.debug(BACKUP_LISTED, count=0)
            return ()

        infos: list[BackupInfo] = []

        for entry in self._backup_path.iterdir():
            if entry.is_dir():
                self._try_load_dir_info(entry, infos)
            elif entry.name.endswith(".tar.gz"):
                await self._try_load_archive_info(entry, infos)

        infos.sort(key=lambda i: i.timestamp, reverse=True)
        logger.debug(BACKUP_LISTED, count=len(infos))
        return tuple(infos)

    def _try_load_dir_info(
        self,
        entry: Path,
        infos: list[BackupInfo],
    ) -> None:
        """Try to load backup info from a directory manifest."""
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            m = BackupManifest.model_validate(data)
            infos.append(
                BackupInfo(
                    backup_id=m.backup_id,
                    timestamp=m.timestamp,
                    trigger=m.trigger,
                    components=m.components,
                    size_bytes=m.size_bytes,
                    compressed=False,
                )
            )
        except Exception:
            logger.debug(
                BACKUP_MANIFEST_INVALID,
                path=str(manifest_path),
            )

    async def _try_load_archive_info(
        self,
        entry: Path,
        infos: list[BackupInfo],
    ) -> None:
        """Try to load backup info from a compressed archive."""
        try:
            m = await asyncio.to_thread(
                self._read_manifest_from_archive,
                entry,
            )
            if m is not None:
                infos.append(
                    BackupInfo(
                        backup_id=m.backup_id,
                        timestamp=m.timestamp,
                        trigger=m.trigger,
                        components=m.components,
                        size_bytes=m.size_bytes,
                        compressed=True,
                    )
                )
        except Exception:
            logger.debug(
                BACKUP_MANIFEST_INVALID,
                path=str(entry),
            )

    async def get_backup(self, backup_id: str) -> BackupManifest:
        """Get the full manifest for a specific backup.

        Args:
            backup_id: Backup identifier.

        Returns:
            Full backup manifest.

        Raises:
            BackupNotFoundError: If backup does not exist.
        """
        return await self._load_manifest(backup_id)

    async def delete_backup(self, backup_id: str) -> None:
        """Delete a backup by ID.

        Args:
            backup_id: Backup identifier.

        Raises:
            BackupNotFoundError: If backup does not exist.
        """
        deleted = self._try_delete_backup(backup_id)

        if not deleted:
            logger.warning(BACKUP_NOT_FOUND, backup_id=backup_id)
            raise BackupNotFoundError(_not_found_msg(backup_id))

        logger.info(BACKUP_DELETED, backup_id=backup_id)

    def _try_delete_backup(self, backup_id: str) -> bool:
        """Attempt to delete a backup, returning True on success."""
        if not self._backup_path.exists():
            return False

        for entry in self._backup_path.iterdir():
            if entry.is_dir():
                if self._dir_matches_backup(entry, backup_id):
                    shutil.rmtree(str(entry))
                    return True
            elif (
                entry.is_file()
                and entry.name.endswith(".tar.gz")
                and entry.name.startswith(backup_id)
            ):
                entry.unlink()
                return True
        return False

    @staticmethod
    def _dir_matches_backup(entry: Path, backup_id: str) -> bool:
        """Check if a directory contains a manifest matching backup_id."""
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            return False
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return bool(data.get("backup_id") == backup_id)
        except Exception:
            return False

    async def _load_manifest(self, backup_id: str) -> BackupManifest:
        """Load manifest for a given backup ID."""
        if self._backup_path.exists():
            for entry in self._backup_path.iterdir():
                result = await self._try_load_entry_manifest(entry, backup_id)
                if result is not None:
                    return result

        logger.warning(BACKUP_NOT_FOUND, backup_id=backup_id)
        raise BackupNotFoundError(_not_found_msg(backup_id))

    async def _try_load_entry_manifest(
        self,
        entry: Path,
        backup_id: str,
    ) -> BackupManifest | None:
        """Try to load a manifest matching backup_id from a directory or archive."""
        if entry.is_dir():  # noqa: ASYNC240
            manifest_path = entry / "manifest.json"
            if manifest_path.exists():
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    m = BackupManifest.model_validate(data)
                    if m.backup_id == backup_id:
                        return m
                except Exception as exc:
                    logger.warning(
                        BACKUP_MANIFEST_INVALID,
                        path=str(manifest_path),
                        error=str(exc),
                    )
        elif entry.name.endswith(".tar.gz"):
            try:
                archive_manifest = await asyncio.to_thread(
                    self._read_manifest_from_archive,
                    entry,
                )
                if (
                    archive_manifest is not None
                    and archive_manifest.backup_id == backup_id
                ):
                    return archive_manifest
            except Exception:
                logger.debug(
                    BACKUP_MANIFEST_INVALID,
                    path=str(entry),
                )
        return None

    def _find_backup_dir(self, backup_id: str) -> Path | None:
        """Find uncompressed backup directory by ID."""
        if not self._backup_path.exists():
            return None
        for entry in self._backup_path.iterdir():
            if not entry.is_dir():
                continue
            if self._dir_matches_backup(entry, backup_id):
                return entry
        return None

    async def _extract_archive(self, backup_id: str) -> Path | None:
        """Extract a compressed backup archive to a temp directory."""
        if not self._backup_path.exists():
            return None
        for entry in self._backup_path.iterdir():
            if not entry.name.endswith(".tar.gz"):
                continue
            if not self._archive_matches_backup(entry, backup_id):
                continue

            # Extract to temp directory
            temp_dir = self._backup_path / f"_restore_{backup_id}"
            try:
                await asyncio.to_thread(
                    self._extract_tar,
                    entry,
                    temp_dir,
                )
            except Exception:
                if temp_dir.exists():
                    shutil.rmtree(str(temp_dir))
                return None
            else:
                return temp_dir
        return None

    def _archive_matches_backup(
        self,
        entry: Path,
        backup_id: str,
    ) -> bool:
        """Check if an archive contains a manifest matching backup_id."""
        if entry.name.startswith(backup_id):
            return True
        try:
            m = self._read_manifest_from_archive(entry)
        except Exception:
            return False
        else:
            return m is not None and m.backup_id == backup_id

    @staticmethod
    def _compute_checksum(directory: Path) -> str:
        """Compute SHA-256 checksum of all files in a directory."""
        hasher = hashlib.sha256()
        for filepath in sorted(directory.rglob("*")):
            if filepath.is_file() and filepath.name != "manifest.json":
                hasher.update(filepath.read_bytes())
        return hasher.hexdigest()

    @staticmethod
    def _compress_dir(source_dir: Path, archive_path: Path) -> None:
        """Create a tar.gz archive from a directory."""
        with tarfile.open(str(archive_path), "w:gz") as tar:
            for item in source_dir.iterdir():
                tar.add(str(item), arcname=item.name)

    @staticmethod
    def _extract_tar(archive_path: Path, target_dir: Path) -> None:
        """Extract a tar.gz archive to a target directory."""
        target_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(str(archive_path), "r:gz") as tar:
            # Security: filter out absolute paths and path traversal
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    msg = f"Unsafe path in archive: {member.name}"
                    raise ManifestError(msg)
            tar.extractall(str(target_dir), filter="data")

    @staticmethod
    def _read_manifest_from_archive(
        archive_path: Path,
    ) -> BackupManifest | None:
        """Read manifest.json from a tar.gz archive without full extraction."""
        try:
            with tarfile.open(str(archive_path), "r:gz") as tar:
                try:
                    member = tar.getmember("manifest.json")
                except KeyError:
                    return None
                f = tar.extractfile(member)
                if f is None:
                    return None
                data = json.loads(f.read())
                return BackupManifest.model_validate(data)
        except Exception:
            return None
