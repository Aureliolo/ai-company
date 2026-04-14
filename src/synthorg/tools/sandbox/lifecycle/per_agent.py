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
    SANDBOX_LIFECYCLE_DESTROY_FAILED,
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
        self._idle_timers: dict[str, asyncio.Task[None]] = {}
        self._destroy_fns: dict[str, Callable[[ContainerHandle], Awaitable[None]]] = {}
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
            # Cancel idle timer -- container is now checked out.
            old_idle = self._idle_timers.pop(owner_id, None)
            if old_idle is not None and not old_idle.done():
                old_idle.cancel()

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
            # Re-check: a concurrent acquire may have won the race.
            if owner_id in self._containers:
                existing = self._containers[owner_id]
                logger.info(
                    SANDBOX_LIFECYCLE_ACQUIRE,
                    strategy="per-agent",
                    owner_id=owner_id,
                    reused=True,
                )
                self._last_used[owner_id] = monotonic()
                # Destroy the losing handle outside the lock.
                destroy_fn = self._destroy_fns.get(owner_id)
                if destroy_fn is not None:
                    try:
                        await destroy_fn(handle)
                    except Exception:
                        logger.warning(
                            SANDBOX_LIFECYCLE_DESTROY_FAILED,
                            strategy="per-agent",
                            owner_id=owner_id,
                            container_id=handle.container_id,
                        )
                return existing

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
            self._destroy_fns[owner_id] = destroy_fn
            self._reset_idle_timer(owner_id)
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
                            SANDBOX_LIFECYCLE_DESTROY_FAILED,
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
            all_tasks = list(self._timers.values()) + list(
                self._idle_timers.values(),
            )
            self._timers.clear()
            self._idle_timers.clear()
            self._destroy_fns.clear()

            for task in all_tasks:
                task.cancel()
            if all_tasks:
                await asyncio.gather(
                    *all_tasks,
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
                    SANDBOX_LIFECYCLE_DESTROY_FAILED,
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

    def _reset_idle_timer(self, owner_id: str) -> None:
        """Start or restart the idle timeout timer (must hold ``_lock``)."""
        old = self._idle_timers.pop(owner_id, None)
        if old is not None and not old.done():
            old.cancel()
        if self._max_idle <= 0:
            return

        async def _idle_expire() -> None:
            while True:
                async with self._lock:
                    last = self._last_used.get(owner_id)
                    if last is None or owner_id not in self._containers:
                        return
                    remaining = self._max_idle - (monotonic() - last)
                if remaining <= 0:
                    break
                await asyncio.sleep(remaining)
            # Idle timeout reached -- destroy.
            async with self._lock:
                handle = self._containers.pop(owner_id, None)
                self._last_used.pop(owner_id, None)
                self._idle_timers.pop(owner_id, None)
                destroy_fn = self._destroy_fns.pop(owner_id, None)
            if handle is not None and destroy_fn is not None:
                logger.info(
                    SANDBOX_LIFECYCLE_GRACE_EXPIRED,
                    strategy="per-agent",
                    owner_id=owner_id,
                    reason="idle-timeout",
                    container_id=handle.container_id,
                )
                try:
                    await destroy_fn(handle)
                except Exception:
                    logger.warning(
                        SANDBOX_LIFECYCLE_DESTROY_FAILED,
                        strategy="per-agent",
                        owner_id=owner_id,
                    )

        self._idle_timers[owner_id] = asyncio.create_task(
            _idle_expire(),
            name=f"sandbox-idle-{owner_id}",
        )
