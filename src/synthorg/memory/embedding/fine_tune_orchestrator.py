"""Fine-tuning pipeline orchestrator.

Manages background execution of the five-stage pipeline with state
persistence, cancellation, WebSocket progress events, and resume
from last completed stage.
"""

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from synthorg.memory.embedding.cancellation import CancellationToken
from synthorg.memory.embedding.fine_tune import (
    FineTuneStage,
    contrastive_fine_tune,
    deploy_checkpoint,
    evaluate_checkpoint,
    generate_training_data,
    mine_hard_negatives,
)
from synthorg.memory.embedding.fine_tune_models import (
    FineTuneRun,
    FineTuneRunConfig,
    FineTuneStatus,
)
from synthorg.memory.errors import FineTuneCancelledError
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_FINE_TUNE_CANCELLED,
    MEMORY_FINE_TUNE_COMPLETED,
    MEMORY_FINE_TUNE_FAILED,
    MEMORY_FINE_TUNE_PROGRESS,
    MEMORY_FINE_TUNE_STAGE_ENTERED,
    MEMORY_FINE_TUNE_STARTED,
    MEMORY_FINE_TUNE_WS_EMIT_FAILED,
)

if TYPE_CHECKING:
    from synthorg.memory.embedding.fine_tune_models import (
        FineTuneRequest,
    )
    from synthorg.persistence.sqlite.fine_tune_repo import (
        SQLiteFineTuneCheckpointRepository,
        SQLiteFineTuneRunRepository,
    )

logger = get_logger(__name__)

# Minimum interval between WS progress events.
_PROGRESS_THROTTLE_SEC = 1.0


