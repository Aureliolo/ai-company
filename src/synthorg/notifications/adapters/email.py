"""Email notification sink -- SMTP via asyncio.to_thread."""

import asyncio
import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.notification import (
    NOTIFICATION_EMAIL_DELIVERED,
    NOTIFICATION_EMAIL_FAILED,
)

if TYPE_CHECKING:
    from synthorg.notifications.models import Notification

logger = get_logger(__name__)


class EmailNotificationSink:
    """Notification sink that sends email via SMTP.

    Uses stdlib ``smtplib`` wrapped in ``asyncio.to_thread`` to
    avoid blocking the event loop and avoid adding ``aiosmtplib``
    as a dependency.

    Args:
        host: SMTP server host.
        port: SMTP server port.
        username: SMTP authentication username (optional).
        password: SMTP authentication password (optional).
        from_addr: Sender email address.
        to_addrs: Recipient email addresses.
        use_tls: Whether to use STARTTLS.
    """

    __slots__ = (
        "_from_addr",
        "_host",
        "_password",
        "_port",
        "_to_addrs",
        "_use_tls",
        "_username",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        host: str,
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        from_addr: str,
        to_addrs: tuple[str, ...],
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_addr = from_addr
        self._to_addrs = to_addrs
        self._use_tls = use_tls

    @property
    def sink_name(self) -> str:
        """Return the sink identifier."""
        return "email"

    async def send(self, notification: Notification) -> None:
        """Send the notification via SMTP.

        Args:
            notification: The notification to deliver.
        """
        try:
            await asyncio.to_thread(self._send_sync, notification)
            logger.info(
                NOTIFICATION_EMAIL_DELIVERED,
                notification_id=notification.id,
                to_count=len(self._to_addrs),
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                NOTIFICATION_EMAIL_FAILED,
                notification_id=notification.id,
                error=str(exc),
            )
            raise

    def _send_sync(self, notification: Notification) -> None:
        """Synchronous SMTP send (runs in a thread)."""
        msg = EmailMessage()
        msg["Subject"] = (
            f"[SynthOrg {notification.severity.upper()}] {notification.title}"
        )
        msg["From"] = self._from_addr
        msg["To"] = ", ".join(self._to_addrs)
        msg.set_content(
            f"{notification.title}\n\n"
            f"{notification.body}\n\n"
            f"Category: {notification.category}\n"
            f"Source: {notification.source}\n"
            f"Timestamp: {notification.timestamp.isoformat()}"
        )

        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(msg)
