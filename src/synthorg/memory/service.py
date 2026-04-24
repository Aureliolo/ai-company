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

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from synthorg.core.types import NotBlankStr
from synthorg.memory.embedding.fine_tune_models import (
    CheckpointRecord,
    FineTuneRun,
    FineTuneStatus,
    PreflightCheck,
    PreflightResult,
)
from synthorg.memory.fine_tune_plan import (
    ActiveEmbedderSnapshot,
    BackendUnsupportedError,
    FineTunePlan,
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_CHECKPOINT_DEPLOY_FAILED,
    MEMORY_CHECKPOINT_DEPLOYED,
    MEMORY_CHECKPOINT_ROLLBACK,
    MEMORY_CHECKPOINT_ROLLBACK_FAILED,
    MEMORY_CHECKPOINT_ROLLBACK_STEP_FAILED,
    MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
    MEMORY_FINE_TUNE_BACKEND_UNSUPPORTED,
    MEMORY_FINE_TUNE_CANCELLED,
    MEMORY_FINE_TUNE_PREFLIGHT_COMPLETED,
    MEMORY_FINE_TUNE_REQUESTED,
    MEMORY_FINE_TUNE_STARTED,
)
from synthorg.persistence.errors import QueryError
from synthorg.persistence.fine_tune_protocol import (
    FineTuneCheckpointRepository,  # noqa: TC001
    FineTuneRunRepository,  # noqa: TC001
)