class FineTuneOrchestrator:
    """Background pipeline orchestrator.

    Manages the lifecycle of fine-tuning runs: start, resume,
    cancel, and startup recovery.

    Args:
        run_repo: SQLite repository for run state.
        checkpoint_repo: SQLite repository for checkpoints.
        settings_service: Runtime settings (for deploy stage).
        channels_plugin: Litestar WS plugin (for progress events).
        llm_provider: Optional LLM provider for data generation.
    """

    def __init__(
        self,
        *,
        run_repo: SQLiteFineTuneRunRepository,
        checkpoint_repo: SQLiteFineTuneCheckpointRepository,
        settings_service: object | None = None,
        channels_plugin: Any | None = None,
        llm_provider: object | None = None,
    ) -> None:
        self._run_repo = run_repo
        self._checkpoint_repo = checkpoint_repo
        self._settings_service = settings_service
        self._channels_plugin = channels_plugin
        self._llm_provider = llm_provider
        self._current_task: asyncio.Task[None] | None = None
        self._cancellation: CancellationToken | None = None
        self._current_run: FineTuneRun | None = None

    # -- Public API ---------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether a pipeline run is currently active."""
        return self._current_task is not None and not self._current_task.done()

    @property
    def current_run(self) -> FineTuneRun | None:
        """The currently active or most recently completed run."""
        return self._current_run

    async def start(
        self,
        request: FineTuneRequest,
    ) -> FineTuneRun:
        """Start a new pipeline run.

        Args:
            request: Fine-tuning request parameters.

        Returns:
            The created run record.

        Raises:
            RuntimeError: If a run is already active (409 Conflict).
        """
        if self.is_running:
            msg = "A fine-tuning run is already active"
            raise RuntimeError(msg)

        config = _build_config(request)
        now = datetime.now(UTC)
        run = FineTuneRun(
            id=str(uuid.uuid4()),
            stage=FineTuneStage.GENERATING_DATA,
            config=config,
            started_at=now,
            updated_at=now,
        )
        await self._run_repo.save_run(run)
        self._current_run = run
        logger.info(
            MEMORY_FINE_TUNE_STARTED,
            run_id=run.id,
            source_dir=config.source_dir,
        )

        self._cancellation = CancellationToken()
        self._current_task = asyncio.create_task(
            self._execute_pipeline(run),
        )
        self._current_task.add_done_callback(self._on_task_done)
        return run

    async def resume(self, run_id: str) -> FineTuneRun:
        """Resume a failed/cancelled run from last completed stage.

        Args:
            run_id: ID of the run to resume.

        Returns:
            The resumed run record.

        Raises:
            RuntimeError: If a run is already active.
            ValueError: If run not found or not resumable.
        """
        if self.is_running:
            msg = "A fine-tuning run is already active"
            raise RuntimeError(msg)
        run = await self._run_repo.get_run(run_id)
        if run is None:
            msg = f"Run {run_id} not found"
            raise ValueError(msg)
        if run.stage not in (
            FineTuneStage.FAILED,
            FineTuneStage.COMPLETE,
        ):
            msg = f"Run {run_id} is not resumable (stage={run.stage})"
            raise ValueError(msg)

        now = datetime.now(UTC)
        resumed = run.model_copy(
            update={
                "stage": FineTuneStage.GENERATING_DATA,
                "progress": None,
                "error": None,
                "updated_at": now,
                "completed_at": None,
            },
        )
        await self._run_repo.save_run(resumed)
        self._current_run = resumed
        logger.info(
            MEMORY_FINE_TUNE_STARTED,
            run_id=run_id,
            resumed=True,
            stages_completed=run.stages_completed,
        )

        self._cancellation = CancellationToken()
        self._current_task = asyncio.create_task(
            self._execute_pipeline(resumed),
        )
        self._current_task.add_done_callback(self._on_task_done)
        return resumed

    async def cancel(self) -> None:
        """Cancel the active pipeline run."""
        if self._cancellation is not None:
            self._cancellation.cancel()
            logger.info(MEMORY_FINE_TUNE_CANCELLED)

    async def recover_interrupted(self) -> int:
        """Mark interrupted runs as FAILED on startup."""
        return await self._run_repo.mark_interrupted()

    async def get_status(self) -> FineTuneStatus:
        """Get current pipeline status."""
        if self._current_run is not None:
            return FineTuneStatus(
                run_id=self._current_run.id,
                stage=self._current_run.stage,
                progress=self._current_run.progress,
                error=self._current_run.error,
            )
        # Check DB for most recent run.
        runs, _ = await self._run_repo.list_runs(limit=1)
        if runs:
            r = runs[0]
            return FineTuneStatus(
                run_id=r.id,
                stage=r.stage,
                progress=r.progress,
                error=r.error,
            )
        return FineTuneStatus()

    # -- Pipeline execution -------------------------------------------

    async def _execute_pipeline(self, run: FineTuneRun) -> None:
        """Execute stages sequentially in the background."""
        try:
            run = await self._run_stages(run)
            now = datetime.now(UTC)
            run = run.model_copy(
                update={
                    "stage": FineTuneStage.COMPLETE,
                    "progress": None,
                    "updated_at": now,
                    "completed_at": now,
                },
            )
            await self._run_repo.save_run(run)
            self._current_run = run
            logger.info(
                MEMORY_FINE_TUNE_COMPLETED,
                run_id=run.id,
            )
            self._emit_ws("memory.fine_tune.completed", run)
        except FineTuneCancelledError:
            await self._mark_failed(
                run,
                "cancelled by user",
            )
            self._emit_ws(
                "memory.fine_tune.failed",
                self._current_run if self._current_run is not None else run,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            await self._mark_failed(run, str(exc))
            self._emit_ws(
                "memory.fine_tune.failed",
                self._current_run if self._current_run is not None else run,
            )
            logger.exception(
                MEMORY_FINE_TUNE_FAILED,
                run_id=run.id,
                error=str(exc),
            )

    async def _run_stages(
        self,
        run: FineTuneRun,
    ) -> FineTuneRun:
        """Run all stages, skipping completed ones (resume)."""
        cfg = run.config
        out_dir = f"{cfg.output_dir}/runs/{run.id}"
        completed = set(run.stages_completed)

        # Stage 1: Generate training data.
        if "generating_data" not in completed:
            run = await self._enter_stage(
                run,
                FineTuneStage.GENERATING_DATA,
            )
            train_path, val_path = await generate_training_data(
                source_dir=cfg.source_dir,
                output_dir=out_dir,
                llm_provider=self._llm_provider,
                validation_split=cfg.validation_split,
                progress_callback=self._make_progress_cb(run),
                cancellation=self._cancellation,
            )
            run = await self._complete_stage(
                run,
                "generating_data",
            )
        else:
            train_path = Path(f"{out_dir}/training.jsonl")
            val_path = Path(f"{out_dir}/validation.jsonl")

        # Stage 2: Mine hard negatives.
        if "mining_negatives" not in completed:
            run = await self._enter_stage(
                run,
                FineTuneStage.MINING_NEGATIVES,
            )
            triples_path = await mine_hard_negatives(
                training_data_path=str(train_path),
                base_model=cfg.base_model,
                output_dir=out_dir,
                top_k=cfg.top_k,
                progress_callback=self._make_progress_cb(run),
                cancellation=self._cancellation,
            )
            run = await self._complete_stage(
                run,
                "mining_negatives",
            )
        else:
            triples_path = Path(f"{out_dir}/training_triples.jsonl")

        # Stage 3: Contrastive fine-tuning.
        if "training" not in completed:
            run = await self._enter_stage(
                run,
                FineTuneStage.TRAINING,
            )
            checkpoint_path = await contrastive_fine_tune(
                training_data_path=str(triples_path),
                base_model=cfg.base_model,
                output_dir=out_dir,
                epochs=cfg.epochs,
                learning_rate=cfg.learning_rate,
                temperature=cfg.temperature,
                batch_size=cfg.batch_size,
                progress_callback=self._make_progress_cb(run),
                cancellation=self._cancellation,
            )
            run = await self._complete_stage(run, "training")
        else:
            checkpoint_path = Path(f"{out_dir}/checkpoint")

        # Stage 4: Evaluation.
        if "evaluating" not in completed:
            run = await self._enter_stage(
                run,
                FineTuneStage.EVALUATING,
            )
            await evaluate_checkpoint(
                checkpoint_path=str(checkpoint_path),
                base_model=cfg.base_model,
                validation_data_path=str(val_path),
                output_dir=out_dir,
                progress_callback=self._make_progress_cb(run),
                cancellation=self._cancellation,
            )
            run = await self._complete_stage(run, "evaluating")

        # Stage 5: Deploy.
        if "deploying" not in completed:
            run = await self._enter_stage(
                run,
                FineTuneStage.DEPLOYING,
            )
            await deploy_checkpoint(
                checkpoint_path=str(checkpoint_path),
                settings_service=self._settings_service,
            )
            run = await self._complete_stage(run, "deploying")

        return run

    # -- Stage lifecycle helpers --------------------------------------

    async def _enter_stage(
        self,
        run: FineTuneRun,
        stage: FineTuneStage,
    ) -> FineTuneRun:
        """Mark a stage as entered."""
        now = datetime.now(UTC)
        run = run.model_copy(
            update={
                "stage": stage,
                "progress": 0.0,
                "updated_at": now,
            },
        )
        await self._run_repo.save_run(run)
        self._current_run = run
        logger.info(
            MEMORY_FINE_TUNE_STAGE_ENTERED,
            run_id=run.id,
            stage=stage.value,
        )
        self._emit_ws("memory.fine_tune.stage_changed", run)
        return run

    async def _complete_stage(
        self,
        run: FineTuneRun,
        stage_name: str,
    ) -> FineTuneRun:
        """Record a stage as completed."""
        now = datetime.now(UTC)
        run = run.model_copy(
            update={
                "progress": None,
                "updated_at": now,
                "stages_completed": (
                    *run.stages_completed,
                    stage_name,
                ),
            },
        )
        await self._run_repo.save_run(run)
        self._current_run = run
        return run

    async def _mark_failed(
        self,
        run: FineTuneRun,
        error: str,
    ) -> None:
        """Mark the run as failed."""
        now = datetime.now(UTC)
        run = run.model_copy(
            update={
                "stage": FineTuneStage.FAILED,
                "progress": None,
                "error": error,
                "updated_at": now,
                "completed_at": now,
            },
        )
        await self._run_repo.save_run(run)
        self._current_run = run

    # -- Progress + WebSocket helpers ---------------------------------

    def _make_progress_cb(
        self,
        run: FineTuneRun,
    ) -> Any:
        """Create a throttled progress callback for a stage.

        The callback captures the run ID and reads ``self._current_run``
        at call time so it always reflects the latest stage/progress,
        even when invoked from a worker thread via ``asyncio.to_thread``.
        """
        run_id = run.id
        last_emit = 0.0

        def _cb(progress: float) -> None:
            nonlocal last_emit
            now = time.monotonic()
            if now - last_emit < _PROGRESS_THROTTLE_SEC:
                return
            last_emit = now
            current = self._current_run
            if current is not None and current.id == run_id:
                updated = current.model_copy(
                    update={"progress": progress},
                )
                self._current_run = updated
            else:
                updated = run.model_copy(
                    update={"progress": progress},
                )
                self._current_run = updated
            logger.debug(
                MEMORY_FINE_TUNE_PROGRESS,
                run_id=run_id,
                progress=progress,
            )
            self._emit_ws(
                "memory.fine_tune.progress",
                self._current_run if self._current_run is not None else run,
            )

        return _cb

    def _emit_ws(
        self,
        event_type: str,
        run: FineTuneRun,
    ) -> None:
        """Best-effort emit a WebSocket event."""
        if self._channels_plugin is None:
            return
        try:
            payload = json.dumps(
                {
                    "event_type": event_type,
                    "channel": "system",
                    "payload": {
                        "run_id": run.id,
                        "stage": run.stage.value,
                        "progress": run.progress,
                    },
                },
            )
            self._channels_plugin.publish(
                payload,
                channels=["system"],
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                MEMORY_FINE_TUNE_WS_EMIT_FAILED,
                event_type=event_type,
            )

    @staticmethod
    def _on_task_done(task: asyncio.Task[None]) -> None:
        """Log unhandled exceptions from pipeline background tasks."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                MEMORY_FINE_TUNE_FAILED,
                error=str(exc),
                note="unhandled exception in pipeline task",
            )


# -- Config builder ---------------------------------------------------


def _build_config(request: FineTuneRequest) -> FineTuneRunConfig:
    """Build a frozen config snapshot from a request."""
    r = request
    return FineTuneRunConfig(
        source_dir=r.source_dir,
        base_model=(r.base_model if r.base_model is not None else "auto"),
        output_dir=(r.output_dir if r.output_dir is not None else "/data/fine-tune"),
        epochs=r.epochs if r.epochs is not None else 3,
        learning_rate=(r.learning_rate if r.learning_rate is not None else 1e-5),
        temperature=(r.temperature if r.temperature is not None else 0.02),
        top_k=r.top_k if r.top_k is not None else 4,
        batch_size=(r.batch_size if r.batch_size is not None else 128),
        validation_split=(
            r.validation_split if r.validation_split is not None else 0.1
        ),
    )
