"""Department controller -- listing, health, ceremony policy, and CRUD mutations."""

import asyncio
import copy
import json
import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Self

from litestar import Controller, Request, Response, delete, get, patch, post, put
from litestar.datastructures import State  # noqa: TC002
from litestar.status_codes import HTTP_204_NO_CONTENT
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from synthorg.api.channels import CHANNEL_DEPARTMENTS, publish_ws_event
from synthorg.api.concurrency import compute_etag
from synthorg.api.controllers._workflow_helpers import get_auth_user_id
from synthorg.api.dto import ApiResponse, PaginatedResponse
from synthorg.api.dto_org import (  # noqa: TC001
    CreateDepartmentRequest,
    ReorderAgentsRequest,
    UpdateDepartmentRequest,
)
from synthorg.api.errors import (
    ApiValidationError,
    NotFoundError,
    ServiceUnavailableError,
)
from synthorg.api.guards import (
    require_org_mutation,
    require_read_access,
)
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.api.ws_models import WsEventType
from synthorg.budget.currency import DEFAULT_CURRENCY
from synthorg.budget.trends import BucketSize, TrendDataPoint, bucket_cost_records
from synthorg.config.schema import AgentConfig  # noqa: TC001
from synthorg.constants import BUDGET_ROUNDING_PRECISION
from synthorg.core.company import Department  # noqa: TC001
from synthorg.core.enums import AgentStatus
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.workflow.ceremony_policy import CeremonyPolicyConfig
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_CEREMONY_POLICY_DEPT_CLEARED,
    API_CEREMONY_POLICY_DEPT_UPDATED,
    API_DEPARTMENT_HEALTH_QUERIED,
    API_REQUEST_ERROR,
    API_RESOURCE_NOT_FOUND,
    API_SERVICE_UNAVAILABLE,
)

if TYPE_CHECKING:
    from synthorg.budget.cost_record import CostRecord
    from synthorg.hr.performance.models import AgentPerformanceSnapshot

logger = get_logger(__name__)


# ── Response model ────────────────────────────────────────────


class DepartmentHealth(BaseModel):
    """Department-level health aggregation for dashboard display.

    Attributes:
        department_name: Department name.
        agent_count: Total agents in the department.
        active_agent_count: Number of active agents.
        avg_performance_score: Mean quality score across agents.
        department_cost_7d: Total cost in the last 7 days.
        cost_trend: Daily spend sparkline for the last 7 days.
        collaboration_score: Mean collaboration score across agents.
        utilization_percent: Derived (computed_field) from
            active_agent_count / agent_count.
        currency: ISO 4217 currency code.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    department_name: NotBlankStr = Field(description="Department name")
    agent_count: int = Field(ge=0, description="Total agents")
    active_agent_count: int = Field(ge=0, description="Active agents")
    currency: str = Field(
        default=DEFAULT_CURRENCY,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )
    avg_performance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Mean quality score (0-10)",
    )
    department_cost_7d: float = Field(
        ge=0.0,
        description="Total cost in last 7 days",
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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def utilization_percent(self) -> float:
        """Percentage of agents that are active."""
        if self.agent_count == 0:
            return 0.0
        return round(self.active_agent_count / self.agent_count * 100, 2)

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
    """Return agents belonging to the named department (case-insensitive)."""
    lower = dept_name.lower()
    return tuple(a for a in agents if a.department.lower() == lower)


async def _resolve_active_count(
    app_state: AppState,
    dept_name: str,
) -> int:
    """Count active agents in the department via the registry.

    Falls back to 0 if the registry is unavailable.
    """
    if not app_state.has_agent_registry:
        return 0
    try:
        dept_agents = await app_state.agent_registry.list_by_department(
            dept_name,
        )
        return sum(1 for a in dept_agents if a.status == AgentStatus.ACTIVE)
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
    whose snapshots fail to load are skipped with a warning log.
    """
    results: list[AgentPerformanceSnapshot | None] = [None] * len(agent_ids)

    async def _fetch(idx: int, aid: str) -> None:
        try:
            results[idx] = await app_state.performance_tracker.get_snapshot(
                aid,
            )
        except MemoryError, RecursionError:
            raise
        except ServiceUnavailableError:
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
    Agents not found in the registry are skipped with a warning log.
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
        math.fsum(r.cost for r in dept_records),
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
    *,
    currency: str = DEFAULT_CURRENCY,
) -> DepartmentHealth:
    """Build a minimal DepartmentHealth for when queries fail."""
    return DepartmentHealth(
        department_name=dept_name,
        agent_count=agent_count,
        active_agent_count=0,
        department_cost_7d=0.0,
        cost_trend=bucket_cost_records(
            (),
            _sparkline_start(now),
            now,
            BucketSize.DAY,
        ),
        currency=currency,
    )


