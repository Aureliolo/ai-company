"""Health check controller."""

import time
from enum import StrEnum

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
        persistence: Whether persistence backend is healthy.
        message_bus: Whether message bus is running.
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

        persistence_ok: bool | None
        if app_state.has_persistence:
            try:
                persistence_ok = await app_state.persistence.health_check()
            except Exception:
                logger.warning(
                    API_HEALTH_CHECK,
                    component="persistence",
                    exc_info=True,
                )
                persistence_ok = False
        else:
            persistence_ok = None

        bus_ok: bool | None
        if app_state.has_message_bus:
            try:
                bus_ok = app_state.message_bus.is_running
            except Exception:
                logger.warning(
                    API_HEALTH_CHECK,
                    component="message_bus",
                    exc_info=True,
                )
                bus_ok = False
        else:
            bus_ok = None

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
