"""Health check controller."""

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


class HealthStatus(BaseModel):
    """Health check response payload.

    Attributes:
        status: Overall health status.
        persistence: True if healthy, False if unhealthy, None if not configured.
        message_bus: True if running, False if stopped, None if not configured.
        version: Application version.
        uptime_seconds: Seconds since application startup.
    """

    model_config = ConfigDict(frozen=True)

    status: ServiceStatus = Field(description="Overall health status")
    persistence: bool | None = Field(
        description="Persistence backend healthy (None if not configured)",
    )
    message_bus: bool | None = Field(
        description="Message bus running (None if not configured)",
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


def _probe_sync_service(
    *,
    configured: bool,
    probe: Callable[[], bool],
    component: str,
) -> bool | None:
    """Probe a synchronous service, returning None if not configured."""
    if not configured:
        return None
    try:
        return probe()
    except Exception:
        logger.warning(API_HEALTH_CHECK, component=component, exc_info=True)
        return False


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

        persistence_ok = await _probe_service(
            configured=app_state.has_persistence,
            probe=lambda: app_state.persistence.health_check(),  # noqa: PLW0108
            component="persistence",
        )
        bus_ok = _probe_sync_service(
            configured=app_state.has_message_bus,
            probe=lambda: app_state.message_bus.is_running,
            component="message_bus",
        )

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
        )

        return ApiResponse(
            data=HealthStatus(
                status=status,
                persistence=persistence_ok,
                message_bus=bus_ok,
                version=__version__,
                uptime_seconds=uptime,
            ),
        )
