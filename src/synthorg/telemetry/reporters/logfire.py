"""Logfire telemetry reporter.

Sends curated, privacy-validated telemetry events to the
SynthOrg project on Logfire via the Logfire SDK (OpenTelemetry
compatible).

The ``logfire`` package is an optional dependency. This module
is only imported when ``TelemetryBackend.LOGFIRE`` is selected,
so the import is deferred to avoid loading logfire when telemetry
is disabled.

The Logfire write token is project-owned and compiled in: it is
the only source, and cannot be overridden at runtime. Telemetry
is a SynthOrg product signal, not a user-facing observability
channel. Operators who need their own metrics pipeline use the
Postgres + Prometheus + audit-chain stack.
"""

import asyncio
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.telemetry import (
    TELEMETRY_REPORT_FAILED,
    TELEMETRY_REPORTER_INITIALIZED,
)

if TYPE_CHECKING:
    from synthorg.telemetry.protocol import TelemetryEvent

logger = get_logger(__name__)

# Write-only token for the SynthOrg project on Logfire.
# This token can ONLY send data: it cannot read telemetry,
# access the account, or perform any other operation. Safe to
# embed in source (same pattern as Sentry DSNs, PostHog keys).
# Runtime override is intentionally not supported -- see module
# docstring for rationale.
_PROJECT_TOKEN = "pylf_v1_eu_BMgmPmm3hLxdSz2fRQkpL0l62rYzvRJBbScQddH2wB7n"  # noqa: S105


class LogfireReporter:
    """Logfire SDK-based telemetry reporter.

    Initializes ``logfire.configure()`` with the compiled-in
    project write token. Events are sent as Logfire log records
    with structured properties.
    """

    def __init__(self) -> None:
        try:
            import logfire as _logfire  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError as exc:
            msg = (
                "logfire package not installed. "
                'Install with: pip install "synthorg[telemetry]"'
            )
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                detail="logfire_import_failed",
                error_type="ImportError",
            )
            raise ImportError(msg) from exc

        self._logfire = _logfire

        try:
            self._logfire.configure(
                token=_PROJECT_TOKEN,
                send_to_logfire="if-token-present",
                service_name="synthorg-telemetry",
                service_version=_get_synthorg_version(),
            )
        except Exception as exc:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                detail="logfire_configure_failed",
                error_type=type(exc).__name__,
                exc_info=True,
            )
            raise

        logger.info(TELEMETRY_REPORTER_INITIALIZED, backend="logfire")

    async def report(self, event: TelemetryEvent) -> None:
        """Send a telemetry event to Logfire.

        Offloads the synchronous SDK call to a thread to avoid
        blocking the event loop. Lets backend exceptions propagate
        so :meth:`TelemetryCollector._send` returns ``False`` and
        skips the misleading ``*_SENT`` success event for an
        undelivered write. :meth:`TelemetryCollector._send` owns
        the ``TELEMETRY_REPORT_FAILED`` alert -- no log here
        avoids duplicating the same metric per failure.
        """
        await asyncio.to_thread(
            self._logfire.info,
            event.event_type,
            event_timestamp=event.timestamp,
            deployment_id=event.deployment_id,
            synthorg_version=event.synthorg_version,
            python_version=event.python_version,
            os_platform=event.os_platform,
            **event.properties,
        )

    async def flush(self) -> None:
        """Flush the Logfire exporter."""
        try:
            await asyncio.to_thread(self._logfire.force_flush)
        except Exception as exc:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                detail="flush",
                error_type=type(exc).__name__,
                exc_info=True,
            )

    async def shutdown(self) -> None:
        """Flush and shut down the Logfire exporter."""
        await self.flush()
        try:
            await asyncio.to_thread(self._logfire.shutdown)
        except Exception as exc:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                detail="shutdown",
                error_type=type(exc).__name__,
                exc_info=True,
            )


def _get_synthorg_version() -> str:
    try:
        import synthorg  # noqa: PLC0415
    except ImportError:
        return "unknown"

    try:
        return synthorg.__version__
    except AttributeError:
        logger.warning(
            TELEMETRY_REPORT_FAILED,
            detail="version_attribute_missing",
        )
        return "unknown"
