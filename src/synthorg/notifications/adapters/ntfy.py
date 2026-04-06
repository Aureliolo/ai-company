"""ntfy notification sink -- HTTP POST to an ntfy server."""

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


class NtfyNotificationSink:
    """Notification sink that posts to an ntfy server.

    Uses ``httpx.AsyncClient`` for a single HTTP POST per
    notification. The client is lazily created and reused for
    connection pooling.

    Args:
        server_url: ntfy server base URL (e.g. ``"https://ntfy.sh"``).
        topic: ntfy topic name.
        token: Optional authentication token.
    """

    __slots__ = ("_client", "_server_url", "_token", "_topic")

    def __init__(
        self,
        *,
        server_url: str,
        topic: str,
        token: str | None = None,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._topic = topic
        self._token = token
        self._client: httpx.AsyncClient | None = None

    @property
    def sink_name(self) -> str:
        """Return the sink identifier."""
        return "ntfy"

    async def send(self, notification: Notification) -> None:
        """Post the notification to the ntfy server.

        Args:
            notification: The notification to deliver.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)

        url = f"{self._server_url}/{self._topic}"
        headers: dict[str, str] = {
            "Title": notification.title,
            "Priority": _SEVERITY_TO_PRIORITY.get(notification.severity, "default"),
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
        except Exception as exc:
            logger.warning(
                NOTIFICATION_NTFY_FAILED,
                notification_id=notification.id,
                error=str(exc),
            )
