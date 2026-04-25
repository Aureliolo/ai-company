"""Checkpoint and heartbeat repository protocols."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import AwareDatetime  # noqa: TC002

from synthorg.core.types import NotBlankStr  # noqa: TC001

if TYPE_CHECKING:
    from synthorg.engine.checkpoint.models import Checkpoint, Heartbeat

__all__ = [
    "CheckpointRepository",
    "HeartbeatRepository",
]


@runtime_checkable
class CheckpointRepository(Protocol):
    """CRUD interface for checkpoint persistence."""

    async def save(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint (insert or replace by ID).

        Args:
            checkpoint: The checkpoint to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_latest(
        self,
        *,
        execution_id: NotBlankStr | None = None,
        task_id: NotBlankStr | None = None,
    ) -> Checkpoint | None:
        """Retrieve the latest checkpoint by turn_number.

        At least one filter (``execution_id`` or ``task_id``) is required.

        Args:
            execution_id: Filter by execution identifier.
            task_id: Filter by task identifier.

        Returns:
            The checkpoint with the highest turn_number, or ``None``.

        Raises:
            PersistenceError: If the operation fails.
            ValueError: If neither filter is provided.
        """
        ...

    async def delete_by_execution(self, execution_id: NotBlankStr) -> int:
        """Delete all checkpoints for an execution.

        Args:
            execution_id: The execution identifier.

        Returns:
            Number of checkpoints deleted.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...


@runtime_checkable
class HeartbeatRepository(Protocol):
    """CRUD interface for heartbeat persistence."""

    async def save(self, heartbeat: Heartbeat) -> None:
        """Persist a heartbeat (upsert by execution_id).

        Args:
            heartbeat: The heartbeat to persist.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get(self, execution_id: NotBlankStr) -> Heartbeat | None:
        """Retrieve a heartbeat by execution ID.

        Args:
            execution_id: The execution identifier.

        Returns:
            The heartbeat, or ``None`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def get_stale(
        self,
        threshold: AwareDatetime,
    ) -> tuple[Heartbeat, ...]:
        """Retrieve heartbeats older than the threshold.

        Args:
            threshold: Heartbeats with ``last_heartbeat_at`` before
                this timestamp are considered stale.

        Returns:
            Stale heartbeats as a tuple.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...

    async def delete(self, execution_id: NotBlankStr) -> bool:
        """Delete a heartbeat by execution ID.

        Args:
            execution_id: The execution identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...
