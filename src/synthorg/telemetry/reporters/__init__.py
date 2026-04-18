"""Reporter factory for telemetry backends."""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.telemetry import TELEMETRY_REPORT_FAILED
from synthorg.telemetry.config import TelemetryBackend
from synthorg.telemetry.reporters.noop import NoopReporter

if TYPE_CHECKING:
    from synthorg.telemetry.config import TelemetryConfig
    from synthorg.telemetry.protocol import TelemetryReporter

logger = get_logger(__name__)


def create_reporter(config: TelemetryConfig) -> TelemetryReporter:
    """Create a telemetry reporter from configuration.

    Returns a ``NoopReporter`` when telemetry is disabled or the
    backend is explicitly set to ``noop``.  Falls back to
    ``NoopReporter`` if the Logfire package is not installed.

    Args:
        config: Telemetry configuration.

    Returns:
        A concrete ``TelemetryReporter`` implementation.

    Raises:
        ValueError: If the backend is not recognised.
    """
    if not config.enabled or config.backend == TelemetryBackend.NOOP:
        return NoopReporter()

    if config.backend == TelemetryBackend.LOGFIRE:
        try:
            from synthorg.telemetry.reporters.logfire import (  # noqa: PLC0415
                LogfireReporter,
            )

            return LogfireReporter(environment=config.environment)
        except Exception as exc:
            logger.warning(
                TELEMETRY_REPORT_FAILED,
                detail="logfire_init_failed",
                error_type=type(exc).__name__,
            )
            return NoopReporter()

    msg = f"Unknown telemetry backend: {config.backend!r}"  # type: ignore[unreachable]
    raise ValueError(msg)
