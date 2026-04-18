"""Health check controller."""

import asyncio
import time
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field

from synthorg import __version__
from synthorg.api.dto import ApiResponse
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_HEALTH_CHECK

logger = get_logger(__name__)


class ServiceStatus(StrEnum):
    """Health check status values."""

    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class TelemetryStatus(StrEnum):
    """Project telemetry runtime state.

    ``enabled`` means the collector is opted in AND the reporter can
    deliver events (``SYNTHORG_TELEMETRY=true`` plus the ``telemetry``
    extra installed and :func:`create_reporter` returning a live
    backend). ``disabled`` covers every other case: opt-out, noop
    reporter, missing ``logfire`` package, or reporter construction
    failure -- the factory degrades to :class:`NoopReporter` in the
    latter three, and the collector's ``is_functional`` property
    reflects that. The collector itself is still fire-and-forget:
    this field reflects the reporter's ability to deliver, not
    post-send delivery confirmation.
    """

    ENABLED = "enabled"
    DISABLED = "disabled"


class HealthStatus(BaseModel):
    """Health check response payload.

    Attributes:
        status: Overall health status.
        persistence: True if healthy, False if unhealthy, None if not configured.
        message_bus: True if running, False if stopped, None if not configured.
        telemetry: ``enabled`` when the collector is actively sending
            anonymous project telemetry, ``disabled`` otherwise.
        version: Application version.
        uptime_seconds: Seconds since application startup.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    status: ServiceStatus = Field(description="Overall health status")
    persistence: bool | None = Field(
        description="Persistence backend healthy (None if not configured)",
    )
    message_bus: bool | None = Field(
        description="Message bus running (None if not configured)",
    )
    telemetry: TelemetryStatus = Field(
        description="Project telemetry delivery state",
    )
    version: str = Field(description="Application version")
    uptime_seconds: float = Field(
        description="Seconds since startup",
    )


async def _probe_service(
    *,
    configured: bool,
    probe: Callable[[], Awaitable[bool]],
    component: str,
) -> bool | None:
    """Probe an async service, returning None if not configured."""
    if not configured:
        return None
    try:
        return await probe()
    except Exception:
        logger.warning(API_HEALTH_CHECK, component=component, exc_info=True)
        return False


def _resolve_telemetry_status(app_state: AppState) -> TelemetryStatus:
    """Read the telemetry collector and map to a public status.

    Returns ``disabled`` when no collector is attached (test harness),
    when the operator opted out, or when the reporter silently
    degraded to :class:`NoopReporter` (missing ``logfire`` extra,
    reporter construction failure, or explicit ``noop`` backend).
    Uses ``collector.is_functional`` instead of ``enabled`` so the
    health endpoint reflects delivery capability, not just the
    config opt-in flag.
    """
    if not app_state.has_telemetry_collector:
        return TelemetryStatus.DISABLED
    return (
        TelemetryStatus.ENABLED
        if app_state.telemetry_collector.is_functional
        else TelemetryStatus.DISABLED
    )


class HealthController(Controller):
    """Health check endpoint."""

    path = "/health"
    tags = ("health",)

    @get()
    async def health_check(
        self,
        state: State,
    ) -> ApiResponse[HealthStatus]:
        """Return current health status.

        Args:
            state: Application state.

        Returns:
            Health status envelope.
        """
        app_state: AppState = state.app_state

        # Probe persistence and the message bus in parallel: the two
        # checks are independent and each may wait on a round-trip
        # (e.g. NATS PING/PONG), so sequential awaits add their
        # latencies. TaskGroup gives structured concurrency with
        # proper cancellation propagation if one probe raises (the
        # ``_probe_service`` wrapper already swallows expected
        # failures into ``False``, so only truly unexpected errors
        # -- e.g. MemoryError -- propagate here).
        async with asyncio.TaskGroup() as tg:
            persistence_task = tg.create_task(
                _probe_service(
                    configured=app_state.has_persistence,
                    probe=lambda: app_state.persistence.health_check(),  # noqa: PLW0108
                    component="persistence",
                ),
            )
            bus_task = tg.create_task(
                _probe_service(
                    configured=app_state.has_message_bus,
                    probe=lambda: app_state.message_bus.health_check(),  # noqa: PLW0108
                    component="message_bus",
                ),
            )
        persistence_ok = persistence_task.result()
        bus_ok = bus_task.result()
        telemetry_status = _resolve_telemetry_status(app_state)

        checks = [v for v in (persistence_ok, bus_ok) if v is not None]
        if not checks or all(checks):
            status = ServiceStatus.OK
        elif any(checks):
            status = ServiceStatus.DEGRADED
        else:
            status = ServiceStatus.DOWN

        uptime = round(time.monotonic() - app_state.startup_time, 2)

        logger.debug(
            API_HEALTH_CHECK,
            status=status.value,
            persistence=persistence_ok,
            message_bus=bus_ok,
            telemetry=telemetry_status.value,
        )

        return ApiResponse(
            data=HealthStatus(
                status=status,
                persistence=persistence_ok,
                message_bus=bus_ok,
                telemetry=telemetry_status,
                version=__version__,
                uptime_seconds=uptime,
            ),
        )
