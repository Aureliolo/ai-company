"""Checkpoint recovery strategy.

Resumes execution from the last persisted checkpoint on crash.
After ``max_resume_attempts`` resume attempts, falls back to the
``FailAndReassignStrategy``.
"""

import asyncio
from typing import Final

from ai_company.engine.checkpoint.models import CheckpointConfig  # noqa: TC001
from ai_company.engine.context import AgentContext  # noqa: TC001
from ai_company.engine.recovery import (
    FailAndReassignStrategy,
    RecoveryResult,
    RecoveryStrategy,
)
from ai_company.engine.task_execution import TaskExecution  # noqa: TC001
from ai_company.observability import get_logger
from ai_company.observability.events.checkpoint import (
    CHECKPOINT_LOAD_FAILED,
    CHECKPOINT_LOADED,
    CHECKPOINT_RECOVERY_FALLBACK,
    CHECKPOINT_RECOVERY_NO_CHECKPOINT,
    CHECKPOINT_RECOVERY_RESUME,
    CHECKPOINT_RECOVERY_START,
)
from ai_company.persistence.repositories import CheckpointRepository  # noqa: TC001

logger = get_logger(__name__)


class CheckpointRecoveryStrategy:
    """Resume from the last checkpoint on crash.

    Loads the latest checkpoint for the execution and returns a
    ``RecoveryResult`` with the serialized checkpoint context
    (making ``can_resume`` evaluate to ``True``).  After
    ``max_resume_attempts`` resume attempts, delegates to the
    fallback strategy (default: fail-and-reassign).

    Args:
        checkpoint_repo: Repository for loading checkpoints.
        config: Checkpoint configuration (controls max_resume_attempts).
        fallback: Fallback recovery strategy; defaults to
            ``FailAndReassignStrategy``.
    """

    STRATEGY_TYPE: Final[str] = "checkpoint"

    def __init__(
        self,
        *,
        checkpoint_repo: CheckpointRepository,
        config: CheckpointConfig,
        fallback: RecoveryStrategy | None = None,
    ) -> None:
        self._checkpoint_repo = checkpoint_repo
        self._config = config
        self._fallback: RecoveryStrategy = fallback or FailAndReassignStrategy()
        self._resume_counts: dict[str, int] = {}
        self._resume_lock = asyncio.Lock()

    async def recover(
        self,
        *,
        task_execution: TaskExecution,
        error_message: str,
        context: AgentContext,
    ) -> RecoveryResult:
        """Apply checkpoint recovery.

        1. Load the latest checkpoint for the execution.
        2. If no checkpoint exists, delegate to fallback.
        3. If resume attempts are exhausted, delegate to fallback.
        4. Otherwise, return a ``RecoveryResult`` with the checkpoint
           context for resume.

        Args:
            task_execution: Current execution state.
            error_message: Description of the failure.
            context: Full agent context at the time of failure.

        Returns:
            ``RecoveryResult`` — either resumable or fallback.
        """
        execution_id = context.execution_id
        task_id = task_execution.task.id

        logger.info(
            CHECKPOINT_RECOVERY_START,
            execution_id=execution_id,
            task_id=task_id,
            strategy=self.STRATEGY_TYPE,
        )

        # Load the latest checkpoint
        try:
            checkpoint = await self._checkpoint_repo.get_latest(
                execution_id=execution_id,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                CHECKPOINT_LOAD_FAILED,
                execution_id=execution_id,
                task_id=task_id,
            )
            checkpoint = None

        if checkpoint is None:
            logger.info(
                CHECKPOINT_RECOVERY_NO_CHECKPOINT,
                execution_id=execution_id,
                task_id=task_id,
            )
            return await self._delegate_to_fallback(
                task_execution=task_execution,
                error_message=error_message,
                context=context,
            )

        logger.debug(
            CHECKPOINT_LOADED,
            execution_id=execution_id,
            checkpoint_id=checkpoint.id,
            turn_number=checkpoint.turn_number,
        )

        # Check resume attempts (locked to prevent TOCTOU race)
        async with self._resume_lock:
            resume_count = self._resume_counts.get(execution_id, 0)
            if resume_count >= self._config.max_resume_attempts:
                logger.info(
                    CHECKPOINT_RECOVERY_FALLBACK,
                    execution_id=execution_id,
                    task_id=task_id,
                    resume_count=resume_count,
                    max_resume_attempts=self._config.max_resume_attempts,
                    reason="max_resume_attempts_exhausted",
                )
                self._resume_counts.pop(execution_id, None)
                return await self._delegate_to_fallback(
                    task_execution=task_execution,
                    error_message=error_message,
                    context=context,
                )

            # Increment counter
            self._resume_counts[execution_id] = resume_count + 1

        snapshot = context.to_snapshot()
        logger.info(
            CHECKPOINT_RECOVERY_RESUME,
            execution_id=execution_id,
            task_id=task_id,
            checkpoint_id=checkpoint.id,
            turn_number=checkpoint.turn_number,
            resume_attempt=resume_count + 1,
            max_resume_attempts=self._config.max_resume_attempts,
        )

        return RecoveryResult(
            task_execution=task_execution,
            strategy_type=self.STRATEGY_TYPE,
            context_snapshot=snapshot,
            error_message=error_message,
            checkpoint_context_json=checkpoint.context_json,
            resume_attempt=resume_count + 1,
        )

    def get_strategy_type(self) -> str:
        """Return the strategy type identifier."""
        return self.STRATEGY_TYPE

    def clear_resume_count(self, execution_id: str) -> None:
        """Clear the resume counter for a completed execution.

        Called after successful completion to reset the counter.

        Args:
            execution_id: The execution identifier to clear.
        """
        self._resume_counts.pop(execution_id, None)

    async def _delegate_to_fallback(
        self,
        *,
        task_execution: TaskExecution,
        error_message: str,
        context: AgentContext,
    ) -> RecoveryResult:
        """Delegate recovery to the fallback strategy."""
        return await self._fallback.recover(
            task_execution=task_execution,
            error_message=error_message,
            context=context,
        )
