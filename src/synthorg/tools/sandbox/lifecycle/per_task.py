"""Per-task sandbox lifecycle strategy.

Reuses a container for all tool calls within the same task.  On
``release()`` the container is destroyed immediately -- task boundaries
are clean cuts with no grace period.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.sandbox import (
    SANDBOX_LIFECYCLE_ACQUIRE,
    SANDBOX_LIFECYCLE_CLEANUP,
    SANDBOX_LIFECYCLE_RELEASE,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from synthorg.tools.sandbox.lifecycle.protocol import ContainerHandle

logger = get_logger(__name__)


class PerTaskStrategy:
    """Reuse a container per *owner_id*, destroy immediately on release."""

    def __init__(self) -> None:
        """Initialize the per-task lifecycle strategy."""
        self._containers: dict[str, ContainerHandle] = {}

    async def acquire(
        self,
        *,
        owner_id: str,
        create_fn: Callable[[], Awaitable[ContainerHandle]],
    ) -> ContainerHandle:
        """Return an existing container or create a new one."""
        if owner_id in self._containers:
            logger.debug(
                SANDBOX_LIFECYCLE_ACQUIRE,
                strategy="per-task",
                owner_id=owner_id,
                reused=True,
            )
            return self._containers[owner_id]

        handle = await create_fn()
        self._containers[owner_id] = handle
        logger.debug(
            SANDBOX_LIFECYCLE_ACQUIRE,
            strategy="per-task",
            owner_id=owner_id,
            reused=False,
            container_id=handle.container_id,
        )
        return handle

    async def release(self, *, owner_id: str) -> None:
        """Destroy the container immediately (task boundary)."""
        handle = self._containers.pop(owner_id, None)
        if handle is None:
            return
        logger.debug(
            SANDBOX_LIFECYCLE_RELEASE,
            strategy="per-task",
            owner_id=owner_id,
            action="destroy",
            container_id=handle.container_id,
        )

    async def cleanup_all(self) -> None:
        """Destroy all tracked containers."""
        count = len(self._containers)
        self._containers.clear()
        logger.info(
            SANDBOX_LIFECYCLE_CLEANUP,
            strategy="per-task",
            destroyed_count=count,
        )
