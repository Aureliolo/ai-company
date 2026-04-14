"""Per-agent sandbox lifecycle strategy.

Reuses a container for all tool calls by the same agent.  After
``release()`` the container is kept alive for a configurable grace
period, then destroyed.  A subsequent ``acquire()`` within the grace
window cancels the timer and returns the warm container.
"""

import asyncio
from time import monotonic
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.sandbox import (
    SANDBOX_LIFECYCLE_ACQUIRE,
    SANDBOX_LIFECYCLE_CLEANUP,
    SANDBOX_LIFECYCLE_GRACE_EXPIRED,
    SANDBOX_LIFECYCLE_RELEASE,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from synthorg.tools.sandbox.lifecycle.config import SandboxLifecycleConfig
    from synthorg.tools.sandbox.lifecycle.protocol import ContainerHandle

logger = get_logger(__name__)


class PerAgentStrategy:
    """Reuse a container per *owner_id*, destroy after grace period."""

    def __init__(self, config: SandboxLifecycleConfig) -> None:
        """Initialize the per-agent lifecycle strategy.

        Args:
            config: Lifecycle configuration (grace period, max idle, etc.).
        """
        self._grace_seconds = config.grace_period_seconds
        self._max_idle = config.max_idle_seconds
        self._containers: dict[str, ContainerHandle] = {}
        self._last_used: dict[str, float] = {}
        self._timers: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        *,
        owner_id: str,
        create_fn: Callable[[], Awaitable[ContainerHandle]],
    ) -> ContainerHandle:
        """Return an existing container or create a new one."""
        async with self._lock:
            self._cancel_timer(owner_id)

            if owner_id in self._containers:
                logger.info(
                    SANDBOX_LIFECYCLE_ACQUIRE,
                    strategy="per-agent",
                    owner_id=owner_id,
                    reused=True,
                )
                self._last_used[owner_id] = monotonic()
                return self._containers[owner_id]

        # Release the lock while creating (create_fn may be slow).
        handle = await create_fn()

        async with self._lock:
            self._containers[owner_id] = handle
            self._last_used[owner_id] = monotonic()
            logger.info(
                SANDBOX_LIFECYCLE_ACQUIRE,
                strategy="per-agent",
                owner_id=owner_id,
                reused=False,
                container_id=handle.container_id,
            )
            return handle

    async def release(
        self,
        *,
        owner_id: str,
        destroy_fn: Callable[[ContainerHandle], Awaitable[None]],
    ) -> None:
        """Start a grace-period timer; destroy after expiry."""
        async with self._lock:
            if owner_id not in self._containers:
                return

            self._cancel_timer(owner_id)
            logger.info(
                SANDBOX_LIFECYCLE_RELEASE,
                strategy="per-agent",
                owner_id=owner_id,
                action="grace-start",
                grace_seconds=self._grace_seconds,
            )

            async def _grace_expire() -> None:
                await asyncio.sleep(self._grace_seconds)
                async with self._lock:
                    handle = self._containers.pop(owner_id, None)
                    self._last_used.pop(owner_id, None)
                    self._timers.pop(owner_id, None)
                if handle is not None:
                    logger.info(
                        SANDBOX_LIFECYCLE_GRACE_EXPIRED,
                        strategy="per-agent",
                        owner_id=owner_id,
                        container_id=handle.container_id,
                    )
                    try:
                        await destroy_fn(handle)
                    except Exception:
                        logger.warning(
                            "sandbox.lifecycle.destroy_failed",
                            strategy="per-agent",
                            owner_id=owner_id,
                            container_id=handle.container_id,
                        )

            self._timers[owner_id] = asyncio.create_task(
                _grace_expire(),
                name=f"sandbox-grace-{owner_id}",
            )

    async def cleanup_all(
        self,
        *,
        destroy_fn: Callable[[ContainerHandle], Awaitable[None]],
    ) -> None:
        """Cancel all timers, destroy all containers."""
        async with self._lock:
            tasks_to_cancel = list(self._timers.values())
            self._timers.clear()

            for task in tasks_to_cancel:
                task.cancel()
            if tasks_to_cancel:
                await asyncio.gather(
                    *tasks_to_cancel,
                    return_exceptions=True,
                )

            handles = list(self._containers.values())
            count = len(handles)
            self._containers.clear()
            self._last_used.clear()

        for handle in handles:
            try:
                await destroy_fn(handle)
            except Exception:
                logger.warning(
                    "sandbox.lifecycle.destroy_failed",
                    strategy="per-agent",
                    container_id=handle.container_id,
                )

        logger.info(
            SANDBOX_LIFECYCLE_CLEANUP,
            strategy="per-agent",
            destroyed_count=count,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cancel_timer(self, owner_id: str) -> None:
        """Cancel a pending grace timer (must hold ``_lock``)."""
        timer = self._timers.pop(owner_id, None)
        if timer is not None and not timer.done():
            timer.cancel()
