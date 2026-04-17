"""ntfy notification sink -- HTTP POST to an ntfy server."""

import ipaddress
import math
import re
from urllib.parse import urlparse

import httpx

from synthorg.notifications.models import (
    Notification,
    NotificationSeverity,
)
from synthorg.observability import get_logger
from synthorg.observability.events.notification import (
    NOTIFICATION_NTFY_DELIVERED,
    NOTIFICATION_NTFY_FAILED,
)

logger = get_logger(__name__)

_SEVERITY_TO_PRIORITY: dict[NotificationSeverity, str] = {
    NotificationSeverity.INFO: "default",
    NotificationSeverity.WARNING: "high",
    NotificationSeverity.ERROR: "urgent",
    NotificationSeverity.CRITICAL: "max",
}

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _validate_outbound_url(url: str, field: str) -> None:
    """Reject URLs that target internal/loopback hosts or non-HTTP schemes."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        msg = f"{field} must use http or https scheme, got {parsed.scheme!r}"
        raise ValueError(msg)
    host = parsed.hostname or ""
    if host in _BLOCKED_HOSTS:
        msg = f"{field} must not target loopback address"
        raise ValueError(msg)
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        # Not a literal IP -- hostname like "ntfy.example.com".
        # Already checked against _BLOCKED_HOSTS above.
        return
    if addr.is_private or addr.is_link_local or addr.is_loopback:
        msg = f"{field} must not target private/internal IP"
        raise ValueError(msg)


class NtfyNotificationSink:
    """Notification sink that posts to an ntfy server.

    Uses ``httpx.AsyncClient`` for a single HTTP POST per
    notification. The client is eagerly created for connection
    pooling and properly cleaned up via ``close()``.

    Args:
        server_url: ntfy server base URL (e.g. ``"https://ntfy.sh"``).
        topic: ntfy topic name.
        token: Optional authentication token.
        webhook_timeout_seconds: HTTP timeout for ntfy POST calls, in
            seconds. Mirrors the
            ``notifications.ntfy_webhook_timeout_seconds`` setting;
            the notification factory threads the resolved value in at
            construction so operator tuning takes effect on restart.
            Must be positive.

    Raises:
        ValueError: If *server_url* targets a private/loopback host,
            or if *webhook_timeout_seconds* is not positive.
    """

    __slots__ = ("_client", "_server_url", "_token", "_topic")

    def __init__(
        self,
        *,
        server_url: str,
        topic: str,
        token: str | None = None,
        webhook_timeout_seconds: float = 10.0,
    ) -> None:
        _validate_outbound_url(server_url, "server_url")
        if not math.isfinite(webhook_timeout_seconds) or webhook_timeout_seconds <= 0:
            msg = (
                "webhook_timeout_seconds must be a finite number > 0, got "
                f"{webhook_timeout_seconds}"
            )
            raise ValueError(msg)
        self._server_url = server_url.rstrip("/")
        self._topic = topic
        self._token = token
        self._client = httpx.AsyncClient(
            timeout=webhook_timeout_seconds,
            follow_redirects=False,
        )

    @property
    def sink_name(self) -> str:
        """Return the sink identifier."""
        return "ntfy"

    async def send(self, notification: Notification) -> None:
        """Post the notification to the ntfy server.

        Args:
            notification: The notification to deliver.
        """
        safe_title = _CONTROL_CHAR_RE.sub("", notification.title)
        url = f"{self._server_url}/{self._topic}"
        headers: dict[str, str] = {
            "Title": safe_title,
            "Priority": _SEVERITY_TO_PRIORITY.get(
                notification.severity,
                "default",
            ),
            "Tags": notification.category,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            response = await self._client.post(
                url,
                content=notification.body or notification.title,
                headers=headers,
            )
            response.raise_for_status()
            logger.info(
                NOTIFICATION_NTFY_DELIVERED,
                notification_id=notification.id,
                status_code=response.status_code,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                NOTIFICATION_NTFY_FAILED,
                notification_id=notification.id,
                error=str(exc),
            )
            raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
