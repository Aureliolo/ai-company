"""Simulation run lifecycle endpoints at /simulations."""

import asyncio
from datetime import UTC, datetime
from typing import Any

from litestar import Controller, Request, get, post
from litestar.datastructures import State  # noqa: TC002
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.api.channels import CHANNEL_SIMULATIONS, publish_ws_event
from synthorg.api.dto import ApiResponse, PaginatedResponse
from synthorg.api.errors import ConflictError, NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.api.ws_models import WsEventType
from synthorg.client.config import SimulationRunnerConfig
from synthorg.client.generators.procedural import ProceduralGenerator
from synthorg.client.models import (
    SimulationConfig,  # noqa: TC001
    SimulationMetrics,  # noqa: TC001
)
from synthorg.client.report.detailed import DetailedReport
from synthorg.client.report.summary import SummaryReport
from synthorg.client.runner import SimulationRunner
from synthorg.client.store import SimulationRecord
from synthorg.observability import get_logger

logger = get_logger(__name__)


class StartSimulationPayload(BaseModel):
    """Request payload for starting a new simulation run."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    config: SimulationConfig = Field(description="Simulation configuration")


class SimulationStatusResponse(BaseModel):
    """Public view of a simulation run."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    simulation_id: str
    status: str
    config: SimulationConfig
    metrics: SimulationMetrics
    progress: float
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    error: str | None = None


def _to_response(record: SimulationRecord) -> SimulationStatusResponse:
    """Convert a store record into the API response shape."""
    return SimulationStatusResponse(
        simulation_id=record.simulation_id,
        status=record.status,
        config=record.config,
        metrics=record.metrics,
        progress=record.progress,
        started_at=record.started_at,
        completed_at=record.completed_at,
        error=record.error,
    )


def _publish_event(
    request: Request[Any, Any, Any],
    event_type: WsEventType,
    record: SimulationRecord,
) -> None:
    """Best-effort publish a simulation lifecycle event."""
    publish_ws_event(
        request,
        event_type,
        CHANNEL_SIMULATIONS,
        {
            "simulation_id": record.simulation_id,
            "status": record.status,
            "progress": record.progress,
        },
    )


async def _run_in_background(
    *,
    app_state: AppState,
    record: SimulationRecord,
) -> None:
    """Execute a simulation run and update the store with results."""
    sim_state = app_state.client_simulation_state
    if sim_state.intake_engine is None:
        await sim_state.simulation_store.update_status(
            record.simulation_id,
            status="failed",
            error="Intake engine not configured",
        )
        return
    clients = await sim_state.pool.list_clients()
    if not clients:
        await sim_state.simulation_store.update_status(
            record.simulation_id,
            status="failed",
            error="No clients in pool",
        )
        return
    runner = SimulationRunner(
        config=SimulationRunnerConfig(
            max_concurrent_tasks=4,
            task_timeout_sec=30.0,
            review_timeout_sec=30.0,
        ),
        intake_engine=sim_state.intake_engine,
        feedback_sink=sim_state.feedback_store.record,
    )
    try:
        metrics, _ = await runner.run(
            sim_config=record.config,
            clients=clients,
            generator=ProceduralGenerator(seed=1),
        )
    except Exception as exc:
        logger.exception(
            "simulation.run.failed",
            simulation_id=record.simulation_id,
        )
        await sim_state.simulation_store.update_status(
            record.simulation_id,
            status="failed",
            error=str(exc),
        )
        return
    await sim_state.simulation_store.update_status(
        record.simulation_id,
        status="completed",
        metrics=metrics,
        progress=1.0,
    )


