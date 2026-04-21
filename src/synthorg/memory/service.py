"""Memory admin service layer for fine-tuning checkpoints and runs.

Encapsulates persistence access for the ``/memory/fine-tune/*`` endpoints
so the controller stays thin (parse / shape / return) and the raw
``app_state.persistence.get_db()`` handle stays inside the persistence
package where it belongs.

The service operates on SQLite today because the fine-tuning pipeline is
SQLite-only (Postgres does not yet expose a matching repository); the
abstraction is ready to grow a Postgres sibling without touching the
controller.
"""

import contextlib
import json
from typing import TYPE_CHECKING, Any

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.embedding.fine_tune_models import (
    CheckpointRecord,  # noqa: TC001
    FineTuneRun,  # noqa: TC001
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_CHECKPOINT_DEPLOY_FAILED,
    MEMORY_CHECKPOINT_DEPLOYED,
    MEMORY_CHECKPOINT_ROLLBACK,
    MEMORY_CHECKPOINT_ROLLBACK_FAILED,
)
from synthorg.persistence.errors import QueryError

if TYPE_CHECKING:
    from synthorg.persistence.sqlite.fine_tune_repo import (
        SQLiteFineTuneCheckpointRepository,
        SQLiteFineTuneRunRepository,
    )
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)


class CheckpointNotFoundError(Exception):
    """Raised when a deploy/rollback/delete targets a missing checkpoint."""


class CheckpointRollbackUnavailableError(Exception):
    """Raised when a rollback is requested but no backup config exists."""


class CheckpointRollbackCorruptError(Exception):
    """Raised when the stored backup config fails JSON parsing."""


