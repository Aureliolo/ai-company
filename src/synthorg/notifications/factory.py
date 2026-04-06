"""Notification sink factory.

Builds ``NotificationDispatcher`` instances from
``NotificationConfig`` by instantiating the appropriate adapter
for each configured sink.
"""

from typing import TYPE_CHECKING

from synthorg.notifications.adapters.console import ConsoleNotificationSink
from synthorg.notifications.config import (
    NotificationConfig,
    NotificationSinkConfig,
    NotificationSinkType,
)
from synthorg.notifications.dispatcher import NotificationDispatcher
from synthorg.observability import get_logger
from synthorg.observability.events.notification import (
    NOTIFICATION_SINK_CONFIG_INVALID,
    NOTIFICATION_SINK_DISABLED,
    NOTIFICATION_SINK_UNKNOWN_TYPE,
)

if TYPE_CHECKING:
    from synthorg.notifications.protocol import NotificationSink

logger = get_logger(__name__)


def build_notification_dispatcher(
    config: NotificationConfig,
) -> NotificationDispatcher:
    """Build a ``NotificationDispatcher`` from configuration.

    Always includes a console sink as a fallback if no sinks are
    configured or all configured sinks are disabled.

    Args:
        config: Notification subsystem configuration.

    Returns:
        Configured notification dispatcher.
    """
    sinks: list[NotificationSink] = []
    for sink_cfg in config.sinks:
        if not sink_cfg.enabled:
            logger.debug(
                NOTIFICATION_SINK_DISABLED,
                sink_type=sink_cfg.type,
            )
            continue
        sink = _create_notification_sink(sink_cfg)
        if sink is not None:
            sinks.append(sink)
    if not sinks:
        sinks.append(ConsoleNotificationSink())
    return NotificationDispatcher(
        sinks=tuple(sinks),
        min_severity=config.min_severity,
    )


def _create_notification_sink(
    cfg: NotificationSinkConfig,
) -> NotificationSink | None:
    """Instantiate a notification sink from config.

    Args:
        cfg: Single sink configuration.

    Returns:
        Sink instance or ``None`` for unknown or invalid types.
    """
    sink_type = cfg.type
    params = cfg.params
    if sink_type is NotificationSinkType.CONSOLE:
        return ConsoleNotificationSink()
    if sink_type is NotificationSinkType.NTFY:
        return _create_ntfy_sink(params)
    if sink_type is NotificationSinkType.SLACK:
        return _create_slack_sink(params)
    if sink_type is NotificationSinkType.EMAIL:
        return _create_email_sink(params)
    # Defensive fallback for forward compatibility if new sink
    # types are added to NotificationSinkType before the factory
    # is updated.
    logger.warning(  # type: ignore[unreachable]
        NOTIFICATION_SINK_UNKNOWN_TYPE,
        sink_type=sink_type,
    )
    return None


def _create_ntfy_sink(
    params: dict[str, str],
) -> NotificationSink | None:
    """Create an ntfy notification sink.

    Requires ``topic`` in params. The ``server_url`` defaults to
    ``https://ntfy.sh`` when not provided. Returns ``None`` with
    a warning if ``topic`` is missing -- public ntfy.sh topics
    should never be used by default.

    Args:
        params: Adapter-specific parameters.

    Returns:
        Configured ntfy sink or ``None`` if topic is missing.
    """
    from synthorg.notifications.adapters.ntfy import (  # noqa: PLC0415
        NtfyNotificationSink,
    )

    topic = params.get("topic", "")
    if not topic:
        logger.warning(
            NOTIFICATION_SINK_CONFIG_INVALID,
            sink_type="ntfy",
            error="topic is required",
        )
        return None
    return NtfyNotificationSink(
        server_url=params.get("server_url", "https://ntfy.sh"),
        topic=topic,
        token=params.get("token"),
    )


def _create_slack_sink(
    params: dict[str, str],
) -> NotificationSink | None:
    """Create a Slack webhook notification sink.

    Args:
        params: Adapter-specific parameters.

    Returns:
        Configured Slack sink or ``None`` if webhook URL is missing.
    """
    from synthorg.notifications.adapters.slack import (  # noqa: PLC0415
        SlackNotificationSink,
    )

    webhook_url = params.get("webhook_url", "")
    if not webhook_url:
        logger.warning(
            NOTIFICATION_SINK_CONFIG_INVALID,
            sink_type="slack",
            error="webhook_url is required",
        )
        return None
    return SlackNotificationSink(webhook_url=webhook_url)


def _create_email_sink(
    params: dict[str, str],
) -> NotificationSink | None:
    """Create an email SMTP notification sink.

    Args:
        params: Adapter-specific parameters.

    Returns:
        Configured email sink or ``None`` if required params
        are missing.
    """
    from synthorg.notifications.adapters.email import (  # noqa: PLC0415
        EmailNotificationSink,
    )

    host = params.get("host", "")
    if not host:
        logger.warning(
            NOTIFICATION_SINK_CONFIG_INVALID,
            sink_type="email",
            error="host is required",
        )
        return None
    to_addrs = tuple(
        a.strip() for a in params.get("to_addrs", "").split(",") if a.strip()
    )
    if not to_addrs:
        logger.warning(
            NOTIFICATION_SINK_CONFIG_INVALID,
            sink_type="email",
            error="to_addrs is required",
        )
        return None
    try:
        port = int(params.get("port", "587"))
    except ValueError:
        logger.warning(
            NOTIFICATION_SINK_CONFIG_INVALID,
            sink_type="email",
            error=f"invalid port: {params.get('port')!r}",
        )
        return None
    return EmailNotificationSink(
        host=host,
        port=port,
        username=params.get("username"),
        password=params.get("password"),
        from_addr=params.get("from_addr", "synthorg@localhost"),
        to_addrs=to_addrs,
        use_tls=params.get("use_tls", "true").lower() == "true",
    )