def _build_health_from_data(  # noqa: PLR0913
    dept_name: str,
    agent_count: int,
    active_count: int,
    cost_records: tuple[CostRecord, ...],
    agent_ids: tuple[str, ...],
    snapshots: tuple[AgentPerformanceSnapshot, ...],
    now: datetime,
    *,
    currency: str = DEFAULT_CURRENCY,
) -> DepartmentHealth:
    """Build DepartmentHealth from resolved query results."""
    agent_id_set = frozenset(agent_ids)
    dept_cost_7d, cost_trend = _aggregate_dept_cost(
        cost_records,
        agent_id_set,
        now,
    )
    return DepartmentHealth(
        department_name=dept_name,
        agent_count=agent_count,
        active_agent_count=active_count,
        avg_performance_score=_mean_optional(
            [s.overall_quality_score for s in snapshots],
        ),
        department_cost_7d=dept_cost_7d,
        cost_trend=cost_trend,
        collaboration_score=_mean_optional(
            [s.overall_collaboration_score for s in snapshots],
        ),
        currency=currency,
    )


async def _assemble_department_health(
    app_state: AppState,
    dept_name: str,
    dept_agents: tuple[AgentConfig, ...],
    *,
    currency: str = DEFAULT_CURRENCY,
) -> DepartmentHealth:
    """Aggregate all data sources into a DepartmentHealth response.

    Phase 1 queries active agent count, cost records, and agent ID
    resolution in parallel via TaskGroup.  If Phase 1 fails, returns
    a degraded health response with zeroed metrics.  Phase 2 fetches
    performance snapshots (depends on resolved agent IDs from Phase 1).

    Args:
        app_state: Application state with service references.
        dept_name: Department name.
        dept_agents: Agent configurations belonging to the department.
        currency: ISO 4217 currency code for display formatting.

    Returns:
        Aggregated department health, possibly degraded on failure.
    """
    agent_count = len(dept_agents)
    agent_names = tuple(str(a.name) for a in dept_agents)

    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)

    # Phase 1: parallel queries for active count, cost, and agent IDs
    try:
        async with asyncio.TaskGroup() as tg:
            t_active = tg.create_task(
                _resolve_active_count(app_state, dept_name),
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
        return _build_degraded_health(dept_name, agent_count, now, currency=currency)

    # Phase 2: snapshots (depend on resolved agent_ids)
    snapshots = await _resolve_snapshots(app_state, t_ids.result())

    return _build_health_from_data(
        dept_name=dept_name,
        agent_count=agent_count,
        active_count=t_active.result(),
        cost_records=t_cost.result(),
        agent_ids=t_ids.result(),
        snapshots=snapshots,
        now=now,
        currency=currency,
    )


# ── Department ceremony policy helpers ────────────────────────


async def _require_department_exists(
    app_state: AppState,
    name: str,
) -> str:
    """Raise NotFoundError if the department does not exist.

    Args:
        app_state: Application state with config resolver.
        name: Department name (case-insensitive lookup).

    Returns:
        The canonical department name as stored.

    Raises:
        NotFoundError: If the department is not found.
        ServiceUnavailableError: If the config resolver is not available.
    """
    if not app_state.has_config_resolver:
        msg = "Config resolver not available"
        logger.warning(API_SERVICE_UNAVAILABLE, service="config_resolver")
        raise ServiceUnavailableError(msg)
    departments = await app_state.config_resolver.get_departments()
    name_lower = name.lower()
    for dept in departments:
        if dept.name.lower() == name_lower:
            return dept.name
    msg = f"Department {name!r} not found"
    logger.warning(API_RESOURCE_NOT_FOUND, resource="department", name=name)
    raise NotFoundError(msg)


async def _load_dept_policies_json(
    app_state: AppState,
    *,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """Load the dept_ceremony_policies JSON setting.

    Args:
        app_state: Application state with settings service.
        raise_on_error: If ``True``, propagate exceptions instead
            of returning an empty dict.  Must be ``True`` for
            read-modify-write callers to prevent data loss.

    Returns:
        Parsed dict of department overrides. Empty dict if the
        setting is not persisted or unreadable (only when
        ``raise_on_error`` is ``False``).

    Raises:
        ServiceUnavailableError: If settings service is unavailable
            and ``raise_on_error`` is ``True``.
    """
    if not app_state.has_settings_service:
        if raise_on_error:
            msg = "Settings service not available"
            logger.warning(API_SERVICE_UNAVAILABLE, service="settings")
            raise ServiceUnavailableError(msg)
        return {}
    try:
        entry = await app_state.settings_service.get(
            "coordination",
            "dept_ceremony_policies",
        )
        parsed = json.loads(entry.value)
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="departments.ceremony_policy.load",
            error="failed to load dept_ceremony_policies",
            exc_info=True,
        )
        if raise_on_error:
            msg = "Failed to load department ceremony policies"
            raise ServiceUnavailableError(msg) from exc
        return {}

    if not isinstance(parsed, dict):
        msg = f"dept_ceremony_policies is not a dict: {type(parsed).__name__}"
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="departments.ceremony_policy.load",
            error=msg,
        )
        if raise_on_error:
            raise ServiceUnavailableError(msg)
        return {}
    return parsed


