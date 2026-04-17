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
    from synthorg.settings.bridge_configs import NotificationsBridgeConfig

logger = get_logger(__name__)


def build_notification_dispatcher(
    config: NotificationConfig,
    *,
    bridge_config: NotificationsBridgeConfig | None = None,
) -> NotificationDispatcher:
    """Build a ``NotificationDispatcher`` from configuration.

    Always includes a console sink as a fallback if no sinks are
    configured or all configured sinks are disabled.

    Args:
        config: Notification subsystem configuration.
        bridge_config: Optional operator-tuned bridge settings
            (webhook/SMTP timeouts). When ``None``, adapter defaults
            are used. The API startup hook resolves this from
            ``ConfigResolver.get_notifications_bridge_config()`` and
            rebuilds the dispatcher so operator tuning takes effect
            on restart.

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
        sink = _create_notification_sink(sink_cfg, bridge_config=bridge_config)
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
    *,
    bridge_config: NotificationsBridgeConfig | None = None,
) -> NotificationSink | None:
    """Instantiate a notification sink from config.

    Args:
        cfg: Single sink configuration.
        bridge_config: Optional operator-tuned bridge settings.

    Returns:
        Sink instance or ``None`` for unknown or invalid types.
    """
    sink_type = cfg.type
    params = cfg.params
    if sink_type is NotificationSinkType.CONSOLE:
        return ConsoleNotificationSink()
    if sink_type is NotificationSinkType.NTFY:
        return _create_ntfy_sink(params, bridge_config=bridge_config)
    if sink_type is NotificationSinkType.SLACK:
        return _create_slack_sink(params, bridge_config=bridge_config)
    if sink_type is NotificationSinkType.EMAIL:
        return _create_email_sink(params, bridge_config=bridge_config)
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
    *,
    bridge_config: NotificationsBridgeConfig | None = None,
) -> NotificationSink | None:
    """Create an ntfy notification sink.

    Requires ``topic`` in params. The ``server_url`` defaults to
    ``https://ntfy.sh`` when not provided. Returns ``None`` with
    a warning if ``topic`` is missing -- public ntfy.sh topics
    should never be used by default.

    Args:
        params: Adapter-specific parameters.
        bridge_config: Optional operator-tuned notification bridge
            config. When provided, threads
            ``ntfy_webhook_timeout_seconds`` into the adapter.

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
    server_url = params.get("server_url", "https://ntfy.sh")
    token = params.get("token")
    if bridge_config is None:
        return NtfyNotificationSink(
            server_url=server_url,
            topic=topic,
            token=token,
        )
    return NtfyNotificationSink(
        server_url=server_url,
        topic=topic,
        token=token,
        webhook_timeout_seconds=bridge_config.ntfy_webhook_timeout_seconds,
    )


def _create_slack_sink(
    params: dict[str, str],
    *,
    bridge_config: NotificationsBridgeConfig | None = None,
) -> NotificationSink | None:
    """Create a Slack webhook notification sink.

    Args:
        params: Adapter-specific parameters.
        bridge_config: Optional operator-tuned notification bridge
            config. When provided, threads
            ``slack_webhook_timeout_seconds`` into the adapter.

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
    if bridge_config is None:
        return SlackNotificationSink(webhook_url=webhook_url)
    return SlackNotificationSink(
        webhook_url=webhook_url,
        webhook_timeout_seconds=bridge_config.slack_webhook_timeout_seconds,
    )


def _create_email_sink(
    params: dict[str, str],
    *,
    bridge_config: NotificationsBridgeConfig | None = None,
) -> NotificationSink | None:
    """Create an email SMTP notification sink.

    Args:
        params: Adapter-specific parameters.
        bridge_config: Optional operator-tuned notification bridge
            config. When provided, threads
            ``email_smtp_timeout_seconds`` into the adapter.

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
    username = params.get("username")
    password = params.get("password")
    from_addr = params.get("from_addr", "synthorg@localhost")
    use_tls = params.get("use_tls", "true").lower() == "true"
    if bridge_config is None:
        return EmailNotificationSink(
            host=host,
            port=port,
            username=username,
            password=password,
            from_addr=from_addr,
            to_addrs=to_addrs,
            use_tls=use_tls,
        )
    return EmailNotificationSink(
        host=host,
        port=port,
        username=username,
        password=password,
        from_addr=from_addr,
        to_addrs=to_addrs,
        use_tls=use_tls,
        smtp_timeout_seconds=bridge_config.email_smtp_timeout_seconds,
    )
