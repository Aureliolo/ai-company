"""MessageService -- read + publish facade over the message bus.

Wraps :class:`MessageBus` for channel / history reads and the publish
path; destructive removal raises
:class:`CapabilityNotSupportedError` because the underlying
:class:`MessageRepository` is append-only by design (durable channel
history is an audit log; operators redact via content rewrite rather
than deletion).  Handlers translate that to a typed ``not_supported``
envelope so callers understand the gap.
"""

from typing import TYPE_CHECKING

from synthorg.communication.mcp_errors import CapabilityNotSupportedError
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMMUNICATION_MESSAGE_SENT_VIA_MCP,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synthorg.communication.bus_protocol import MessageBus
    from synthorg.communication.channel import Channel
    from synthorg.communication.message import Message
    from synthorg.core.types import NotBlankStr
    from synthorg.persistence.protocol import PersistenceBackend

logger = get_logger(__name__)

_DELETE_CAP = "message_delete"
_DELETE_DETAIL = (
    "MessageRepository is append-only; operators rewrite content via "
    "a follow-up message rather than deleting history entries"
)


class MessageService:
    """Facade over the message bus for MCP.

    Args:
        bus: Message bus used for channel listings and publishing.
        persistence: Persistence backend whose ``messages`` repository
            owns the durable channel history.
    """

    def __init__(
        self,
        *,
        bus: MessageBus,
        persistence: PersistenceBackend,
    ) -> None:
        self._bus = bus
        self._persistence = persistence

    async def list_channels(self) -> Sequence[Channel]:
        """Return all channels the bus is aware of."""
        return tuple(await self._bus.list_channels())

    async def list_messages(
        self,
        *,
        channel: NotBlankStr | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[Sequence[Message], int]:
        """Return message history for a channel, paginated.

        Returns ``(items, total)`` where ``items`` is the requested page
        slice and ``total`` is the unfiltered count for the channel.
        The handler uses ``total`` to build the pagination envelope so
        callers can navigate.  Passing ``channel=None`` returns
        ``((), 0)`` -- an empty page -- without touching persistence.
        """
        if offset < 0:
            msg = f"offset must be >= 0, got {offset}"
            raise ValueError(msg)
        if limit is not None and limit < 1:
            msg = f"limit must be >= 1 when provided, got {limit}"
            raise ValueError(msg)
        if channel is None:
            return ((), 0)
        history = tuple(await self._persistence.messages.get_history(channel))
        total = len(history)
        end = total if limit is None else offset + limit
        return (history[offset:end], total)

    async def get_message(
        self,
        *,
        channel: NotBlankStr,
        message_id: str,
    ) -> Message | None:
        """Return one message by ``(channel, id)`` or ``None``."""
        history = await self._persistence.messages.get_history(channel)
        for msg in history:
            if str(msg.id) == message_id:
                return msg
        return None

    async def send_message(
        self,
        *,
        message: Message,
        actor_id: NotBlankStr,
    ) -> None:
        """Publish ``message`` onto the bus and audit the send.

        ``actor_id`` is the trusted, handler-supplied identity of the
        MCP caller; it drives the audit event so a malicious payload
        cannot spoof ``sender`` in the log.  The payload-side
        ``message.sender`` is still logged as ``sender`` for
        observability but is never treated as the authenticated actor.
        """
        await self._bus.publish(message)
        logger.info(
            COMMUNICATION_MESSAGE_SENT_VIA_MCP,
            channel=message.channel,
            actor_id=actor_id,
            sender=message.sender,
        )

    async def delete_message(
        self,
        *,
        channel: NotBlankStr,  # noqa: ARG002 - part of public contract
        message_id: str,  # noqa: ARG002
        actor_id: NotBlankStr,  # noqa: ARG002
        reason: NotBlankStr,  # noqa: ARG002
    ) -> bool:
        """Reject deletion with a typed ``not_supported`` error.

        The audit-grade durability of channel history means content
        removal is a separate operator workflow (log rotation /
        compliance tooling) rather than an MCP surface.
        """
        raise CapabilityNotSupportedError(_DELETE_CAP, _DELETE_DETAIL)


__all__ = [
    "MessageService",
]
