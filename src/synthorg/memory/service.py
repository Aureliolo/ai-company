"""Memory admin service layer for fine-tuning checkpoints and runs.

Encapsulates persistence access for the ``/memory/fine-tune/*`` endpoints
so the controller stays thin (parse / shape / return) and the raw
``app_state.persistence.get_db()`` handle stays inside the persistence
package where it belongs.

The service is backend-agnostic: both SQLite and Postgres expose the
``FineTuneRunRepository`` + ``FineTuneCheckpointRepository`` protocols
via ``PersistenceBackend.fine_tune_runs`` and
``PersistenceBackend.fine_tune_checkpoints``, and the parametrized
conformance suite at ``tests/conformance/persistence/`` exercises both
arms on every run.
"""

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
    MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
)
from synthorg.persistence.errors import QueryError
from synthorg.persistence.fine_tune_protocol import (
    FineTuneCheckpointRepository,  # noqa: TC001
    FineTuneRunRepository,  # noqa: TC001
)

if TYPE_CHECKING:
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
        checkpoint_repo: FineTuneCheckpointRepository,
        run_repo: FineTuneRunRepository,
        settings_service: SettingsService | None,
    ) -> None:
        """Initialize with repository + settings dependencies.

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
    ) -> tuple[tuple[CheckpointRecord, ...], int]:
        """Return a page of checkpoints newest-first along with the total count.

        Both values are needed so callers (REST controllers, MCP
        handlers) can attach accurate pagination metadata without
        reaching past the service boundary.

        Args:
            limit: Page size.
            offset: Page offset.

        Returns:
            Tuple of ``(checkpoints, total)`` where ``total`` is the
            unfiltered count the repository would return for an
            unpaginated query.
        """
        return await self._checkpoints.list_checkpoints(
            limit=limit,
            offset=offset,
        )

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
                parsed: Any = json.loads(cp.backup_config_json)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    MEMORY_CHECKPOINT_ROLLBACK_FAILED,
                    checkpoint_id=checkpoint_id,
                    error_type=type(exc).__name__,
                )
                msg = "Backup config is corrupt and cannot be restored"
                raise CheckpointRollbackCorruptError(msg) from exc
            if not isinstance(parsed, dict):
                # ``json.loads`` happily returns ``list``, ``None``, ``str``,
                # etc.; the rollback loop assumes a mapping and would crash
                # with ``AttributeError`` on ``backup.items()``. Fail closed
                # with the dedicated corruption error instead.
                logger.warning(
                    MEMORY_CHECKPOINT_ROLLBACK_FAILED,
                    checkpoint_id=checkpoint_id,
                    error_type="BackupConfigNotMapping",
                    parsed_type=type(parsed).__name__,
                )
                msg = (
                    f"Backup config must be a JSON object; got {type(parsed).__name__}"
                )
                raise CheckpointRollbackCorruptError(msg)
            backup: dict[str, Any] = parsed
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
        """Delete a checkpoint by id.

        The underlying repository is a silent no-op when the target
        does not exist, so we pre-check and surface
        :class:`CheckpointNotFoundError` here. The controller maps that
        to HTTP 404, keeping the contract identical across
        deploy / rollback / delete endpoints (all three surface 404 for
        missing checkpoints and 409 for a ``QueryError`` such as
        attempting to delete the currently-active checkpoint).

        Raises:
            CheckpointNotFoundError: If the id does not exist.
            QueryError: On unrecoverable persistence faults (including
                the domain rule "cannot delete the active checkpoint").
        """
        existing = await self._checkpoints.get_checkpoint(checkpoint_id)
        if existing is None:
            msg = f"Checkpoint {checkpoint_id} not found"
            raise CheckpointNotFoundError(msg)
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

        prior_model_value, prior_model_exists = await self._read_setting(
            "embedder_model",
        )
        prior_provider_value, prior_provider_exists = await self._read_setting(
            "embedder_provider",
        )

        try:
            await self._settings.set("memory", "embedder_model", model_path)
            await self._settings.set("memory", "embedder_provider", "local")
        except Exception as exc:
            if prior is not None:
                await self._rollback_step(
                    self._checkpoints.set_active(prior.id),
                    checkpoint_id=checkpoint_id,
                    step="reactivate_prior_checkpoint",
                )
            else:
                await self._rollback_step(
                    self._checkpoints.deactivate_all(),
                    checkpoint_id=checkpoint_id,
                    step="deactivate_all_checkpoints",
                )
            # Restore or explicitly delete each setting based on whether a
            # prior value existed. Collapsing "did not exist" and
            # "couldn't read" into a single ``None`` would leave a freshly
            # written setting behind on failure whenever the read was
            # simply noisy, so the two cases are tracked separately.
            await self._restore_or_delete(
                "embedder_model",
                prior_model_value,
                prior_model_exists,
                checkpoint_id,
            )
            await self._restore_or_delete(
                "embedder_provider",
                prior_provider_value,
                prior_provider_exists,
                checkpoint_id,
            )
            logger.warning(
                MEMORY_CHECKPOINT_DEPLOY_FAILED,
                checkpoint_id=checkpoint_id,
                error_type=type(exc).__name__,
            )
            raise

    async def _restore_or_delete(
        self,
        key: str,
        prior_value: str | None,
        prior_exists: bool,  # noqa: FBT001 -- internal helper, not a public API
        checkpoint_id: str,
    ) -> None:
        """Restore *prior_value* or delete the key when there was no prior.

        ``prior_exists`` distinguishes "was unset before" (delete) from
        "failed to read before" (restore if we have a value to restore,
        otherwise leave alone to avoid losing the newly-written setting).
        """
        assert self._settings is not None  # noqa: S101 - guarded by caller
        if prior_exists and prior_value is not None:
            await self._rollback_step(
                self._settings.set("memory", key, prior_value),
                checkpoint_id=checkpoint_id,
                step=f"restore_{key}",
            )
        elif prior_exists and prior_value is None:
            # Existed but resolved to ``None`` -- treat as "was unset".
            await self._rollback_step(
                self._settings.delete("memory", key),
                checkpoint_id=checkpoint_id,
                step=f"delete_{key}",
            )
        elif not prior_exists and prior_value is None:
            # Key was genuinely absent before the deploy: remove the newly
            # written value so rollback returns to a pristine state.
            await self._rollback_step(
                self._settings.delete("memory", key),
                checkpoint_id=checkpoint_id,
                step=f"delete_{key}",
            )
        # prior_exists=False + prior_value is not None cannot happen.

    async def _read_setting(self, key: str) -> tuple[str | None, bool]:
        """Best-effort read of a ``memory.<key>`` setting for rollback.

        Returns ``(value, exists)`` so callers can distinguish three
        cases cleanly: "was set" (``exists=True``), "was genuinely
        unset" (``exists=False, value=None``) and "failed to read"
        (``exists=False, value=None``). All three feed the rollback
        path -- any ``exists=False`` branch asks the caller to delete
        the newly-written setting so rollback never leaves a residue,
        and the DEBUG log distinguishes the read-error sub-case for
        operator audit.
        """
        if self._settings is None:
            return None, False
        try:
            value = await self._settings.get("memory", key)
        except Exception as exc:
            logger.debug(
                MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
                setting=key,
                error_type=type(exc).__name__,
                reason="read_for_rollback",
            )
            # Any exception (missing, storage glitch, ...) collapses to
            # exists=False so rollback will explicitly delete the
            # newly-written setting instead of leaving it in place.
            return None, False
        return value.value, True

    @staticmethod
    async def _rollback_step(
        coro: Any,
        *,
        checkpoint_id: str,
        step: str,
    ) -> None:
        """Run *coro* in a rollback path, logging any failure at WARNING.

        Rollback failures must never shadow the original deploy error
        (which is already being raised up the call stack), but they
        must be audit-visible so operators know the config may be in
        an inconsistent state. Uses the rollback-specific event so
        alerting can distinguish primary deploy failures from partial
        rollback conditions.
        """
        try:
            await coro
        except Exception as exc:
            logger.warning(
                MEMORY_CHECKPOINT_ROLLBACK_FAILED,
                checkpoint_id=checkpoint_id,
                error_type=type(exc).__name__,
                stage="rollback",
                step=step,
            )
