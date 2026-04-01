"""Shipping event constants for log aggregation and shipping.

These constants define the event taxonomy for log shipping operations.
They are intended for use by higher-level orchestration code and
monitoring consumers.  The handler internals (``http_handler.py``,
``syslog_handler.py``) use ``print(..., file=sys.stderr)`` for
bootstrap-safe error reporting as permitted by the logging exceptions
in CLAUDE.md.
"""

from typing import Final

# Syslog events
SHIPPING_SYSLOG_CONNECTED: Final[str] = "shipping.syslog.connected"
SHIPPING_SYSLOG_SEND_FAILED: Final[str] = "shipping.syslog.send_failed"
SHIPPING_SYSLOG_RECONNECTED: Final[str] = "shipping.syslog.reconnected"

# HTTP events
SHIPPING_HTTP_BATCH_SENT: Final[str] = "shipping.http.batch_sent"
SHIPPING_HTTP_BATCH_FAILED: Final[str] = "shipping.http.batch_failed"
SHIPPING_HTTP_RETRY: Final[str] = "shipping.http.retry"
SHIPPING_HTTP_DROPPED: Final[str] = "shipping.http.dropped"
SHIPPING_HTTP_FLUSHER_STARTED: Final[str] = "shipping.http.flusher_started"
SHIPPING_HTTP_FLUSHER_STOPPED: Final[str] = "shipping.http.flusher_stopped"

# Compression events
SHIPPING_COMPRESSION_COMPLETED: Final[str] = "shipping.compression.completed"
SHIPPING_COMPRESSION_FAILED: Final[str] = "shipping.compression.failed"
