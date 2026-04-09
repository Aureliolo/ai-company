"""Logfire telemetry reporter.

Sends curated, privacy-validated telemetry events to a Logfire
project via the Logfire SDK (OpenTelemetry-compatible).

The ``logfire`` package is an optional dependency.  This module
is only imported when ``TelemetryBackend.LOGFIRE`` is selected,
so the import is deferred to avoid loading logfire when telemetry
is disabled.
"""

import os
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.telemetry import (
    TELEMETRY_REPORT_FAILED,
    TELEMETRY_REPORTER_INITIALIZED,
)

if TYPE_CHECKING:
    from synthorg.telemetry.protocol import TelemetryEvent

logger = get_logger(__name__)

_TOKEN_ENV = "SYNTHORG_TELEMETRY_TOKEN"  # noqa: S105


class LogfireReporter:
    """Logfire SDK-based telemetry reporter.

    Initializes ``logfire.configure()`` with the project write token.
    Events are sent as Logfire log records with structured properties.

    Args:
        token: Logfire write token.  When ``None``, reads from
            ``SYNTHORG_TELEMETRY_TOKEN`` env var.
    """

    def __init__(self, token: str | None = None) -> None:
        try:
            import logfire as _logfire  # noqa: PLC0415
        except ImportError as exc:
            msg = "logfire package not installed. Install with: uv add logfire"
            raise ImportError(msg) from exc

        self._logfire = _logfire

        resolved_token = token or os.environ.get(_TOKEN_ENV)

        self._logfire.configure(
            token=resolved_token,
            send_to_logfire="if-token-present",
            service_name="synthorg-telemetry",
            service_version=_get_synthorg_version(),
        )

        logger.info(
            TELEMETRY_REPORTER_INITIALIZED,
            backend="logfire",
            has_token=resolved_token is not None,
        )

    async def report(self, event: TelemetryEvent) -> None:
        """Send a telemetry event to Logfire."""
        try:
            self._logfire.info(
                event.event_type,
                deployment_id=event.deployment_id,
                synthorg_version=event.synthorg_version,
                python_version=event.python_version,
                os_platform=event.os_platform,
                **event.properties,
            )
        except Exception:
            logger.debug(
                TELEMETRY_REPORT_FAILED,
                event_type=event.event_type,
            )

    async def flush(self) -> None:
        """Flush the Logfire exporter."""
        try:
            self._logfire.force_flush()
        except Exception:
            logger.debug(TELEMETRY_REPORT_FAILED, detail="flush")

    async def shutdown(self) -> None:
        """Flush and shut down the Logfire exporter."""
        await self.flush()
        try:
            self._logfire.shutdown()
        except Exception:
            logger.debug(TELEMETRY_REPORT_FAILED, detail="shutdown")


def _get_synthorg_version() -> str:
    try:
        import synthorg  # noqa: PLC0415
    except ImportError, AttributeError:
        return "unknown"
    else:
        return synthorg.__version__