if TYPE_CHECKING:
    from synthorg.memory.embedding.fine_tune_orchestrator import (
        FineTuneOrchestrator,
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

    __slots__ = ("_checkpoints", "_orchestrator", "_runs", "_settings")

    def __init__(
        self,
        *,
        checkpoint_repo: FineTuneCheckpointRepository,
        run_repo: FineTuneRunRepository,
        settings_service: SettingsService | None,
        orchestrator: FineTuneOrchestrator | None = None,
    ) -> None:
        """Initialise with repository + settings + orchestrator deps.

        Args:
            checkpoint_repo: Fine-tune checkpoint persistence.
            run_repo: Fine-tune run persistence.
            settings_service: Runtime settings service (may be ``None``
                if the operator has not configured one; deploy flows
                degrade to "activate only, skip settings push").
            orchestrator: Fine-tune pipeline orchestrator. ``None`` on
                backends that do not support fine-tune runs (the
                fine-tune lifecycle methods raise
                :class:`BackendUnsupportedError` in that case).
        """
        self._checkpoints = checkpoint_repo
        self._runs = run_repo
        self._settings = settings_service
        self._orchestrator = orchestrator

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
    ) -> tuple[tuple[FineTuneRun, ...], int]:
        """Return a page of fine-tune runs newest-first + the total count.

        The MCP surface needs both the page and the unfiltered total so
        ``PaginationMeta`` can be attached without a second round trip.

        Raises:
            ValueError: If ``offset`` is negative or ``limit`` is not
                strictly positive. Enforcing the bounds here keeps
                invalid paging inputs from reaching the repository
                where the error mode is backend-specific.
        """
        if offset < 0:
            msg = f"offset must be >= 0, got {offset}"
            raise ValueError(msg)
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)
        return await self._runs.list_runs(limit=limit, offset=offset)

    # ── Fine-tune lifecycle ────────────────────────────────────────

    async def start_fine_tune(self, plan: FineTunePlan) -> FineTuneRun:
        """Start a new fine-tune run from *plan*.

        Args:
            plan: MCP-facing fine-tune plan (shield over
                :class:`FineTuneRequest`).

        Returns:
            The created run record.

        Raises:
            BackendUnsupportedError: When the active backend does not
                expose fine-tune support.
            RuntimeError: If another run is already active.
        """
        orchestrator = self._require_orchestrator()
        logger.info(
            MEMORY_FINE_TUNE_REQUESTED,
            source_dir=plan.source_dir,
            base_model=plan.base_model,
            resume_run_id=plan.resume_run_id,
        )
        run = await orchestrator.start(plan.to_request())
        logger.info(
            MEMORY_FINE_TUNE_STARTED,
            run_id=run.id,
            source_dir=plan.source_dir,
        )
        return run

    async def resume_fine_tune(self, run_id: NotBlankStr) -> FineTuneRun:
        """Resume a failed / cancelled fine-tune run.

        Raises:
            BackendUnsupportedError: When the active backend does not
                expose fine-tune support.
            ValueError: If the run is unknown or not resumable.
            RuntimeError: If another run is already active.
        """
        orchestrator = self._require_orchestrator()
        return await orchestrator.resume(str(run_id))

    async def get_fine_tune_status(
        self,
        run_id: NotBlankStr | None = None,
    ) -> FineTuneStatus:
        """Return the current orchestrator status.

        When ``run_id`` is omitted, returns the orchestrator's
        idea of the current / most-recent run (matches
        :meth:`FineTuneOrchestrator.get_status`). When provided, looks
        up the run directly from persistence and synthesises a status
        envelope (so historical runs remain queryable after the
        in-memory ``current_run`` slot rotates).

        Raises:
            BackendUnsupportedError: When the backend does not support
                fine-tune runs.
            ValueError: If *run_id* is given but the run does not exist.
        """
        orchestrator = self._require_orchestrator()
        if run_id is None:
            return await orchestrator.get_status()
        run = await self._runs.get_run(str(run_id))
        if run is None:
            msg = f"Fine-tune run {run_id!r} not found"
            raise ValueError(msg)
        return FineTuneStatus(
            run_id=run.id,
            stage=run.stage,
            progress=run.progress,
            error=run.error,
        )

    async def cancel_fine_tune(self) -> None:
        """Cancel the currently active fine-tune run.

        The orchestrator tracks exactly one active run, so this is
        scoped to that run. Completing a cancel is cooperative and
        awaits the background task for up to 30s (see
        :meth:`FineTuneOrchestrator.cancel`).

        Raises:
            BackendUnsupportedError: When the backend does not support
                fine-tune runs.
        """
        orchestrator = self._require_orchestrator()
        await orchestrator.cancel()
        logger.info(MEMORY_FINE_TUNE_CANCELLED)

    async def run_preflight(self, plan: FineTunePlan) -> PreflightResult:
        """Validate *plan* against local-env prerequisites.

        Keeps the check minimal + deterministic so it is callable from
        any MCP client without kicking off the full pipeline: verifies
        that the ``source_dir`` exists and is a directory, that
        ``output_dir`` (if provided) is writable (or at least
        creatable), and that numeric overrides are within the runner's
        declared bounds.

        Raises:
            BackendUnsupportedError: When the backend does not support
                fine-tune runs.
        """
        self._require_orchestrator()
        checks: list[PreflightCheck] = []
        checks.append(_check_source_dir_exists(plan.source_dir))
        if plan.output_dir is not None:
            checks.append(_check_output_dir_writable(plan.output_dir))
        checks.append(_check_overrides(plan))
        result = PreflightResult(checks=tuple(checks))
        logger.info(
            MEMORY_FINE_TUNE_PREFLIGHT_COMPLETED,
            can_proceed=result.can_proceed,
            check_count=len(checks),
        )
        return result

    async def get_active_embedder(self) -> ActiveEmbedderSnapshot:
        """Return the active embedder snapshot read from settings.

        Combines the active checkpoint id (from
        :meth:`get_active_checkpoint`) with the
        ``memory.embedder_model`` / ``memory.embedder_provider``
        settings so MCP callers get a single atomic read.
        """
        active_checkpoint = await self._checkpoints.get_active_checkpoint()
        if self._settings is None:
            return ActiveEmbedderSnapshot(
                checkpoint_id=(
                    active_checkpoint.id if active_checkpoint is not None else None
                ),
                read_from_settings=False,
            )
        provider_value, _ = await self._read_setting("embedder_provider")
        model_value, _ = await self._read_setting("embedder_model")
        return ActiveEmbedderSnapshot(
            provider=(
                NotBlankStr(provider_value)
                if provider_value is not None and provider_value
                else None
            ),
            model=(
                NotBlankStr(model_value)
                if model_value is not None and model_value
                else None
            ),
            checkpoint_id=(
                active_checkpoint.id if active_checkpoint is not None else None
            ),
            read_from_settings=True,
        )

    def _require_orchestrator(self) -> FineTuneOrchestrator:
        """Return the orchestrator or raise :class:`BackendUnsupportedError`.

        Handlers catch the exception and surface a ``not_supported``
        envelope (see :mod:`synthorg.meta.mcp.handlers.memory`).
        """
        if self._orchestrator is None:
            msg = (
                "fine-tune orchestration is not available on the active "
                "persistence backend (SQLite-only today)"
            )
            # Log before raising so operators can see the failure
            # path in telemetry even when handlers swallow the
            # exception into a ``not_supported`` wire envelope.
            logger.warning(
                MEMORY_FINE_TUNE_BACKEND_UNSUPPORTED,
                method="_require_orchestrator",
                reason="orchestrator_not_wired",
            )
            raise BackendUnsupportedError(msg)
        return self._orchestrator

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
        # SettingNotFoundError is the "setting genuinely absent" path --
        # benign and stays at DEBUG. Anything else (connection / auth /
        # corruption) is operationally interesting and escalates to
        # WARNING so prod monitoring catches prolonged settings-service
        # outages during a checkpoint-deploy rollback.
        from synthorg.settings.errors import (  # noqa: PLC0415 -- cycle break
            SettingNotFoundError,
        )

        try:
            value = await self._settings.get("memory", key)
        except SettingNotFoundError as exc:
            logger.debug(
                MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
                setting=key,
                error_type=type(exc).__name__,
                reason="read_for_rollback_not_found",
            )
            return None, False
        except Exception as exc:
            logger.warning(
                MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
                setting=key,
                error_type=type(exc).__name__,
                reason="read_for_rollback_transient",
            )
            # Any non-NotFound exception (storage glitch, auth, network
            # timeout, ...) collapses to exists=False so rollback will
            # explicitly delete the newly-written setting instead of
            # leaving it in place.
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
            # Emit both the legacy aggregate event (for existing
            # dashboards / alerting) AND the step-specific event so
            # alerts can pick up partial-rollback conditions distinctly
            # from the overall rollback failure signal.
            logger.warning(
                MEMORY_CHECKPOINT_ROLLBACK_FAILED,
                checkpoint_id=checkpoint_id,
                error_type=type(exc).__name__,
                stage="rollback",
                step=step,
            )
            logger.error(  # noqa: TRY400 -- not an exception-context log; distinct audit event, not a traceback dump
                MEMORY_CHECKPOINT_ROLLBACK_STEP_FAILED,
                checkpoint_id=checkpoint_id,
                error_type=type(exc).__name__,
                step=step,
            )