async def _save_dept_policies_json(
    app_state: AppState,
    policies: dict[str, Any],
) -> None:
    """Persist the dept_ceremony_policies JSON setting.

    Args:
        app_state: Application state with settings service.
        policies: Full department overrides dict.

    Raises:
        ServiceUnavailableError: If the settings service is not
            available.
    """
    if not app_state.has_settings_service:
        msg = "Settings service not available"
        logger.warning(API_SERVICE_UNAVAILABLE, service="settings")
        raise ServiceUnavailableError(msg)
    try:
        await app_state.settings_service.set(
            "coordination",
            "dept_ceremony_policies",
            json.dumps(policies, separators=(",", ":")),
        )
    except MemoryError, RecursionError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception as exc:
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="departments.ceremony_policy.save",
            error="failed to persist dept_ceremony_policies",
            exc_info=True,
        )
        msg = "Failed to save department ceremony policies"
        raise ServiceUnavailableError(msg) from exc


async def _get_dept_ceremony_override(
    app_state: AppState,
    department_name: NotBlankStr,
) -> dict[str, Any] | None:
    """Get the ceremony policy override for a department.

    Checks the settings-based overrides first, then falls back to
    the department's config ``ceremony_policy`` field.

    Args:
        app_state: Application state.
        department_name: Department name.

    Returns:
        The override dict, or None if the department inherits.

    Raises:
        NotFoundError: If the department does not exist.
        ServiceUnavailableError: If the settings service is not
            available or the JSON blob is unreadable.
    """
    # Check settings-based overrides first (raise on error to
    # surface service failures instead of silently showing "inherit")
    policies = await _load_dept_policies_json(
        app_state,
        raise_on_error=True,
    )
    if department_name in policies:
        val = policies[department_name]
        # None sentinel means "explicitly inheriting"
        if val is None:
            return None
        if isinstance(val, dict):
            # Validate structure before returning to catch corrupt data
            try:
                CeremonyPolicyConfig.model_validate(val)
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    API_REQUEST_ERROR,
                    endpoint="departments.ceremony_policy.get",
                    department=department_name,
                    error=f"Invalid stored override: {exc}",
                )
                msg = f"Corrupt ceremony policy override for {department_name!r}"
                raise ServiceUnavailableError(msg) from exc
            return val
        return None

    # Fall back to config-based ceremony_policy
    if not app_state.has_config_resolver:
        msg = "Config resolver not available"
        logger.warning(API_SERVICE_UNAVAILABLE, service="config_resolver")
        raise ServiceUnavailableError(msg)
    departments = await app_state.config_resolver.get_departments()
    for dept in departments:
        if dept.name == department_name:
            return dept.ceremony_policy
    msg = f"Department {department_name!r} not found"
    logger.warning(
        API_RESOURCE_NOT_FOUND,
        resource="department",
        name=department_name,
    )
    raise NotFoundError(msg)


# Serializes concurrent read-modify-write operations on the
# dept_ceremony_policies JSON blob.  The asyncio.Lock is sufficient
# because Litestar runs in a single-process, single-event-loop
# deployment model -- all concurrent requests share the same loop.
# TODO: multi-worker deployment requires settings-service CAS or per-dept keys
_dept_policy_lock = asyncio.Lock()


async def _set_dept_ceremony_override(
    app_state: AppState,
    department_name: NotBlankStr,
    policy: dict[str, Any],
) -> None:
    """Set the ceremony policy override for a department.

    Args:
        app_state: Application state.
        department_name: Department name.
        policy: Validated ceremony policy dict.

    Raises:
        ServiceUnavailableError: If the settings service or JSON
            blob cannot be loaded (prevents data loss from
            writing over unreadable state).
    """
    async with _dept_policy_lock:
        policies = await _load_dept_policies_json(
            app_state,
            raise_on_error=True,
        )
        policies[department_name] = copy.deepcopy(policy)
        await _save_dept_policies_json(app_state, policies)


