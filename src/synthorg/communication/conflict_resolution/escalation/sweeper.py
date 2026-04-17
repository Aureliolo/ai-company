"""Background task that expires stale escalations (#1418).

Runs in the event loop at ``sweeper_interval_seconds`` cadence, calling
:meth:`EscalationQueueStore.mark_expired` so PENDING rows past their
``expires_at`` transition to ``EXPIRED`` without relying on the
resolver coroutine still being alive.

Crucial for restart recovery: after a process restart, any coroutine
that was awaiting a decision has died, but the escalation row remains
``PENDING`` in the store.  The sweeper will eventually reap it.
"""

import asyncio
from datetime import UTC, datetime

from synthorg.communication.conflict_resolution.escalation.protocol import (
    EscalationQueueStore,  # noqa: TC001
)
from synthorg.observability import get_logger
from synthorg.observability.events.conflict import (
    CONFLICT_ESCALATION_EXPIRED,
    CONFLICT_ESCALATION_SWEEPER_FAILED,
    CONFLICT_ESCALATION_SWEEPER_STARTED,
    CONFLICT_ESCALATION_SWEEPER_STOPPED,
)

logger = get_logger(__name__)


class EscalationExpirationSweeper:
    """Periodic background task that expires stale escalations."""

    def __init__(
        self,
        store: EscalationQueueStore,
        *,
        interval_seconds: float = 30.0,
    ) -> None:
        """Initialise the sweeper.

        Args:
            store: The queue store whose PENDING rows will be expired.
            interval_seconds: How often to run; must be >= 1 second.
        """
        if interval_seconds < 1.0:
            msg = "interval_seconds must be >= 1.0"
            raise ValueError(msg)
        self._store = store
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Schedule the background loop.

        Idempotent: calling ``start()`` on an already-running sweeper
        is a no-op.
        """
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run(),
            name="escalation-sweeper",
        )
        logger.info(
            CONFLICT_ESCALATION_SWEEPER_STARTED,
            interval_seconds=self._interval,
        )

    async def stop(self) -> None:
        """Signal the loop to exit and await its completion."""
        self._stop_event.set()
        task = self._task
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            # Expected -- we just cancelled the task.
            pass
        except Exception as exc:
            # Best-effort shutdown; never propagate.
            logger.debug(
                CONFLICT_ESCALATION_SWEEPER_FAILED,
                error_type=type(exc).__name__,
                error=str(exc),
                note="shutdown",
            )
        finally:
            self._task = None
        logger.info(CONFLICT_ESCALATION_SWEEPER_STOPPED)

    async def _run(self) -> None:
        """Main loop body."""
        while not self._stop_event.is_set():
            try:
                await self._sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    CONFLICT_ESCALATION_SWEEPER_FAILED,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._interval,
                )
            except TimeoutError:
                continue

    async def _sweep_once(self) -> None:
        """Expire any rows whose deadline has passed."""
        now = datetime.now(UTC)
        expired = await self._store.mark_expired(now.isoformat())
        if expired:
            logger.info(
                CONFLICT_ESCALATION_EXPIRED,
                expired_count=len(expired),
                expired_ids=list(expired),
            )