# ── Preflight helpers ────────────────────────────────────────────


def _check_source_dir_exists(source_dir: str) -> PreflightCheck:
    """Verify that *source_dir* exists, is a directory, and is readable."""
    path = Path(source_dir)
    if not path.exists():
        return PreflightCheck(
            name=NotBlankStr("source_dir_exists"),
            status="fail",
            message=NotBlankStr(f"Source directory does not exist: {source_dir}"),
        )
    if not path.is_dir():
        return PreflightCheck(
            name=NotBlankStr("source_dir_exists"),
            status="fail",
            message=NotBlankStr(f"Source path is not a directory: {source_dir}"),
        )
    # Verify the runner can actually read AND traverse the directory.
    # R_OK alone is insufficient: a directory without execute/search
    # permission cannot be entered, so the runner would fail to open
    # any file inside even though ``R_OK`` passed.
    if not os.access(path, os.R_OK | os.X_OK):
        return PreflightCheck(
            name=NotBlankStr("source_dir_exists"),
            status="fail",
            message=NotBlankStr(
                f"Source directory is not readable or not traversable: {source_dir}",
            ),
        )
    return PreflightCheck(
        name=NotBlankStr("source_dir_exists"),
        status="pass",
        message=NotBlankStr("Source directory exists and is readable"),
    )


def _check_output_dir_writable(output_dir: str) -> PreflightCheck:
    """Verify that *output_dir* (or its parent, if absent) is writable.

    Resolves symlinks before the writability probe so a dangling
    symlink (``output_dir`` is a symlink whose target does not exist)
    does not silently pass the non-existent-parent fallback. The
    resolved target must exist and be writable for the check to pass.
    """
    path = Path(output_dir)
    # Symlink -> must resolve its target before probing. A dangling
    # symlink's ``exists()`` returns False (exists() follows the link),
    # so detect this case explicitly so the warn/fail message can
    # point to the broken target rather than reporting the link path.
    if path.is_symlink():
        resolved = path.resolve(strict=False)
        if not resolved.exists():
            return PreflightCheck(
                name=NotBlankStr("output_dir_writable"),
                status="warn",
                message=NotBlankStr(
                    f"Output directory symlink target does not exist: "
                    f"{path} -> {resolved}",
                ),
                detail="The runner will attempt to create it at pipeline start.",
            )
        probe = resolved
    else:
        probe = path if path.exists() else path.parent
    if not probe.exists():
        return PreflightCheck(
            name=NotBlankStr("output_dir_writable"),
            status="warn",
            message=NotBlankStr(
                f"Output directory parent does not exist: {probe}",
            ),
            detail="The runner will attempt to create it at pipeline start.",
        )
    # Probe must be a directory -- a path that exists but resolves
    # to a regular file cannot serve as the checkpoint output dir
    # and would fail deep inside the runner where the error is
    # harder to act on.
    if not probe.is_dir():
        return PreflightCheck(
            name=NotBlankStr("output_dir_writable"),
            status="fail",
            message=NotBlankStr(
                f"Output directory path is not a directory: {probe}",
            ),
        )
    # Require both write and execute/search permissions: writing a
    # new checkpoint file requires traversing into the directory
    # first, so W_OK alone is insufficient.
    if not os.access(probe, os.W_OK | os.X_OK):
        return PreflightCheck(
            name=NotBlankStr("output_dir_writable"),
            status="fail",
            message=NotBlankStr(
                f"Output directory is not writable or not traversable: {probe}",
            ),
        )
    return PreflightCheck(
        name=NotBlankStr("output_dir_writable"),
        status="pass",
        message=NotBlankStr("Output directory is writable"),
    )


def _check_overrides(plan: FineTunePlan) -> PreflightCheck:
    """Return a pass check -- Pydantic already enforced the bounds.

    Preserved as an explicit check so the preflight report always
    includes the override review; any operator reading the result gets
    an audit-trail style confirmation rather than a silent omission.
    """
    overrides = {
        "epochs": plan.epochs,
        "learning_rate": plan.learning_rate,
        "temperature": plan.temperature,
        "top_k": plan.top_k,
        "batch_size": plan.batch_size,
        "validation_split": plan.validation_split,
    }
    non_default = {k: v for k, v in overrides.items() if v is not None}
    message = (
        "No overrides -- runner defaults will apply"
        if not non_default
        else f"Overrides within bounds: {non_default}"
    )
    return PreflightCheck(
        name=NotBlankStr("override_bounds"),
        status="pass",
        message=NotBlankStr(message),
    )
