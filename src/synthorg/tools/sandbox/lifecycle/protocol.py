"""Sandbox container lifecycle strategy protocol."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@dataclass(frozen=True, slots=True)
class ContainerHandle:
    """Opaque handle to a running sandbox container and its optional sidecar.

    Attributes:
        container_id: Docker container ID for the sandbox.
        sidecar_id: Docker container ID for the network sidecar, or ``None``
            when no sidecar was created.
        network_mode: Docker network mode for commands executing in this
            container (e.g. ``"container:<sidecar_id>"`` or ``"none"``).
    """

    container_id: str
    sidecar_id: str | None = None
    network_mode: str = "none"


@runtime_checkable
class SandboxLifecycleStrategy(Protocol):
    """Pluggable strategy for sandbox container creation and reuse.

    Implementations decide when to create new containers, when to reuse
    existing ones, and when to destroy them.  The strategy is decoupled
    from Docker internals via a ``create_fn`` callback.
    """

    async def acquire(
        self,
        *,
        owner_id: str,
        create_fn: Callable[[], Awaitable[ContainerHandle]],
    ) -> ContainerHandle:
        """Get an existing container or create a new one for *owner_id*.

        Args:
            owner_id: Opaque identifier for the lifecycle owner (agent ID,
                task ID, or a per-call UUID).
            create_fn: Async factory that creates a fresh container.

        Returns:
            A ``ContainerHandle`` ready for command execution.
        """
        ...

    async def release(self, *, owner_id: str) -> None:
        """Signal that *owner_id* no longer needs its container.

        Depending on the strategy this may destroy the container
        immediately, start a grace-period timer, or do nothing.

        Args:
            owner_id: The same identifier passed to ``acquire``.
        """
        ...

    async def cleanup_all(self) -> None:
        """Destroy all tracked containers.

        Called during backend shutdown to ensure no containers leak.
        """
        ...
