"""Department controller -- listing and health aggregation."""

import asyncio
import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Self

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.api.dto import ApiResponse, PaginatedResponse
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.budget.trends import BucketSize, TrendDataPoint, bucket_cost_records
from synthorg.constants import BUDGET_ROUNDING_PRECISION
from synthorg.core.company import Department  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_DEPARTMENT_HEALTH_QUERIED,
    API_REQUEST_ERROR,
    API_RESOURCE_NOT_FOUND,
)

if TYPE_CHECKING:
    from synthorg.budget.cost_record import CostRecord
    from synthorg.config.schema import AgentConfig
    from synthorg.hr.performance.models import AgentPerformanceSnapshot

logger = get_logger(__name__)


# ── Response model ────────────────────────────────────────────


class DepartmentHealth(BaseModel):
    """Department-level health aggregation for dashboard display.

    Attributes:
        department_name: Department name.
        agent_count: Total agents in the department.
        active_agent_count: Number of active agents.
        utilization_percent: Percentage of agents that are active.
        avg_performance_score: Mean quality score across agents.
        department_cost_7d: Total cost in the last 7 days.
        cost_trend: Daily spend sparkline for the last 7 days.
        collaboration_score: Mean collaboration score across agents.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    department_name: NotBlankStr = Field(description="Department name")
    agent_count: int = Field(ge=0, description="Total agents")
    active_agent_count: int = Field(ge=0, description="Active agents")
    utilization_percent: float = Field(
        ge=0.0,
        le=100.0,
        description="Percent of agents active",
    )
    avg_performance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Mean quality score (0-10)",
    )
    department_cost_7d: float = Field(
        ge=0.0,
        description="Total cost in last 7 days (USD)",
    )
    cost_trend: tuple[TrendDataPoint, ...] = Field(
        description="7-day daily spend sparkline",
    )
    collaboration_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Mean collaboration score (0-10)",
    )

    @model_validator(mode="after")
    def _validate_active_le_total(self) -> Self:
        """Ensure active agent count does not exceed total."""
        if self.active_agent_count > self.agent_count:
            msg = (
                f"active_agent_count ({self.active_agent_count}) "
                f"exceeds agent_count ({self.agent_count})"
            )
            raise ValueError(msg)
        return self


# ── Helpers ───────────────────────────────────────────────────


def _filter_agents_by_department(
    agents: tuple[AgentConfig, ...],
    dept_name: str,
) -> tuple[AgentConfig, ...]:
    """Return agents belonging to the named department."""
    return tuple(a for a in agents if a.department == dept_name)


async def _resolve_active_count(
    app_state: AppState,
    dept_agent_names: frozenset[str],
) -> int:
    """Count active agents in the department via the registry.

    Falls back to 0 if the registry is unavailable.
    """
    if not app_state.has_agent_registry:
        return 0
    try:
        active = await app_state.agent_registry.list_active()
        return sum(1 for a in active if str(a.name).lower() in dept_agent_names)
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="departments.health",
            error="agent_registry_query_failed",
            exc_info=True,
        )
        return 0


async def _resolve_snapshots(
    app_state: AppState,
    agent_ids: tuple[str, ...],
) -> tuple[AgentPerformanceSnapshot, ...]:
    """Fetch performance snapshots for the given agent IDs.

    Uses ``asyncio.TaskGroup`` for parallel fan-out.  Agents
    whose snapshots fail to load are silently skipped.
    """
    results: list[AgentPerformanceSnapshot | None] = [None] * len(agent_ids)

    async def _fetch(idx: int, aid: str) -> None:
        try:
            results[idx] = await app_state.performance_tracker.get_snapshot(
                aid,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="departments.health.snapshot",
                agent_id=aid,
                exc_info=True,
            )

    async with asyncio.TaskGroup() as tg:
        for i, aid in enumerate(agent_ids):
            tg.create_task(_fetch(i, aid))

    return tuple(r for r in results if r is not None)


async def _resolve_agent_ids(
    app_state: AppState,
    agent_names: tuple[str, ...],
) -> tuple[str, ...]:
    """Map agent names to IDs via the registry.

    Uses ``asyncio.TaskGroup`` for parallel fan-out.
    Agents not found in the registry are silently skipped.
    """
    if not app_state.has_agent_registry:
        return ()
    results: list[str | None] = [None] * len(agent_names)

    async def _lookup(idx: int, name: str) -> None:
        try:
            identity = await app_state.agent_registry.get_by_name(name)
            if identity is not None:
                results[idx] = str(identity.id)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="departments.health.resolve_id",
                agent_name=name,
                exc_info=True,
            )

    async with asyncio.TaskGroup() as tg:
        for i, name in enumerate(agent_names):
            tg.create_task(_lookup(i, name))

    return tuple(r for r in results if r is not None)


def _mean_optional(values: list[float | None]) -> float | None:
    """Compute mean of non-None values, or None if all are None."""
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return round(math.fsum(filtered) / len(filtered), 2)


def _sparkline_start(now: datetime) -> datetime:
    """Compute the aligned start for a 7-day daily sparkline."""
    return now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    ) - timedelta(days=6)


def _aggregate_dept_cost(
    cost_records: tuple[CostRecord, ...],
    agent_id_set: frozenset[str],
    now: datetime,
) -> tuple[float, tuple[TrendDataPoint, ...]]:
    """Filter cost records to department agents and compute totals.

    Returns:
        Tuple of (total_cost_7d, cost_trend_sparkline).
    """
    dept_records = tuple(r for r in cost_records if r.agent_id in agent_id_set)
    total = round(
        math.fsum(r.cost_usd for r in dept_records),
        BUDGET_ROUNDING_PRECISION,
    )
    trend = bucket_cost_records(
        dept_records,
        _sparkline_start(now),
        now,
        BucketSize.DAY,
    )
    return total, trend


def _build_degraded_health(
    dept_name: str,
    agent_count: int,
    now: datetime,
) -> DepartmentHealth:
    """Build a minimal DepartmentHealth for when queries fail."""
    return DepartmentHealth(
        department_name=dept_name,
        agent_count=agent_count,
        active_agent_count=0,
        utilization_percent=0.0,
        department_cost_7d=0.0,
        cost_trend=bucket_cost_records(
            (),
            _sparkline_start(now),
            now,
            BucketSize.DAY,
        ),
    )


async def _assemble_department_health(
    app_state: AppState,
    dept_name: str,
    dept_agents: tuple[AgentConfig, ...],
) -> DepartmentHealth:
    """Aggregate all data sources into a DepartmentHealth response."""
    agent_count = len(dept_agents)
    agent_names = tuple(str(a.name) for a in dept_agents)
    name_set = frozenset(n.lower() for n in agent_names)

    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)

    # Phase 1: parallel queries for active count, cost, and agent IDs
    try:
        async with asyncio.TaskGroup() as tg:
            t_active = tg.create_task(
                _resolve_active_count(app_state, name_set),
            )
            t_cost = tg.create_task(
                app_state.cost_tracker.get_records(
                    start=seven_days_ago,
                    end=now,
                ),
            )
            t_ids = tg.create_task(
                _resolve_agent_ids(app_state, agent_names),
            )
    except ExceptionGroup as eg:
        fatal = eg.subgroup((MemoryError, RecursionError))
        if fatal is not None:
            raise fatal from eg
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="departments.health",
            department=dept_name,
            error_count=len(eg.exceptions),
            exc_info=True,
        )
        return _build_degraded_health(dept_name, agent_count, now)

    active_count = t_active.result()
    cost_records: tuple[CostRecord, ...] = t_cost.result()
    agent_ids = t_ids.result()

    # Phase 2: snapshots (depend on resolved agent_ids)
    snapshots = await _resolve_snapshots(app_state, agent_ids)

    # Aggregate
    agent_id_set = frozenset(agent_ids)
    dept_cost_7d, cost_trend = _aggregate_dept_cost(
        cost_records,
        agent_id_set,
        now,
    )
    utilization = round(active_count / agent_count * 100, 2) if agent_count > 0 else 0.0

    return DepartmentHealth(
        department_name=dept_name,
        agent_count=agent_count,
        active_agent_count=active_count,
        utilization_percent=utilization,
        avg_performance_score=_mean_optional(
            [s.overall_quality_score for s in snapshots],
        ),
        department_cost_7d=dept_cost_7d,
        cost_trend=cost_trend,
        collaboration_score=_mean_optional(
            [s.overall_collaboration_score for s in snapshots],
        ),
    )


# ── Controller ────────────────────────────────────────────────


class DepartmentController(Controller):
    """Read-only access to departments and health aggregation."""

    path = "/departments"
    tags = ("departments",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_departments(
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[Department]:
        """List all departments.

        Args:
            state: Application state.
            offset: Pagination offset.
            limit: Page size.

        Returns:
            Paginated department list.
        """
        app_state: AppState = state.app_state
        departments = await app_state.config_resolver.get_departments()
        page, meta = paginate(departments, offset=offset, limit=limit)
        return PaginatedResponse(data=page, pagination=meta)

    @get("/{name:str}")
    async def get_department(
        self,
        state: State,
        name: PathName,
    ) -> ApiResponse[Department]:
        """Get a department by name.

        Args:
            state: Application state.
            name: Department name.

        Returns:
            Department envelope.

        Raises:
            NotFoundError: If the department is not found.
        """
        app_state: AppState = state.app_state
        departments = await app_state.config_resolver.get_departments()
        for dept in departments:
            if dept.name == name:
                return ApiResponse(data=dept)
        msg = f"Department {name!r} not found"
        logger.warning(API_RESOURCE_NOT_FOUND, resource="department", name=name)
        raise NotFoundError(msg)

    @get("/{name:str}/health")
    async def get_department_health(
        self,
        state: State,
        name: PathName,
    ) -> ApiResponse[DepartmentHealth]:
        """Get department health aggregation.

        Aggregates agent count, utilization, cost, performance, and
        collaboration data for the named department.

        Args:
            state: Application state.
            name: Department name.

        Returns:
            Department health envelope.

        Raises:
            NotFoundError: If the department is not found.
        """
        app_state: AppState = state.app_state
        departments = await app_state.config_resolver.get_departments()

        found = False
        for dept in departments:
            if dept.name == name:
                found = True
                break
        if not found:
            msg = f"Department {name!r} not found"
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="department",
                name=name,
            )
            raise NotFoundError(msg)

        agents = await app_state.config_resolver.get_agents()
        dept_agents = _filter_agents_by_department(agents, name)
        health = await _assemble_department_health(
            app_state,
            name,
            dept_agents,
        )

        logger.debug(
            API_DEPARTMENT_HEALTH_QUERIED,
            department=name,
            agent_count=health.agent_count,
            active_count=health.active_agent_count,
            cost_7d=health.department_cost_7d,
        )
        return ApiResponse(data=health)