async def _clear_dept_ceremony_override(
    app_state: AppState,
    department_name: NotBlankStr,
) -> None:
    """Clear the ceremony policy override for a department.

    Persists a ``None`` sentinel so the department explicitly
    inherits the project-level policy, even if the config YAML
    defines a ``ceremony_policy`` for the department.

    Args:
        app_state: Application state.
        department_name: Department name.

    Raises:
        ServiceUnavailableError: If the settings service or JSON
            blob cannot be loaded.
    """
    async with _dept_policy_lock:
        policies = await _load_dept_policies_json(
            app_state,
            raise_on_error=True,
        )
        policies[department_name] = None
        await _save_dept_policies_json(app_state, policies)


# ── Controller ────────────────────────────────────────────────


class DepartmentController(Controller):
    """Departments -- CRUD, health aggregation, ceremony policy."""

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
        name_lower = name.lower()
        for dept in departments:
            if dept.name.lower() == name_lower:
                return ApiResponse(data=dept)
        msg = f"Department {name!r} not found"
        logger.warning(API_RESOURCE_NOT_FOUND, resource="department", name=name)
        raise NotFoundError(msg)

    @post("/", guards=[require_org_mutation()], status_code=201)
    async def create_department(
        self,
        request: Request[Any, Any, Any],
        state: State,
        data: CreateDepartmentRequest,
    ) -> ApiResponse[Department]:
        """Create a new department.

        Args:
            request: Incoming request (for WS publishing).
            state: Application state.
            data: Department creation request.

        Returns:
            Created department envelope (HTTP 201).
        """
        app_state: AppState = state.app_state
        dept = await app_state.org_mutation_service.create_department(
            data,
            saved_by=get_auth_user_id(request),
        )
        publish_ws_event(
            request,
            WsEventType.DEPARTMENT_CREATED,
            CHANNEL_DEPARTMENTS,
            {"name": dept.name, "budget_percent": dept.budget_percent},
        )
        return ApiResponse(data=dept)

    @patch(
        "/{name:str}",
        guards=[require_org_mutation(department_param="name")],
    )
    async def update_department(
        self,
        request: Request[Any, Any, Any],
        state: State,
        name: PathName,
        data: UpdateDepartmentRequest,
    ) -> Response[ApiResponse[Department]]:
        """Update an existing department.

        Supports optimistic concurrency via ``If-Match`` header.

        Args:
            request: Incoming request (for WS publishing).
            state: Application state.
            name: Department name.
            data: Partial update request.

        Returns:
            Updated department envelope with ETag header.
        """
        app_state: AppState = state.app_state
        if_match = request.headers.get("if-match")
        updated = await app_state.org_mutation_service.update_department(
            name,
            data,
            saved_by=get_auth_user_id(request),
            if_match=if_match,
        )
        publish_ws_event(
            request,
            WsEventType.DEPARTMENT_UPDATED,
            CHANNEL_DEPARTMENTS,
            {"name": updated.name},
        )
        new_etag = compute_etag(
            json.dumps(
                updated.model_dump(mode="json"),
                sort_keys=True,
            ),
            "",
        )
        return Response(
            content=ApiResponse(data=updated),
            headers={"ETag": new_etag},
        )

    @delete(
        "/{name:str}",
        guards=[require_org_mutation(department_param="name")],
        status_code=HTTP_204_NO_CONTENT,
    )
    async def delete_department(
        self,
        request: Request[Any, Any, Any],
        state: State,
        name: PathName,
    ) -> None:
        """Delete a department.

        Rejects deletion if agents are attached (HTTP 409).

        Args:
            request: Incoming request (for WS publishing).
            state: Application state.
            name: Department name.
        """
        app_state: AppState = state.app_state
        await app_state.org_mutation_service.delete_department(
            name,
            saved_by=get_auth_user_id(request),
        )
        publish_ws_event(
            request,
            WsEventType.DEPARTMENT_DELETED,
            CHANNEL_DEPARTMENTS,
            {"name": name},
        )

    @post(
        "/{name:str}/reorder-agents",
        guards=[require_org_mutation(department_param="name")],
    )
    async def reorder_agents(
        self,
        request: Request[Any, Any, Any],
        state: State,
        name: PathName,
        data: ReorderAgentsRequest,
    ) -> ApiResponse[tuple[AgentConfig, ...]]:
        """Reorder agents within a department.

        The payload must be an exact permutation of agents in the
        department (no additions or removals).

        Args:
            request: Incoming request (for WS publishing).
            state: Application state.
            name: Department name.
            data: Ordered agent names.

        Returns:
            Reordered agents envelope.
        """
        app_state: AppState = state.app_state
        reordered = await app_state.org_mutation_service.reorder_agents(
            name,
            data,
        )
        publish_ws_event(
            request,
            WsEventType.AGENTS_REORDERED,
            CHANNEL_DEPARTMENTS,
            {
                "department": name,
                "agent_names": [a.name for a in reordered],
            },
        )
        return ApiResponse(data=reordered)

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

        # Fetch departments and agents (both are config reads)
        departments = await app_state.config_resolver.get_departments()
        dept_by_name = {dept.name.lower(): dept for dept in departments}
        if name.lower() not in dept_by_name:
            msg = f"Department {name!r} not found"
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="department",
                name=name,
            )
            raise NotFoundError(msg)

        dept = dept_by_name[name.lower()]
        canonical_name = dept.name

        agents = await app_state.config_resolver.get_agents()
        dept_agents = _filter_agents_by_department(agents, canonical_name)
        budget_cfg = await app_state.config_resolver.get_budget_config()
        health = await _assemble_department_health(
            app_state,
            canonical_name,
            dept_agents,
            currency=budget_cfg.currency,
        )

        logger.debug(
            API_DEPARTMENT_HEALTH_QUERIED,
            department=canonical_name,
            agent_count=health.agent_count,
            active_count=health.active_agent_count,
            cost_7d=health.department_cost_7d,
        )
        return ApiResponse(data=health)

    @get("/{name:str}/ceremony-policy")
    async def get_department_ceremony_policy(
        self,
        state: State,
        name: PathName,
    ) -> ApiResponse[dict[str, Any] | None]:
        """Get the department-level ceremony policy override.

        Returns the override dict if the department has one, or
        ``null`` if the department inherits the project-level policy.

        Args:
            state: Application state.
            name: Department name.

        Returns:
            Ceremony policy dict or null envelope.

        Raises:
            NotFoundError: If the department is not found.
        """
        app_state: AppState = state.app_state
        canonical = await _require_department_exists(app_state, name)
        policy = await _get_dept_ceremony_override(app_state, canonical)
        return ApiResponse(data=policy)

    @put(
        "/{name:str}/ceremony-policy",
        guards=[require_org_mutation(department_param="name")],
    )
    async def update_department_ceremony_policy(
        self,
        state: State,
        name: PathName,
        data: dict[str, Any],
    ) -> ApiResponse[dict[str, Any]]:
        """Set the ceremony policy override for a department.

        Validates the input as a partial ``CeremonyPolicyConfig``.
        Stores the override in the settings system under the
        ``dept_ceremony_policies`` JSON key.

        Args:
            state: Application state.
            name: Department name.
            data: Partial ceremony policy dict.

        Returns:
            The stored ceremony policy dict.

        Raises:
            NotFoundError: If the department does not exist.
            ApiValidationError: If the policy data is invalid.
        """
        app_state: AppState = state.app_state

        # Verify the department exists and get canonical name
        canonical = await _require_department_exists(app_state, name)

        # Validate policy data via Pydantic
        try:
            validated = CeremonyPolicyConfig.model_validate(data)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            msg = "Invalid ceremony policy data"
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="departments.ceremony_policy.update",
                error=str(exc),
            )
            raise ApiValidationError(msg) from exc

        clean_data = validated.model_dump(mode="json", exclude_none=True)

        # Merge into the dept_ceremony_policies JSON setting
        await _set_dept_ceremony_override(app_state, canonical, clean_data)

        logger.info(
            API_CEREMONY_POLICY_DEPT_UPDATED,
            department=canonical,
            strategy=clean_data.get("strategy"),
        )
        return ApiResponse(data=clean_data)

    @delete(
        "/{name:str}/ceremony-policy",
        guards=[require_org_mutation(department_param="name")],
        status_code=HTTP_204_NO_CONTENT,
    )
    async def delete_department_ceremony_policy(
        self,
        state: State,
        name: PathName,
    ) -> None:
        """Clear the department ceremony policy override.

        The department will revert to inheriting the project-level
        policy.

        Args:
            state: Application state.
            name: Department name.

        Raises:
            NotFoundError: If the department does not exist.
        """
        app_state: AppState = state.app_state
        canonical = await _require_department_exists(app_state, name)
        await _clear_dept_ceremony_override(app_state, canonical)
        logger.info(
            API_CEREMONY_POLICY_DEPT_CLEARED,
            department=canonical,
        )