class SimulationController(Controller):
    """Simulation run lifecycle endpoints."""

    path = "/simulations"
    tags = ("simulations",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_simulations(
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[SimulationStatusResponse]:
        """List all known simulation runs."""
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        records = await sim_state.simulation_store.list_all()
        responses = tuple(_to_response(r) for r in records)
        page, meta = paginate(responses, offset=offset, limit=limit)
        return PaginatedResponse(data=page, pagination=meta)

    @get("/{simulation_id:str}")
    async def get_simulation(
        self,
        state: State,
        simulation_id: str,
    ) -> ApiResponse[SimulationStatusResponse]:
        """Return a single simulation run record."""
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            record = await sim_state.simulation_store.get(simulation_id)
        except KeyError as exc:
            msg = f"Simulation {simulation_id!r} not found"
            raise NotFoundError(msg) from exc
        return ApiResponse(data=_to_response(record))

    @post("/", guards=[require_write_access], status_code=201)
    async def start_simulation(
        self,
        request: Request[Any, Any, Any],
        state: State,
        data: StartSimulationPayload,
    ) -> ApiResponse[SimulationStatusResponse]:
        """Start a new simulation run in the background.

        The run executes asynchronously; poll ``GET /simulations/{id}``
        to observe progress and final metrics.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        record = SimulationRecord(
            simulation_id=data.config.simulation_id,
            config=data.config,
            status="running",
            started_at=datetime.now(UTC),
        )
        await sim_state.simulation_store.save(record)
        _publish_event(request, WsEventType.SIMULATION_STARTED, record)

        async def runner_task() -> None:
            await _run_in_background(app_state=app_state, record=record)
            final = await sim_state.simulation_store.get(record.simulation_id)
            event = (
                WsEventType.SIMULATION_COMPLETED
                if final.status == "completed"
                else WsEventType.SIMULATION_CANCELLED
            )
            _publish_event(request, event, final)

        asyncio.create_task(runner_task())  # noqa: RUF006
        return ApiResponse(data=_to_response(record))

    @post("/{simulation_id:str}/cancel", guards=[require_write_access])
    async def cancel_simulation(
        self,
        request: Request[Any, Any, Any],
        state: State,
        simulation_id: str,
    ) -> ApiResponse[SimulationStatusResponse]:
        """Mark a simulation run as cancelled.

        The in-memory runner does not support cooperative
        cancellation yet, so this is a soft cancel that flips the
        status flag. Already-terminal runs produce a 409.

        Raises:
            NotFoundError: If the simulation id is not known.
            ConflictError: If the run is already in a terminal state.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            record = await sim_state.simulation_store.get(simulation_id)
        except KeyError as exc:
            msg = f"Simulation {simulation_id!r} not found"
            raise NotFoundError(msg) from exc
        if record.status in {"completed", "cancelled", "failed"}:
            msg = f"Simulation already {record.status}"
            raise ConflictError(msg)
        updated = await sim_state.simulation_store.update_status(
            simulation_id,
            status="cancelled",
        )
        _publish_event(request, WsEventType.SIMULATION_CANCELLED, updated)
        return ApiResponse(data=_to_response(updated))

    @get("/{simulation_id:str}/report")
    async def get_report(
        self,
        state: State,
        simulation_id: str,
        fmt: str = "summary",
    ) -> ApiResponse[dict[str, Any]]:
        """Return a generated report for a simulation run.

        Args:
            state: Injected app state.
            simulation_id: Id of the run to report on.
            fmt: Report format -- ``summary`` (default) or
                ``detailed``.

        Raises:
            NotFoundError: If the simulation id is not known.
            ConflictError: If ``fmt`` is not a supported format.
        """
        app_state: AppState = state.app_state
        sim_state = app_state.client_simulation_state
        try:
            record = await sim_state.simulation_store.get(simulation_id)
        except KeyError as exc:
            msg = f"Simulation {simulation_id!r} not found"
            raise NotFoundError(msg) from exc
        if fmt == "summary":
            payload = await SummaryReport().generate_report(record.metrics)
        elif fmt == "detailed":
            payload = await DetailedReport().generate_report(record.metrics)
        else:
            msg = f"Unsupported report format: {fmt!r}"
            raise ConflictError(msg)
        payload["simulation_id"] = record.simulation_id
        payload["status"] = record.status
        return ApiResponse(data=payload)
