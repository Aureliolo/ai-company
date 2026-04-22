"""Liveness and readiness probe controllers.

* ``/healthz`` (liveness) -- always 200 while the event loop is
  turning; no dependency probes. Kubernetes-style supervisors use
  this to decide whether to restart the process.
* ``/readyz`` (readiness) -- 200 only when persistence + message
  bus are both healthy; otherwise 503. Used to gate traffic / block
  rollouts until dependencies are up.
"""

import asyncio
import time
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from litestar import Controller, Response, get
from litestar.datastructures import State  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field

from synthorg import __version__
from synthorg.api.dto import ApiResponse
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_HEALTH_CHECK

logger = get_logger(__name__)


class ReadinessOutcome(StrEnum):
    """Binary readiness outcome.

    Readiness is a pass/fail gate for supervisors; we deliberately
    drop the tri-state ``degraded`` value that the old ``/health``
    endpoint used -- a supervisor has no sensible action for it.
    """

    OK = "ok"
    UNAVAILABLE = "unavailable"


class TelemetryStatus(StrEnum):
    """Project telemetry runtime state.

    ``enabled`` means the collector is opted in AND the reporter can
    deliver events. ``disabled`` covers every other case.
    """

    ENABLED = "enabled"
    DISABLED = "disabled"


class LivenessStatus(BaseModel):
    """Liveness response payload.

    Attributes:
        status: Always ``"ok"``.
        version: Application version.
        uptime_seconds: Seconds since startup.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    status: str = Field(description="Always 'ok' while the process is alive")
    version: str = Field(description="Application version")
    uptime_seconds: float = Field(description="Seconds since startup")


class ReadinessStatus(BaseModel):
    """Readiness response payload.

    Attributes:
        status: Overall readiness outcome.
        persistence: Persistence backend healthy (``None`` if not
            configured).
        message_bus: Message bus running (``None`` if not configured).
        telemetry: Project telemetry delivery state.
        version: Application version.
        uptime_seconds: Seconds since startup.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    status: ReadinessOutcome = Field(description="Overall readiness outcome")
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
    uptime_seconds: float = Field(description="Seconds since startup")


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
    """Read the telemetry collector and map to a public status."""
    if not app_state.has_telemetry_collector:
        return TelemetryStatus.DISABLED
    return (
        TelemetryStatus.ENABLED
        if app_state.telemetry_collector.is_functional
        else TelemetryStatus.DISABLED
    )


class LivenessController(Controller):
    """Liveness probe endpoint.

    Kubernetes-style supervisors hit ``/healthz`` to decide whether
    to restart the process. No dependency probes -- only that the
    event loop is responsive.
    """

    path = "/healthz"
    tags = ("health",)

    @get()
    async def liveness(
        self,
        state: State,
    ) -> ApiResponse[LivenessStatus]:
        """Return a constant ``ok`` response while the process is alive."""
        app_state: AppState = state.app_state
        uptime = round(time.monotonic() - app_state.startup_time, 2)
        return ApiResponse(
            data=LivenessStatus(
                status="ok",
                version=__version__,
                uptime_seconds=uptime,
            ),
        )


class ReadinessController(Controller):
    """Readiness probe endpoint.

    Probes persistence + message bus in parallel. Returns 200 when
    both are healthy (or unconfigured); 503 otherwise so supervisors
    and load-balancers can hold traffic off an unready instance.
    """

    path = "/readyz"
    tags = ("health",)

    @get()
    async def readiness(
        self,
        state: State,
    ) -> Response[ApiResponse[ReadinessStatus]]:
        """Return readiness status + 200/503 based on dependency health."""
        app_state: AppState = state.app_state

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

        # Readiness is a pass/fail: every *configured* dependency must
        # report healthy. Unconfigured (None) is treated as not
        # blocking -- dev stacks without a bus still report ready.
        configured_checks = [v for v in (persistence_ok, bus_ok) if v is not None]
        ready = bool(configured_checks) and all(configured_checks)
        outcome = (
            ReadinessOutcome.OK
            if ready or not configured_checks
            else ReadinessOutcome.UNAVAILABLE
        )
        status_code = 200 if outcome is ReadinessOutcome.OK else 503

        uptime = round(time.monotonic() - app_state.startup_time, 2)

        logger.debug(
            API_HEALTH_CHECK,
            status=outcome.value,
            persistence=persistence_ok,
            message_bus=bus_ok,
            telemetry=telemetry_status.value,
        )

        return Response(
            content=ApiResponse(
                data=ReadinessStatus(
                    status=outcome,
                    persistence=persistence_ok,
                    message_bus=bus_ok,
                    telemetry=telemetry_status,
                    version=__version__,
                    uptime_seconds=uptime,
                ),
            ),
            status_code=status_code,
        )
