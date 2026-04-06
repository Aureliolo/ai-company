"""Post-execution memory hooks -- distillation capture and procedural memory.

Extracted from ``agent_engine.py`` to keep the engine file under 800 lines.
The functions here are standalone async helpers that receive all dependencies
as explicit parameters (no ``self``).
"""

import asyncio
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.consolidation import (
    DISTILLATION_CAPTURE_SKIPPED,
)
from synthorg.observability.events.procedural_memory import (
    PROCEDURAL_MEMORY_ERROR,
    PROCEDURAL_MEMORY_SKIPPED,
)

if TYPE_CHECKING:
    from synthorg.engine.loop_protocol import ExecutionResult
    from synthorg.engine.recovery import RecoveryResult
    from synthorg.memory.procedural.models import ProceduralMemoryConfig
    from synthorg.memory.procedural.proposer import ProceduralMemoryProposer
    from synthorg.memory.protocol import MemoryBackend

logger = get_logger(__name__)


async def try_capture_distillation(
    execution_result: ExecutionResult,
    agent_id: str,
    task_id: str,
    *,
    distillation_capture_enabled: bool,
    memory_backend: MemoryBackend | None,
) -> None:
    """Capture trajectory distillation at task completion (non-critical).

    Skips when distillation capture is disabled or no memory backend is
    configured; both skip paths emit a DEBUG log so operators
    investigating "why no distillation entries?" can tell which branch
    was hit.  Captures regardless of termination reason -- successful
    runs, errors, timeouts, and budget exhaustions all produce useful
    trajectory context for downstream consolidation.  Non-system
    failures are swallowed and logged by ``capture_distillation``;
    system errors (``MemoryError``, ``RecursionError``) propagate.
    """
    if not distillation_capture_enabled:
        logger.debug(
            DISTILLATION_CAPTURE_SKIPPED,
            agent_id=agent_id,
            task_id=task_id,
            reason="capture_disabled",
        )
        return
    if memory_backend is None:
        logger.debug(
            DISTILLATION_CAPTURE_SKIPPED,
            agent_id=agent_id,
            task_id=task_id,
            reason="no_memory_backend",
        )
        return
    from pydantic import TypeAdapter  # noqa: PLC0415

    from synthorg.core.types import NotBlankStr  # noqa: PLC0415
    from synthorg.memory.consolidation import capture_distillation  # noqa: PLC0415

    try:
        _nb = TypeAdapter(NotBlankStr)
        await capture_distillation(
            execution_result,
            agent_id=_nb.validate_python(agent_id),
            task_id=_nb.validate_python(task_id),
            backend=memory_backend,
        )
    except MemoryError, RecursionError:
        raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(
            DISTILLATION_CAPTURE_SKIPPED,
            agent_id=agent_id,
            task_id=task_id,
            reason=f"validation_or_capture_failed: {type(exc).__name__}: {exc}",
            exc_info=True,
        )


async def try_procedural_memory(  # noqa: PLR0913
    execution_result: ExecutionResult,
    recovery_result: RecoveryResult | None,
    agent_id: str,
    task_id: str,
    *,
    procedural_proposer: ProceduralMemoryProposer | None,
    memory_backend: MemoryBackend | None,
    procedural_memory_config: ProceduralMemoryConfig | None = None,
) -> None:
    """Run procedural memory pipeline (non-critical, never fatal).

    Skips when the proposer is not configured or no recovery occurred
    (non-error terminations).  Both skip paths emit a DEBUG log so
    operators can diagnose "why no procedural memories?"
    """
    if procedural_proposer is None or recovery_result is None:
        logger.debug(
            PROCEDURAL_MEMORY_SKIPPED,
            agent_id=agent_id,
            task_id=task_id,
            reason=(
                "no_proposer" if procedural_proposer is None else "no_recovery_result"
            ),
        )
        return
    if memory_backend is None:  # pragma: no cover -- guarded by caller
        logger.debug(
            PROCEDURAL_MEMORY_SKIPPED,
            agent_id=agent_id,
            task_id=task_id,
            reason="no_memory_backend",
        )
        return
    try:
        from synthorg.memory.procedural.pipeline import (  # noqa: PLC0415
            propose_procedural_memory,
        )

        await propose_procedural_memory(
            execution_result,
            recovery_result,
            agent_id,
            task_id,
            proposer=procedural_proposer,
            memory_backend=memory_backend,
            config=procedural_memory_config,
        )
    except MemoryError, RecursionError:
        raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(
            PROCEDURAL_MEMORY_ERROR,
            agent_id=agent_id,
            task_id=task_id,
            error=f"procedural memory failed: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
