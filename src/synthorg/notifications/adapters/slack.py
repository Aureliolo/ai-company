"""Slack notification sink -- webhook POST."""

from typing import TYPE_CHECKING

import httpx

from synthorg.observability import get_logger
from synthorg.observability.events.notification import (
    NOTIFICATION_SLACK_DELIVERED,
    NOTIFICATION_SLACK_FAILED,
)

if TYPE_CHECKING:
    from synthorg.notifications.models import Notification

logger = get_logger(__name__)


class SlackNotificationSink:
    """Notification sink that posts to a Slack incoming webhook.

    Args:
        webhook_url: Slack incoming webhook URL.
    """

    __slots__ = ("_client", "_webhook_url")

    def __init__(self, *, webhook_url: str) -> None:
        self._webhook_url = webhook_url
        self._client: httpx.AsyncClient | None = None

    @property
    def sink_name(self) -> str:
        """Return the sink identifier."""
        return "slack"

    async def send(self, notification: Notification) -> None:
        """Post the notification to Slack.

        Args:
            notification: The notification to deliver.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)

        payload = {
            "text": (f"*[{notification.severity.value.upper()}]* {notification.title}"),
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*[{notification.severity.value.upper()}]* "
                            f"{notification.title}\n"
                            f"{notification.body}"
                            if notification.body
                            else (
                                f"*[{notification.severity.value.upper()}]* "
                                f"{notification.title}"
                            )
                        ),
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": (
                                f"Category: {notification.category} | "
                                f"Source: {notification.source}"
                            ),
                        },
                    ],
                },
            ],
        }

        try:
            response = await self._client.post(
                self._webhook_url,
                json=payload,
            )
            response.raise_for_status()
            logger.info(
                NOTIFICATION_SLACK_DELIVERED,
                notification_id=notification.id,
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                NOTIFICATION_SLACK_FAILED,
                notification_id=notification.id,
                error=str(exc),
            )
            raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
