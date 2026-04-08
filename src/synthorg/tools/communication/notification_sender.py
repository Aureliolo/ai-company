"""Notification sender tool -- dispatch notifications via the existing subsystem.

Delegates to the ``NotificationDispatcher`` from
``synthorg.notifications``, which fans out to all configured
sinks (console, email, Slack, ntfy, etc.).
"""

import copy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from synthorg.core.enums import ActionType
from synthorg.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMM_TOOL_NOTIFICATION_SEND_FAILED,
    COMM_TOOL_NOTIFICATION_SEND_START,
    COMM_TOOL_NOTIFICATION_SEND_SUCCESS,
)
from synthorg.tools.base import ToolExecutionResult
from synthorg.tools.communication.base_communication_tool import (
    BaseCommunicationTool,
)
from synthorg.tools.communication.config import (
    CommunicationToolsConfig,  # noqa: TC001
)

if TYPE_CHECKING:
    from synthorg.notifications.dispatcher import NotificationDispatcher

logger = get_logger(__name__)

_VALID_CATEGORIES: Final[frozenset[str]] = frozenset(
    m.value for m in NotificationCategory
)
_VALID_SEVERITIES: Final[frozenset[str]] = frozenset(
    m.value for m in NotificationSeverity
)

_PARAMETERS_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": sorted(_VALID_CATEGORIES),
            "description": "Notification category",
        },
        "severity": {
            "type": "string",
            "enum": sorted(_VALID_SEVERITIES),
            "description": "Notification severity level",
        },
        "title": {
            "type": "string",
            "description": "Notification title",
        },
        "body": {
            "type": "string",
            "description": "Detailed notification body",
            "default": "",
        },
        "source": {
            "type": "string",
            "description": "Source subsystem or agent name",
        },
    },
    "required": ["category", "severity", "title", "source"],
    "additionalProperties": False,
}


class NotificationSenderTool(BaseCommunicationTool):
    """Send notifications via the existing notification subsystem.

    Delegates to the ``NotificationDispatcher`` which fans out
    to all registered sinks (console, ntfy, Slack, email).

    Examples:
        Send a notification::

            tool = NotificationSenderTool(dispatcher=my_dispatcher)
            result = await tool.execute(
                arguments={
                    "category": "system",
                    "severity": "info",
                    "title": "Deployment complete",
                    "source": "deploy-agent",
                }
            )
    """

    def __init__(
        self,
        *,
        dispatcher: NotificationDispatcher | None = None,
        config: CommunicationToolsConfig | None = None,
    ) -> None:
        """Initialize the notification sender tool.

        Args:
            dispatcher: Notification dispatcher instance.
                ``None`` means the tool will return an error.
            config: Communication tool configuration.
        """
        super().__init__(
            name="notification_sender",
            description=(
                "Send notifications to registered sinks (console, email, Slack, ntfy)."
            ),
            parameters_schema=copy.deepcopy(_PARAMETERS_SCHEMA),
            action_type=ActionType.COMMS_INTERNAL,
            config=config,
        )
        self._dispatcher = dispatcher

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Send a notification.

        Args:
            arguments: Must contain ``category``, ``severity``,
                ``title``, and ``source``; optionally ``body``.

        Returns:
            A ``ToolExecutionResult`` with dispatch status.
        """
        if self._dispatcher is None:
            return ToolExecutionResult(
                content=(
                    "Notification sending requires a configured "
                    "NotificationDispatcher. None was provided."
                ),
                is_error=True,
            )

        category_str: str = arguments["category"]
        severity_str: str = arguments["severity"]
        title: str = arguments["title"]
        body: str = arguments.get("body", "")
        source: str = arguments["source"]

        if category_str not in _VALID_CATEGORIES:
            return ToolExecutionResult(
                content=(
                    f"Invalid category: {category_str!r}. "
                    f"Must be one of: {sorted(_VALID_CATEGORIES)}"
                ),
                is_error=True,
            )

        if severity_str not in _VALID_SEVERITIES:
            return ToolExecutionResult(
                content=(
                    f"Invalid severity: {severity_str!r}. "
                    f"Must be one of: {sorted(_VALID_SEVERITIES)}"
                ),
                is_error=True,
            )

        notification = Notification(
            category=NotificationCategory(category_str),
            severity=NotificationSeverity(severity_str),
            title=title,
            body=body,
            source=source,
            timestamp=datetime.now(UTC),
        )

        logger.info(
            COMM_TOOL_NOTIFICATION_SEND_START,
            notification_id=notification.id,
            category=category_str,
            severity=severity_str,
        )

        try:
            await self._dispatcher.dispatch(notification)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                COMM_TOOL_NOTIFICATION_SEND_FAILED,
                notification_id=notification.id,
                error=str(exc),
            )
            return ToolExecutionResult(
                content=f"Notification dispatch failed: {exc}",
                is_error=True,
            )

        logger.info(
            COMM_TOOL_NOTIFICATION_SEND_SUCCESS,
            notification_id=notification.id,
        )

        return ToolExecutionResult(
            content=(f"Notification dispatched: [{severity_str}] {title}"),
            metadata={
                "notification_id": notification.id,
                "category": category_str,
                "severity": severity_str,
            },
        )
