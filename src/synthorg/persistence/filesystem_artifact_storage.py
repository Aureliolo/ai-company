"""File-system artifact storage backend.

Stores artifact content as files under ``<data_dir>/artifacts/<id>``.
Uses ``asyncio.to_thread()`` for blocking file I/O operations.
"""

import asyncio
from pathlib import Path  # noqa: TC003 -- used at runtime

from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_ARTIFACT_RETRIEVE_FAILED,
    PERSISTENCE_ARTIFACT_RETRIEVED,
    PERSISTENCE_ARTIFACT_STORAGE_DELETE_FAILED,
    PERSISTENCE_ARTIFACT_STORAGE_DELETED,
    PERSISTENCE_ARTIFACT_STORE_FAILED,
    PERSISTENCE_ARTIFACT_STORED,
)
from synthorg.persistence.errors import (
    ArtifactStorageFullError,
    ArtifactTooLargeError,
    RecordNotFoundError,
)

logger = get_logger(__name__)

_DEFAULT_MAX_ARTIFACT_BYTES: int = 50 * 1024 * 1024  # 50 MB
_DEFAULT_MAX_TOTAL_BYTES: int = 1024 * 1024 * 1024  # 1 GB


class FileSystemArtifactStorage:
    """File-system implementation of ``ArtifactStorageBackend``.

    Stores each artifact's content as a single file under
    ``<data_dir>/artifacts/<artifact_id>``.

    Args:
        data_dir: Root data directory (artifacts stored in a
            ``artifacts/`` subdirectory).
        max_artifact_bytes: Maximum size of a single artifact in bytes.
        max_total_bytes: Maximum total storage across all artifacts.
    """

    def __init__(
        self,
        data_dir: Path,
        *,
        max_artifact_bytes: int = _DEFAULT_MAX_ARTIFACT_BYTES,
        max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES,
    ) -> None:
        self._artifacts_dir = data_dir / "artifacts"
        self._max_artifact_bytes = max_artifact_bytes
        self._max_total_bytes = max_total_bytes

    @property
    def backend_name(self) -> str:
        """Human-readable backend identifier."""
        return "filesystem"

    async def store(self, artifact_id: str, content: bytes) -> int:
        """Store artifact content to a file.

        Args:
            artifact_id: Unique artifact identifier.
            content: Binary content to store.

        Returns:
            Number of bytes written.

        Raises:
            ArtifactTooLargeError: If *content* exceeds the per-artifact
                size limit.
            ArtifactStorageFullError: If storing would exceed the total
                storage capacity.
        """
        size = len(content)
        if size > self._max_artifact_bytes:
            msg = (
                f"Artifact {artifact_id!r} is {size} bytes, "
                f"exceeds limit of {self._max_artifact_bytes} bytes"
            )
            logger.warning(PERSISTENCE_ARTIFACT_STORE_FAILED, error=msg)
            raise ArtifactTooLargeError(msg)

        current_total = await self.total_size()
        # Subtract existing size if overwriting
        existing_path = self._artifacts_dir / artifact_id
        existing_size = await asyncio.to_thread(
            lambda: existing_path.stat().st_size if existing_path.exists() else 0
        )
        new_total = current_total - existing_size + size
        if new_total > self._max_total_bytes:
            msg = (
                f"Storing artifact {artifact_id!r} ({size} bytes) would "
                f"exceed total limit of {self._max_total_bytes} bytes "
                f"(current usage: {current_total} bytes)"
            )
            logger.warning(PERSISTENCE_ARTIFACT_STORE_FAILED, error=msg)
            raise ArtifactStorageFullError(msg)

        try:
            await asyncio.to_thread(self._write_file, artifact_id, content)
        except OSError as exc:
            msg = f"Failed to store artifact {artifact_id!r}"
            logger.exception(
                PERSISTENCE_ARTIFACT_STORE_FAILED,
                artifact_id=artifact_id,
                error=str(exc),
            )
            raise
        logger.info(
            PERSISTENCE_ARTIFACT_STORED,
            artifact_id=artifact_id,
            size_bytes=size,
        )
        return size

    async def retrieve(self, artifact_id: str) -> bytes:
        """Retrieve artifact content from a file.

        Args:
            artifact_id: Unique artifact identifier.

        Returns:
            The stored binary content.

        Raises:
            RecordNotFoundError: If no content exists for the given ID.
        """
        file_path = self._artifacts_dir / artifact_id
        try:
            content = await asyncio.to_thread(self._read_file, file_path)
        except FileNotFoundError:
            msg = f"Artifact content not found: {artifact_id!r}"
            logger.warning(
                PERSISTENCE_ARTIFACT_RETRIEVE_FAILED,
                artifact_id=artifact_id,
                error=msg,
            )
            raise RecordNotFoundError(msg) from None
        logger.debug(
            PERSISTENCE_ARTIFACT_RETRIEVED,
            artifact_id=artifact_id,
            size_bytes=len(content),
        )
        return content

    async def delete(self, artifact_id: str) -> bool:
        """Delete artifact content.

        Args:
            artifact_id: Unique artifact identifier.

        Returns:
            ``True`` if content was deleted, ``False`` if not found.
        """
        file_path = self._artifacts_dir / artifact_id
        try:
            deleted = await asyncio.to_thread(self._delete_file, file_path)
        except OSError as exc:
            logger.exception(
                PERSISTENCE_ARTIFACT_STORAGE_DELETE_FAILED,
                artifact_id=artifact_id,
                error=str(exc),
            )
            raise
        logger.info(
            PERSISTENCE_ARTIFACT_STORAGE_DELETED,
            artifact_id=artifact_id,
            deleted=deleted,
        )
        return deleted

    async def exists(self, artifact_id: str) -> bool:
        """Check whether content exists for an artifact.

        Args:
            artifact_id: Unique artifact identifier.

        Returns:
            ``True`` if content exists.
        """
        file_path = self._artifacts_dir / artifact_id
        return await asyncio.to_thread(file_path.exists)

    async def total_size(self) -> int:
        """Return total bytes stored across all artifacts.

        Returns:
            Total storage usage in bytes.
        """
        return await asyncio.to_thread(self._compute_total_size)

    # ── Sync helpers (run via asyncio.to_thread) ──────────────────

    def _write_file(self, artifact_id: str, content: bytes) -> None:
        """Write content to a file, creating the directory if needed."""
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._artifacts_dir / artifact_id
        file_path.write_bytes(content)

    @staticmethod
    def _read_file(file_path: Path) -> bytes:
        """Read content from a file."""
        return file_path.read_bytes()

    @staticmethod
    def _delete_file(file_path: Path) -> bool:
        """Delete a file if it exists."""
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def _compute_total_size(self) -> int:
        """Sum file sizes in the artifacts directory."""
        if not self._artifacts_dir.exists():
            return 0
        return sum(
            f.stat().st_size for f in self._artifacts_dir.iterdir() if f.is_file()
        )
