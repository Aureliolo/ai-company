"""Message repository protocol."""

from typing import Protocol, runtime_checkable

from synthorg.communication.message import Message  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001


@runtime_checkable
class MessageRepository(Protocol):
    """Write + history query interface for Message persistence."""

    async def save(self, message: Message) -> None:
        """Persist a message.

        Args:
            message: The message to persist.

        Raises:
            DuplicateRecordError: If a message with the same ID exists.
            PersistenceError: If the operation fails.
        """
        ...

    async def get_history(
        self,
        channel: NotBlankStr,
        *,
        limit: int | None = None,
    ) -> tuple[Message, ...]:
        """Retrieve message history for a channel.

        Args:
            channel: Channel name to query.
            limit: Maximum number of messages to return (newest first).

        Returns:
            Messages ordered by timestamp descending.

        Raises:
            PersistenceError: If the operation fails.
        """
        ...
