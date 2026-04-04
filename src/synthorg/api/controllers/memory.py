"""Memory admin controller -- fine-tuning and embedder endpoints.

All endpoints require CEO or the internal SYSTEM role
(used by the CLI for admin operations).
"""

import asyncio
import contextlib
import json

from litestar import Controller, delete, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.exceptions import ClientException
from litestar.status_codes import HTTP_409_CONFLICT
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import HumanRole, require_roles
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.memory.embedding.fine_tune import FineTuneStage
from synthorg.memory.embedding.fine_tune_models import (
    CheckpointRecord,
    FineTuneRequest,
    FineTuneRun,
    FineTuneStatus,
    PreflightCheck,
    PreflightResult,
)
from synthorg.memory.errors import FineTuneDependencyError
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
    MEMORY_FINE_TUNE_PREFLIGHT_COMPLETED,
    MEMORY_FINE_TUNE_REQUESTED,
)

logger = get_logger(__name__)


class ActiveEmbedderResponse(BaseModel):
    """Active embedder configuration read from settings."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    provider: NotBlankStr | None = Field(
        default=None,
        description="Embedding provider name",
    )
    model: NotBlankStr | None = Field(
        default=None,
        description="Embedding model identifier",
    )
    dims: int | None = Field(
        default=None,
        ge=1,
        description="Embedding vector dimensions",
    )


class MemoryAdminController(Controller):
    """Admin endpoints for memory management.

    Provides fine-tuning pipeline control, checkpoint management,
    and embedder configuration queries.  All endpoints require
    CEO or SYSTEM role.
    """

    path = "/admin/memory"
    tags = ("admin", "memory")
    guards = [require_roles(HumanRole.CEO, HumanRole.SYSTEM)]  # noqa: RUF012

    # -- Fine-tuning pipeline ----------------------------------------

    @post("/fine-tune")
    async def start_fine_tune(
        self,
        state: State,
        data: FineTuneRequest,
    ) -> ApiResponse[FineTuneStatus]:
        """Trigger a fine-tuning pipeline run."""
        app_state: AppState = state.app_state
        logger.info(
            MEMORY_FINE_TUNE_REQUESTED,
            source_dir=data.source_dir,
            base_model=data.base_model,
        )
        if not app_state.has_fine_tune_orchestrator:
            raise ClientException(detail="Fine-tuning is not available")
        orchestrator = app_state.fine_tune_orchestrator
        try:
            run = await orchestrator.start(data)
        except RuntimeError as exc:
            logger.warning(
                MEMORY_FINE_TUNE_REQUESTED,
                error=str(exc),
            )
            raise ClientException(
                detail="A fine-tuning run is already active",
                status_code=HTTP_409_CONFLICT,
            ) from exc
        return ApiResponse(
            data=FineTuneStatus(
                run_id=run.id,
                stage=run.stage,
                progress=run.progress,
            ),
        )

    @post("/fine-tune/resume/{run_id:str}")
    async def resume_fine_tune(
        self,
        state: State,
        run_id: str,
    ) -> ApiResponse[FineTuneStatus]:
        """Resume a failed/cancelled pipeline run."""
        app_state: AppState = state.app_state
        if not app_state.has_fine_tune_orchestrator:
            raise ClientException(detail="Fine-tuning is not available")
        orchestrator = app_state.fine_tune_orchestrator
        try:
            run = await orchestrator.resume(run_id)
        except RuntimeError as exc:
            logger.warning(
                MEMORY_FINE_TUNE_REQUESTED,
                run_id=run_id,
                error=str(exc),
            )
            raise ClientException(
                detail="A fine-tuning run is already active",
                status_code=HTTP_409_CONFLICT,
            ) from exc
        except ValueError as exc:
            logger.warning(
                MEMORY_FINE_TUNE_REQUESTED,
                run_id=run_id,
                error=str(exc),
            )
            raise ClientException(
                detail="Run not found or not resumable",
            ) from exc
        return ApiResponse(
            data=FineTuneStatus(
                run_id=run.id,
                stage=run.stage,
                progress=run.progress,
            ),
        )

    @get("/fine-tune/status")
    async def get_fine_tune_status(
        self,
        state: State,
    ) -> ApiResponse[FineTuneStatus]:
        """Get the current fine-tuning pipeline status."""
        app_state: AppState = state.app_state
        if not app_state.has_fine_tune_orchestrator:
            return ApiResponse(
                data=FineTuneStatus(stage=FineTuneStage.IDLE),
            )
        orchestrator = app_state.fine_tune_orchestrator
        status = await orchestrator.get_status()
        return ApiResponse(data=status)

    @post("/fine-tune/cancel")
    async def cancel_fine_tune(
        self,
        state: State,
    ) -> ApiResponse[FineTuneStatus]:
        """Cancel the active pipeline run."""
        app_state: AppState = state.app_state
        if not app_state.has_fine_tune_orchestrator:
            raise ClientException(detail="Fine-tuning is not available")
        orchestrator = app_state.fine_tune_orchestrator
        await orchestrator.cancel()
        status = await orchestrator.get_status()
        return ApiResponse(data=status)

    @post("/fine-tune/preflight")
    async def run_preflight(
        self,
        state: State,  # noqa: ARG002
        data: FineTuneRequest,
    ) -> ApiResponse[PreflightResult]:
        """Run pre-flight validation checks."""
        async with asyncio.TaskGroup() as tg:
            checks_task = tg.create_task(
                asyncio.to_thread(_run_preflight_checks, data),
            )
            batch_task = tg.create_task(
                asyncio.to_thread(_recommend_batch_size),
            )
        checks = list(checks_task.result())
        batch_size = batch_task.result()
        result = PreflightResult(
            checks=tuple(checks),
            recommended_batch_size=batch_size,
        )
        logger.info(
            MEMORY_FINE_TUNE_PREFLIGHT_COMPLETED,
            can_proceed=result.can_proceed,
            check_count=len(checks),
        )
        return ApiResponse(data=result)

    # -- Checkpoint management ---------------------------------------

    @get("/fine-tune/checkpoints")
    async def list_checkpoints(
        self,
        state: State,
        limit: int = 50,
        offset: int = 0,
    ) -> ApiResponse[tuple[CheckpointRecord, ...]]:
        """List fine-tuning checkpoints."""
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)
        app_state: AppState = state.app_state
        db = app_state.persistence.get_db()
        from synthorg.persistence.sqlite.fine_tune_repo import (  # noqa: PLC0415
            SQLiteFineTuneCheckpointRepository,
        )

        repo = SQLiteFineTuneCheckpointRepository(db)
        cps, _ = await repo.list_checkpoints(
            limit=limit,
            offset=offset,
        )
        return ApiResponse(data=cps)

    @post("/fine-tune/checkpoints/{checkpoint_id:str}/deploy")
    async def deploy_checkpoint(
        self,
        state: State,
        checkpoint_id: str,
    ) -> ApiResponse[CheckpointRecord]:
        """Deploy a specific checkpoint."""
        app_state: AppState = state.app_state
        db = app_state.persistence.get_db()
        from synthorg.persistence.sqlite.fine_tune_repo import (  # noqa: PLC0415
            SQLiteFineTuneCheckpointRepository,
        )

        repo = SQLiteFineTuneCheckpointRepository(db)
        cp = await repo.get_checkpoint(checkpoint_id)
        if cp is None:
            msg = f"Checkpoint {checkpoint_id} not found"
            raise ClientException(detail=msg)
        # Record prior active to allow rollback on failure.
        prior = await repo.get_active_checkpoint()
        await repo.set_active(checkpoint_id)
        # Update runtime embedder config via settings if available.
        if app_state.has_settings_service:
            svc = app_state.settings_service
            # Capture prior settings for rollback.
            prior_model = prior_provider = None
            try:
                sv = await svc.get("memory", "embedder_model")
                prior_model = sv.value if sv is not None else None
            except Exception:  # noqa: S110
                pass  # Best-effort read for rollback
            try:
                sv = await svc.get("memory", "embedder_provider")
                prior_provider = sv.value if sv is not None else None
            except Exception:  # noqa: S110
                pass  # Best-effort read for rollback
            try:
                await svc.set("memory", "embedder_model", cp.model_path)
                await svc.set("memory", "embedder_provider", "local")
            except Exception as exc:
                # Rollback activation + settings on failure.
                if prior is not None:
                    await repo.set_active(prior.id)
                else:
                    await repo.deactivate_all()
                if prior_model is not None:
                    with contextlib.suppress(Exception):
                        await svc.set(
                            "memory",
                            "embedder_model",
                            prior_model,
                        )
                if prior_provider is not None:
                    with contextlib.suppress(Exception):
                        await svc.set(
                            "memory",
                            "embedder_provider",
                            prior_provider,
                        )
                logger.warning(
                    MEMORY_FINE_TUNE_REQUESTED,
                    error=f"Settings update failed: {exc}",
                    checkpoint_id=checkpoint_id,
                )
                raise ClientException(
                    detail="Failed to update embedder settings",
                    status_code=HTTP_409_CONFLICT,
                ) from exc
        updated = await repo.get_checkpoint(checkpoint_id)
        if updated is None:
            raise ClientException(
                detail="Checkpoint activated but not found on re-read",
            )
        return ApiResponse(data=updated)

    @post("/fine-tune/checkpoints/{checkpoint_id:str}/rollback")
    async def rollback_checkpoint(
        self,
        state: State,
        checkpoint_id: str,
    ) -> ApiResponse[CheckpointRecord]:
        """Rollback: restore pre-deployment config from backup."""
        app_state: AppState = state.app_state
        db = app_state.persistence.get_db()
        from synthorg.persistence.sqlite.fine_tune_repo import (  # noqa: PLC0415
            SQLiteFineTuneCheckpointRepository,
        )

        repo = SQLiteFineTuneCheckpointRepository(db)
        cp = await repo.get_checkpoint(checkpoint_id)
        if cp is None:
            msg = f"Checkpoint {checkpoint_id} not found"
            raise ClientException(detail=msg)
        if cp.backup_config_json is None:
            msg = "No backup config available for this checkpoint"
            raise ClientException(detail=msg)
        # Restore backup config via settings service.
        if app_state.has_settings_service:
            try:
                backup = json.loads(cp.backup_config_json)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    MEMORY_FINE_TUNE_REQUESTED,
                    error=f"Corrupt backup config: {exc}",
                    checkpoint_id=checkpoint_id,
                )
                raise ClientException(
                    detail="Backup config is corrupt and cannot be restored",
                ) from exc
            svc = app_state.settings_service
            for key, value in backup.items():
                await svc.set("memory", key, value)
        # Deactivate all checkpoints (no checkpoint is "active" now).
        await repo.deactivate_all()
        updated = await repo.get_checkpoint(checkpoint_id)
        if updated is None:
            raise ClientException(
                detail="Checkpoint not found after rollback",
            )
        return ApiResponse(data=updated)

    @delete("/fine-tune/checkpoints/{checkpoint_id:str}", status_code=200)
    async def delete_checkpoint(
        self,
        state: State,
        checkpoint_id: str,
    ) -> ApiResponse[None]:
        """Delete a checkpoint (rejects active checkpoint)."""
        app_state: AppState = state.app_state
        db = app_state.persistence.get_db()
        from synthorg.persistence.sqlite.fine_tune_repo import (  # noqa: PLC0415
            SQLiteFineTuneCheckpointRepository,
        )

        repo = SQLiteFineTuneCheckpointRepository(db)
        from synthorg.persistence.errors import QueryError  # noqa: PLC0415

        try:
            await repo.delete_checkpoint(checkpoint_id)
        except QueryError as exc:
            raise ClientException(
                detail=str(exc),
                status_code=HTTP_409_CONFLICT,
            ) from exc
        return ApiResponse(data=None)

    # -- Run history -------------------------------------------------

    @get("/fine-tune/runs")
    async def list_runs(
        self,
        state: State,
        limit: int = 50,
        offset: int = 0,
    ) -> ApiResponse[tuple[FineTuneRun, ...]]:
        """List historical pipeline runs."""
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)
        app_state: AppState = state.app_state
        db = app_state.persistence.get_db()
        from synthorg.persistence.sqlite.fine_tune_repo import (  # noqa: PLC0415
            SQLiteFineTuneRunRepository,
        )

        repo = SQLiteFineTuneRunRepository(db)
        runs, _ = await repo.list_runs(limit=limit, offset=offset)
        return ApiResponse(data=runs)

    # -- Embedder config ---------------------------------------------

    @get("/embedder")
    async def get_active_embedder(
        self,
        state: State,
    ) -> ApiResponse[ActiveEmbedderResponse]:
        """Get the active embedder configuration."""
        app_state: AppState = state.app_state
        result = ActiveEmbedderResponse()
        if app_state.has_settings_service:
            svc = app_state.settings_service
            try:
                provider_sv = await svc.get(
                    "memory",
                    "embedder_provider",
                )
                model_sv = await svc.get("memory", "embedder_model")
                dims_sv = await svc.get("memory", "embedder_dims")
                dims_value: int | None = None
                if dims_sv.value:
                    try:
                        dims_value = int(dims_sv.value)
                    except ValueError, TypeError:
                        logger.warning(
                            MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
                            setting="embedder_dims",
                            value=dims_sv.value,
                            reason="invalid integer value",
                        )
                result = ActiveEmbedderResponse(
                    provider=provider_sv.value or None,
                    model=model_sv.value or None,
                    dims=dims_value,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    MEMORY_EMBEDDER_SETTINGS_READ_FAILED,
                    exc_info=True,
                )
        return ApiResponse(data=result)


# -- Preflight helpers ------------------------------------------------


def _run_preflight_checks(
    request: FineTuneRequest,
) -> list[PreflightCheck]:
    """Run all pre-flight validation checks."""
    checks: list[PreflightCheck] = []
    checks.append(_check_dependencies())
    checks.append(_check_gpu())
    checks.append(_check_documents(request.source_dir))
    output_dir = request.output_dir or request.source_dir
    checks.append(_check_disk_space(output_dir))
    return checks


def _check_documents(source_dir: str) -> PreflightCheck:
    """Check source directory has enough documents."""
    from pathlib import Path  # noqa: PLC0415

    src = Path(source_dir)
    if not src.exists():
        return PreflightCheck(
            name="documents",
            status="fail",
            message="Source directory not found",
        )
    count = sum(1 for ext in ("*.txt", "*.md", "*.rst") for _ in src.rglob(ext))
    if count < 10:  # noqa: PLR2004
        return PreflightCheck(
            name="documents",
            status="fail",
            message=f"Too few documents ({count}), minimum 10 required",
        )
    if count < 50:  # noqa: PLR2004
        return PreflightCheck(
            name="documents",
            status="warn",
            message=f"Low document count ({count}), 50+ recommended",
        )
    return PreflightCheck(
        name="documents",
        status="pass",
        message=f"{count} documents found",
    )


def _check_dependencies() -> PreflightCheck:
    """Check if fine-tuning ML dependencies are installed."""
    try:
        from synthorg.memory.embedding.fine_tune import (  # noqa: PLC0415
            _import_sentence_transformers,
            _import_torch,
        )

        _import_torch()
        _import_sentence_transformers()
    except (ImportError, FineTuneDependencyError) as exc:
        return PreflightCheck(
            name="dependencies",
            status="fail",
            message="Missing ML dependencies",
            detail=str(exc),
        )
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        return PreflightCheck(
            name="dependencies",
            status="fail",
            message=f"Dependency check failed: {type(exc).__name__}",
            detail=str(exc),
        )
    return PreflightCheck(
        name="dependencies",
        status="pass",
        message="ML dependencies installed",
    )


def _check_gpu() -> PreflightCheck:
    """Best-effort GPU availability check."""
    try:
        import torch  # type: ignore[import-not-found]  # noqa: PLC0415

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            vram_gb = props.total_memory / (1024**3)
            return PreflightCheck(
                name="gpu",
                status="pass",
                message=f"GPU available: {props.name}",
                detail=f"VRAM: {vram_gb:.1f} GB",
            )
        return PreflightCheck(
            name="gpu",
            status="warn",
            message="No GPU detected -- training will be slow",
            detail="CPU-only mode",
        )
    except ImportError:
        return PreflightCheck(
            name="gpu",
            status="warn",
            message="Cannot detect GPU (torch not installed)",
        )
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        return PreflightCheck(
            name="gpu",
            status="warn",
            message=f"GPU detection error: {type(exc).__name__}",
            detail=str(exc),
        )


def _recommend_batch_size() -> int | None:
    """Recommend batch size based on available VRAM."""
    try:
        import torch  # noqa: PLC0415

        if not torch.cuda.is_available():
            return 16
        props = torch.cuda.get_device_properties(0)
        vram_gb = props.total_memory / (1024**3)
        if vram_gb >= 40:  # noqa: PLR2004
            return 128
        if vram_gb >= 16:  # noqa: PLR2004
            return 64
        if vram_gb >= 8:  # noqa: PLR2004
            return 32
        return 16  # noqa: TRY300
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        logger.debug(
            MEMORY_FINE_TUNE_PREFLIGHT_COMPLETED,
            note="batch size recommendation failed",
            error=str(exc),
        )
        return None


def _check_disk_space(source_dir: str) -> PreflightCheck:
    """Check available disk space for fine-tuning output."""
    import shutil  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    try:
        path = Path(source_dir) if Path(source_dir).exists() else Path()
        usage = shutil.disk_usage(path)
        free_gb = usage.free / (1024**3)
        if free_gb < 1:
            return PreflightCheck(
                name="disk_space",
                status="fail",
                message="Insufficient disk space",
                detail=f"{free_gb:.1f} GB free",
            )
        if free_gb < 5:  # noqa: PLR2004
            return PreflightCheck(
                name="disk_space",
                status="warn",
                message="Low disk space",
                detail=f"{free_gb:.1f} GB free, 5+ GB recommended",
            )
        return PreflightCheck(
            name="disk_space",
            status="pass",
            message=f"{free_gb:.1f} GB available",
        )
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        return PreflightCheck(
            name="disk_space",
            status="warn",
            message=f"Could not check disk space: {type(exc).__name__}",
        )
