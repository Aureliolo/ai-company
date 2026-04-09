"""Reporter factory for telemetry backends."""

from typing import TYPE_CHECKING

from synthorg.telemetry.config import TelemetryBackend
from synthorg.telemetry.reporters.noop import NoopReporter

if TYPE_CHECKING:
    from synthorg.telemetry.config import TelemetryConfig
    from synthorg.telemetry.protocol import TelemetryReporter


def create_reporter(config: TelemetryConfig) -> TelemetryReporter:
    """Create a telemetry reporter from configuration.

    Returns a ``NoopReporter`` when telemetry is disabled or the
    backend is explicitly set to ``noop``.

    Args:
        config: Telemetry configuration.

    Returns:
        A concrete ``TelemetryReporter`` implementation.
    """
    if not config.enabled or config.backend == TelemetryBackend.NOOP:
        return NoopReporter()

    if config.backend == TelemetryBackend.LOGFIRE:
        from synthorg.telemetry.reporters.logfire import (  # noqa: PLC0415
            LogfireReporter,
        )

        return LogfireReporter(token=config.token)

    return NoopReporter()  # type: ignore[unreachable]  # fallback for future backends
