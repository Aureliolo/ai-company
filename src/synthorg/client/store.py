"""In-memory stores for client simulation runtime state."""

import asyncio
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.client.models import (
    ClientFeedback,
    ClientRequest,
    SimulationConfig,
    SimulationMetrics,
)
from synthorg.core.types import NotBlankStr  # noqa: TC001

SimulationRunStatus = Literal[
    "pending",
    "running",
    "completed",
    "cancelled",
    "failed",
]
_TERMINAL_STATUSES: frozenset[SimulationRunStatus] = frozenset(
    {"completed", "cancelled", "failed"},
)


class FeedbackStore:
    """Thread-safe in-memory store for :class:`ClientFeedback`.

    Indexed by ``client_id`` so ``/clients/{id}/satisfaction`` can
    return the full review history for a single client without
    scanning every entry.
    """

    def __init__(self) -> None:
        """Initialize an empty store."""
        self._lock = asyncio.Lock()
        self._by_client: dict[str, list[ClientFeedback]] = {}

    async def record(self, feedback: ClientFeedback) -> None:
        """Append a feedback entry for its client."""
        async with self._lock:
            bucket = self._by_client.setdefault(feedback.client_id, [])
            bucket.append(feedback)

    async def list_for_client(
        self,
        client_id: str,
    ) -> tuple[ClientFeedback, ...]:
        """Return all feedback entries recorded for a client."""
        async with self._lock:
            return tuple(self._by_client.get(client_id, ()))

    async def clear(self, client_id: str) -> None:
        """Remove all feedback entries for a client (no-op if absent)."""
        async with self._lock:
            self._by_client.pop(client_id, None)


class RequestStore:
    """Thread-safe in-memory store for :class:`ClientRequest`.

    Backed by a dict keyed on ``request_id`` and guarded by an
    :class:`asyncio.Lock`. Used by the API controllers to surface
    the independent request lifecycle through HTTP endpoints.
    """

    def __init__(self) -> None:
        """Initialize an empty store."""
        self._lock = asyncio.Lock()
        self._requests: dict[str, ClientRequest] = {}

    async def save(self, request: ClientRequest) -> None:
        """Insert or replace a request by id."""
        async with self._lock:
            self._requests[request.request_id] = request

    async def get(self, request_id: str) -> ClientRequest:
        """Return the request by id or raise ``KeyError``."""
        async with self._lock:
            if request_id not in self._requests:
                msg = f"Request {request_id!r} not found"
                raise KeyError(msg)
            return self._requests[request_id]

    async def list_all(self) -> tuple[ClientRequest, ...]:
        """Return a snapshot of all stored requests."""
        async with self._lock:
            return tuple(self._requests.values())

    async def delete(self, request_id: str) -> None:
        """Remove a request by id (no-op if absent)."""
        async with self._lock:
            self._requests.pop(request_id, None)


class SimulationRecord(BaseModel):
    """Status record for a simulation run.

    Frozen Pydantic model. Persisted in-memory by
    :class:`SimulationStore` and exposed through the
    ``/simulations`` endpoints. Mutations go through
    ``SimulationStore.update_status`` which constructs a new record
    and rebinds it in the store -- never mutates in place.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    simulation_id: NotBlankStr = Field(description="Run identifier")
    config: SimulationConfig = Field(description="Run configuration")
    status: SimulationRunStatus = Field(default="pending")
    metrics: SimulationMetrics = Field(default_factory=SimulationMetrics)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    started_at: AwareDatetime | None = Field(default=None)
    completed_at: AwareDatetime | None = Field(default=None)
    error: str | None = Field(default=None)


class SimulationStore:
    """Thread-safe in-memory store for simulation run records."""

    def __init__(self) -> None:
        """Initialize an empty store."""
        self._lock = asyncio.Lock()
        self._runs: dict[str, SimulationRecord] = {}

    async def save(self, record: SimulationRecord) -> None:
        """Insert or replace a simulation record."""
        async with self._lock:
            self._runs[record.simulation_id] = record

    async def get(self, simulation_id: str) -> SimulationRecord:
        """Return the record by id or raise ``KeyError``."""
        async with self._lock:
            if simulation_id not in self._runs:
                msg = f"Simulation {simulation_id!r} not found"
                raise KeyError(msg)
            return self._runs[simulation_id]

    async def list_all(self) -> tuple[SimulationRecord, ...]:
        """Return a snapshot of all records."""
        async with self._lock:
            return tuple(self._runs.values())

    async def update_status(
        self,
        simulation_id: str,
        *,
        status: SimulationRunStatus,
        metrics: SimulationMetrics | None = None,
        progress: float | None = None,
        error: str | None = None,
    ) -> SimulationRecord:
        """Replace the stored record with an updated copy.

        Constructs a new frozen :class:`SimulationRecord` via
        ``model_copy`` rather than mutating in place, honoring the
        project's immutability rule.
        """
        async with self._lock:
            if simulation_id not in self._runs:
                msg = f"Simulation {simulation_id!r} not found"
                raise KeyError(msg)
            existing = self._runs[simulation_id]
            updates: dict[str, object] = {"status": status}
            if metrics is not None:
                updates["metrics"] = metrics
            if progress is not None:
                updates["progress"] = progress
            if error is not None:
                updates["error"] = error
            if status == "running" and existing.started_at is None:
                updates["started_at"] = datetime.now(UTC)
            if status in _TERMINAL_STATUSES:
                updates["completed_at"] = datetime.now(UTC)
            updated = existing.model_copy(update=updates)
            self._runs[simulation_id] = updated
            return updated
