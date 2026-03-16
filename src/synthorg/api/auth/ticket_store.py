"""In-memory store for short-lived, single-use WebSocket tickets.

Tickets are ephemeral — they do not survive a server restart, which
forces re-authentication (correct security behaviour).  The store
uses ``time.monotonic()`` for expiry so it is immune to wall-clock
adjustments.
"""

import secrets
import time

from pydantic import BaseModel, ConfigDict

from synthorg.api.auth.models import AuthenticatedUser  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_WS_TICKET_CLEANUP,
    API_WS_TICKET_CONSUMED,
    API_WS_TICKET_EXPIRED,
    API_WS_TICKET_INVALID,
    API_WS_TICKET_ISSUED,
)

logger = get_logger(__name__)

_TOKEN_BYTES = 32


class _TicketEntry(BaseModel):
    """Internal record for a pending ticket.

    Attributes:
        user: Authenticated identity captured at ticket creation.
        expires_at: ``time.monotonic()`` deadline.
    """

    model_config = ConfigDict(frozen=True)

    user: AuthenticatedUser
    expires_at: float


class WsTicketStore:
    """In-memory store for one-time WebSocket auth tickets.

    Each ticket is a cryptographically random URL-safe token
    (43 characters).  Tickets expire after *ttl_seconds* or on
    first use, whichever comes first.

    Args:
        ttl_seconds: Ticket lifetime in seconds (default 30).
    """

    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._ttl = ttl_seconds
        self._tickets: dict[str, _TicketEntry] = {}

    @property
    def ttl_seconds(self) -> float:
        """Configured ticket lifetime."""
        return self._ttl

    def create(self, user: AuthenticatedUser) -> str:
        """Issue a new single-use ticket for *user*.

        Args:
            user: Authenticated identity to bind to the ticket.

        Returns:
            URL-safe random token string.
        """
        ticket = secrets.token_urlsafe(_TOKEN_BYTES)
        entry = _TicketEntry(
            user=user,
            expires_at=time.monotonic() + self._ttl,
        )
        self._tickets[ticket] = entry
        logger.info(
            API_WS_TICKET_ISSUED,
            user_id=user.user_id,
            username=user.username,
            ttl_seconds=self._ttl,
        )
        return ticket

    def validate_and_consume(self, ticket: str) -> AuthenticatedUser | None:
        """Validate and consume a ticket (single-use).

        Removes the ticket from the store on success.  Returns
        ``None`` if the ticket is unknown, expired, or already used.

        Args:
            ticket: Raw ticket string from the client.

        Returns:
            The bound ``AuthenticatedUser``, or ``None``.
        """
        self._cleanup_expired()

        entry = self._tickets.pop(ticket, None)
        if entry is None:
            logger.warning(API_WS_TICKET_INVALID, reason="not_found")
            return None

        now = time.monotonic()
        if now > entry.expires_at:
            logger.warning(
                API_WS_TICKET_EXPIRED,
                user_id=entry.user.user_id,
                overdue_seconds=round(now - entry.expires_at, 2),
            )
            return None

        logger.info(
            API_WS_TICKET_CONSUMED,
            user_id=entry.user.user_id,
            username=entry.user.username,
        )
        return entry.user

    def _cleanup_expired(self) -> int:
        """Remove expired tickets.

        Returns:
            Number of entries removed.
        """
        now = time.monotonic()
        expired = [k for k, v in self._tickets.items() if now > v.expires_at]
        for k in expired:
            del self._tickets[k]
        if expired:
            logger.debug(
                API_WS_TICKET_CLEANUP,
                removed=len(expired),
                remaining=len(self._tickets),
            )
        return len(expired)