class MemoryService:
    """Service layer for memory admin operations.

    Wraps the fine-tune checkpoint + run repositories and the settings
    service so API controllers never reach into ``persistence.get_db()``
    directly.
    """

    __slots__ = ("_checkpoints", "_runs", "_settings")

    def __init__(
        self,
        *,
        checkpoint_repo: SQLiteFineTuneCheckpointRepository,
        run_repo: SQLiteFineTuneRunRepository,
        settings_service: SettingsService | None,
    ) -> None:
        """Initialise with repository + settings dependencies.

        Args:
            checkpoint_repo: Fine-tune checkpoint persistence.
            run_repo: Fine-tune run persistence.
            settings_service: Runtime settings service (may be ``None``
                if the operator has not configured one; deploy flows
                degrade to "activate only, skip settings push").
        """
        self._checkpoints = checkpoint_repo
        self._runs = run_repo
        self._settings = settings_service

    async def list_checkpoints(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[CheckpointRecord, ...]:
        """Return a page of checkpoints newest-first."""
        checkpoints, _ = await self._checkpoints.list_checkpoints(
            limit=limit,
            offset=offset,
        )
        return checkpoints

    async def get_checkpoint(
        self,
        checkpoint_id: NotBlankStr,
    ) -> CheckpointRecord | None:
        """Fetch a single checkpoint by id."""
        return await self._checkpoints.get_checkpoint(checkpoint_id)

    async def deploy_checkpoint(
        self,
        checkpoint_id: NotBlankStr,
    ) -> CheckpointRecord:
        """Activate *checkpoint_id* and update runtime embedder config.

        Captures the prior active checkpoint + settings, activates the
        target, and writes ``memory.embedder_model`` /
        ``memory.embedder_provider``. On any settings-side failure the
        prior state is restored atomically.

        Raises:
            CheckpointNotFoundError: If the id does not exist.
            QueryError: On unrecoverable persistence faults.
        """
        cp = await self._checkpoints.get_checkpoint(checkpoint_id)
        if cp is None:
            msg = f"Checkpoint {checkpoint_id} not found"
            raise CheckpointNotFoundError(msg)

        prior = await self._checkpoints.get_active_checkpoint()
        await self._checkpoints.set_active(checkpoint_id)

        if self._settings is not None:
            await self._apply_deploy_settings(
                checkpoint_id=checkpoint_id,
                model_path=cp.model_path,
                prior=prior,
            )

        updated = await self._checkpoints.get_checkpoint(checkpoint_id)
        if updated is None:
            msg = "Checkpoint activated but not found on re-read"
            raise QueryError(msg)
        logger.info(
            MEMORY_CHECKPOINT_DEPLOYED,
            checkpoint_id=checkpoint_id,
            prior_checkpoint_id=prior.id if prior is not None else None,
        )
        return updated

    async def rollback_checkpoint(
        self,
        checkpoint_id: NotBlankStr,
    ) -> CheckpointRecord:
        """Restore the backup config stored with *checkpoint_id*.

        Raises:
            CheckpointNotFoundError: If the id does not exist.
            CheckpointRollbackUnavailableError: If no backup was stored.
            CheckpointRollbackCorruptError: If the backup JSON cannot
                be parsed.
        """
        cp = await self._checkpoints.get_checkpoint(checkpoint_id)
        if cp is None:
            msg = f"Checkpoint {checkpoint_id} not found"
            raise CheckpointNotFoundError(msg)
        if cp.backup_config_json is None:
            msg = "No backup config available for this checkpoint"
            raise CheckpointRollbackUnavailableError(msg)

        if self._settings is not None:
            try:
                backup: dict[str, Any] = json.loads(cp.backup_config_json)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    MEMORY_CHECKPOINT_ROLLBACK_FAILED,
                    checkpoint_id=checkpoint_id,
                    error_type=type(exc).__name__,
                )
                msg = "Backup config is corrupt and cannot be restored"
                raise CheckpointRollbackCorruptError(msg) from exc
            for key, value in backup.items():
                await self._settings.set("memory", key, str(value))

        await self._checkpoints.deactivate_all()
        updated = await self._checkpoints.get_checkpoint(checkpoint_id)
        if updated is None:
            msg = "Checkpoint not found after rollback"
            raise QueryError(msg)
        logger.info(
            MEMORY_CHECKPOINT_ROLLBACK,
            checkpoint_id=checkpoint_id,
        )
        return updated

    async def delete_checkpoint(self, checkpoint_id: NotBlankStr) -> None:
        """Delete a checkpoint (repo rejects active checkpoint)."""
        await self._checkpoints.delete_checkpoint(checkpoint_id)

    async def list_runs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[FineTuneRun, ...]:
        """Return a page of fine-tune runs newest-first."""
        runs, _ = await self._runs.list_runs(limit=limit, offset=offset)
        return runs

    async def _apply_deploy_settings(
        self,
        *,
        checkpoint_id: NotBlankStr,
        model_path: str,
        prior: CheckpointRecord | None,
    ) -> None:
        """Push embedder settings for a freshly-activated checkpoint.

        Rolls back the checkpoint activation + any already-applied
        settings if a subsequent ``set`` call fails, so a failed deploy
        leaves the prior config intact.
        """
        assert self._settings is not None  # noqa: S101 - guarded by caller

        prior_model = await self._read_setting("embedder_model")
        prior_provider = await self._read_setting("embedder_provider")

        try:
            await self._settings.set("memory", "embedder_model", model_path)
            await self._settings.set("memory", "embedder_provider", "local")
        except Exception as exc:
            if prior is not None:
                with contextlib.suppress(Exception):
                    await self._checkpoints.set_active(prior.id)
            else:
                with contextlib.suppress(Exception):
                    await self._checkpoints.deactivate_all()
            if prior_model is not None:
                with contextlib.suppress(Exception):
                    await self._settings.set(
                        "memory",
                        "embedder_model",
                        prior_model,
                    )
            if prior_provider is not None:
                with contextlib.suppress(Exception):
                    await self._settings.set(
                        "memory",
                        "embedder_provider",
                        prior_provider,
                    )
            logger.warning(
                MEMORY_CHECKPOINT_DEPLOY_FAILED,
                checkpoint_id=checkpoint_id,
                error_type=type(exc).__name__,
            )
            raise

    async def _read_setting(self, key: str) -> str | None:
        """Best-effort read of a ``memory.<key>`` setting for rollback."""
        if self._settings is None:
            return None
        try:
            value = await self._settings.get("memory", key)
        except Exception:
            return None
        return value.value if value is not None else None
