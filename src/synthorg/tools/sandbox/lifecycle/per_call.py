"""Per-call sandbox lifecycle strategy.

Wraps the current ephemeral behaviour: every ``acquire()`` creates a
fresh container, and ``release()`` is a no-op because the caller
(``DockerSandbox``) destroys the container in its own finally block.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.sandbox import (
    SANDBOX_LIFECYCLE_ACQUIRE,
    SANDBOX_LIFECYCLE_RELEASE,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from synthorg.tools.sandbox.lifecycle.protocol import ContainerHandle

logger = get_logger(__name__)


class PerCallStrategy:
    """Create a new container for every ``execute()`` call."""

    async def acquire(
        self,
        *,
        owner_id: str,
        create_fn: Callable[[], Awaitable[ContainerHandle]],
    ) -> ContainerHandle:
        """Create a fresh container (no reuse)."""
        logger.debug(
            SANDBOX_LIFECYCLE_ACQUIRE,
            strategy="per-call",
            owner_id=owner_id,
            reused=False,
        )
        return await create_fn()

    async def release(self, *, owner_id: str) -> None:
        """No-op -- the caller destroys the container."""
        logger.debug(
            SANDBOX_LIFECYCLE_RELEASE,
            strategy="per-call",
            owner_id=owner_id,
            action="noop",
        )

    async def cleanup_all(self) -> None:
        """No-op -- nothing tracked."""
