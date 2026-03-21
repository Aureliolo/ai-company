"""In-memory store for short-lived, single-use WebSocket tickets.

Tickets are ephemeral -- they do not survive a server restart, which
forces re-authentication (correct security behaviour).  The store
uses ``time.monotonic()`` for expiry so it is immune to wall-clock
adjustments.

.. note::

   The store is per-process -- if the ASGI server runs multiple
   worker processes, a ticket issued by one worker cannot be
   consumed by another.  ``ServerConfig.workers`` must be ``1``
   (the default) for ticket auth to work correctly.
"""

import math
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


class TicketLimitExceededError(Exception):
    """Raised when a user exceeds the per-user pending ticket cap."""


# 32 bytes → 256 bits of entropy, encoded as 43 URL-safe base64 chars.
_TOKEN_BYTES: int = 32
_MAX_PENDING_PER_USER: int = 5


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
    (43 characters, 256-bit entropy).  Tickets expire after
    *ttl_seconds* or on first use, whichever comes first.

    Args:
        ttl_seconds: Ticket lifetime in seconds (default 30).

    Raises:
        ValueError: If *ttl_seconds* is not positive.
    """

    def __init__(self, ttl_seconds: float = 30.0) -> None:
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            msg = f"ttl_seconds must be a finite positive number, got {ttl_seconds}"
            raise ValueError(msg)
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
        now = time.monotonic()
        user_pending = sum(
            1
            for e in self._tickets.values()
            if e.user.user_id == user.user_id and now <= e.expires_at
        )
        if user_pending >= _MAX_PENDING_PER_USER:
            msg = f"Ticket limit exceeded for user {user.user_id}"
            raise TicketLimitExceededError(msg)

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

        Atomically removes the ticket via ``dict.pop`` before
        checking expiry.  In the single-threaded asyncio event loop,
        ``dict.pop`` cannot be interleaved with another coroutine,
        so concurrent calls on the same ticket are safely serialised.

        Args:
            ticket: Raw ticket string from the client.

        Returns:
            The bound ``AuthenticatedUser``, or ``None``.
        """
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

    def cleanup_expired(self) -> int:
        """Remove expired tickets.

        Called periodically by a background task to prevent
        unbounded memory growth from tickets that are requested
        but never consumed.

        Returns:
            Number of entries removed.
        """
        now = time.monotonic()
        expired = [k for k, v in self._tickets.items() if now > v.expires_at]
        for k in expired:
            self._tickets.pop(k, None)
        if expired:
            logger.info(
                API_WS_TICKET_CLEANUP,
                removed=len(expired),
                remaining=len(self._tickets),
            )
        return len(expired)
