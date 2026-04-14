"""Communication event constants."""

from typing import Final

# Bus lifecycle
COMM_BUS_STARTED: Final[str] = "communication.bus.started"
COMM_BUS_STOPPED: Final[str] = "communication.bus.stopped"
COMM_BUS_ALREADY_RUNNING: Final[str] = "communication.bus.already_running"
COMM_BUS_NOT_RUNNING: Final[str] = "communication.bus.not_running"

# Bus connection lifecycle (distributed backends only)
COMM_BUS_CONNECTED: Final[str] = "communication.bus.connected"
COMM_BUS_RECONNECTING: Final[str] = "communication.bus.reconnecting"
COMM_BUS_DISCONNECTED: Final[str] = "communication.bus.disconnected"
COMM_BUS_RECEIVE_ERROR: Final[str] = "communication.bus.receive_error"
COMM_BUS_KV_READ_FAILED: Final[str] = "communication.bus.kv_read_failed"
COMM_BUS_KV_WRITE_FAILED: Final[str] = "communication.bus.kv_write_failed"
COMM_BUS_STREAM_SCAN_FAILED: Final[str] = "communication.bus.stream_scan_failed"
COMM_BUS_MESSAGE_DESERIALIZE_FAILED: Final[str] = (
    "communication.bus.message_deserialize_failed"
)
COMM_BUS_MESSAGE_TOO_LARGE: Final[str] = "communication.bus.message_too_large"

# Channel management
COMM_CHANNEL_CREATED: Final[str] = "communication.channel.created"
COMM_CHANNEL_NOT_FOUND: Final[str] = "communication.channel.not_found"
COMM_CHANNEL_ALREADY_EXISTS: Final[str] = "communication.channel.already_exists"

# Message routing
COMM_MESSAGE_PUBLISHED: Final[str] = "communication.message.published"
COMM_MESSAGE_DELIVERED: Final[str] = "communication.message.delivered"
COMM_DIRECT_SENT: Final[str] = "communication.message.direct_sent"
COMM_BATCH_PUBLISHED: Final[str] = "communication.message.batch_published"

# Subscriptions
COMM_SUBSCRIPTION_CREATED: Final[str] = "communication.subscription.created"
COMM_SUBSCRIPTION_REMOVED: Final[str] = "communication.subscription.removed"
COMM_SUBSCRIPTION_NOT_FOUND: Final[str] = "communication.subscription.not_found"

# History
COMM_HISTORY_QUERIED: Final[str] = "communication.history.queried"

# Messenger
COMM_MESSENGER_CREATED: Final[str] = "communication.messenger.created"
COMM_MESSENGER_SUBSCRIBED: Final[str] = "communication.messenger.subscribed"
COMM_MESSENGER_UNSUBSCRIBED: Final[str] = "communication.messenger.unsubscribed"
COMM_MESSAGE_SENT: Final[str] = "communication.message.sent"
COMM_MESSAGE_BROADCAST: Final[str] = "communication.message.broadcast"
COMM_HANDLER_DEREGISTER_MISS: Final[str] = "communication.handler.deregister_miss"
COMM_DISPATCH_NO_DISPATCHER: Final[str] = "communication.dispatch.no_dispatcher"

# Dispatcher
COMM_DISPATCH_START: Final[str] = "communication.dispatch.start"
COMM_DISPATCH_HANDLER_MATCHED: Final[str] = "communication.dispatch.handler_matched"
COMM_DISPATCH_HANDLER_ERROR: Final[str] = "communication.dispatch.handler_error"
COMM_DISPATCH_COMPLETE: Final[str] = "communication.dispatch.complete"
COMM_DISPATCH_NO_HANDLERS: Final[str] = "communication.dispatch.no_handlers"

# Handler registration
COMM_HANDLER_REGISTERED: Final[str] = "communication.handler.registered"
COMM_HANDLER_DEREGISTERED: Final[str] = "communication.handler.deregistered"
COMM_HANDLER_INVALID: Final[str] = "communication.handler.invalid"

# Receive
COMM_RECEIVE_SHUTDOWN: Final[str] = "communication.receive.shutdown"
COMM_RECEIVE_UNSUBSCRIBED: Final[str] = "communication.receive.unsubscribed"
COMM_CHANNELS_IDLE_SUMMARY: Final[str] = "communication.channels.idle_summary"

# Validation
COMM_MESSENGER_INVALID_AGENT: Final[str] = "communication.messenger.invalid_agent"
COMM_SEND_DIRECT_INVALID: Final[str] = "communication.message.send_direct_invalid"

# Shutdown
COMM_BUS_SHUTDOWN_SIGNAL: Final[str] = "communication.bus.shutdown_signal"

# Tool: email sending
COMM_TOOL_EMAIL_SEND_START: Final[str] = "communication.tool.email.send_start"
COMM_TOOL_EMAIL_SEND_SUCCESS: Final[str] = "communication.tool.email.send_success"
COMM_TOOL_EMAIL_SEND_FAILED: Final[str] = "communication.tool.email.send_failed"
COMM_TOOL_EMAIL_VALIDATION_FAILED: Final[str] = (
    "communication.tool.email.validation_failed"
)

# Tool: notification sending
COMM_TOOL_NOTIFICATION_SEND_START: Final[str] = (
    "communication.tool.notification.send_start"
)
COMM_TOOL_NOTIFICATION_SEND_SUCCESS: Final[str] = (
    "communication.tool.notification.send_success"
)
COMM_TOOL_NOTIFICATION_SEND_FAILED: Final[str] = (
    "communication.tool.notification.send_failed"
)

# Tool: template rendering
COMM_TOOL_TEMPLATE_RENDER_START: Final[str] = "communication.tool.template.render_start"
COMM_TOOL_TEMPLATE_RENDER_SUCCESS: Final[str] = (
    "communication.tool.template.render_success"
)
COMM_TOOL_TEMPLATE_RENDER_FAILED: Final[str] = (
    "communication.tool.template.render_failed"
)
COMM_TOOL_TEMPLATE_RENDER_INVALID: Final[str] = (
    "communication.tool.template.render_invalid"
)

# Dissent publication
COMM_DISSENT_PUBLISHED: Final[str] = "communication.dissent.published"
COMM_DISSENT_PUBLISH_FAILED: Final[str] = "communication.dissent.publish_failed"
COMM_DISSENT_EMITTED: Final[str] = "communication.dissent.emitted"
