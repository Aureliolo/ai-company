"""Org configuration mutation service.

Encapsulates read-modify-write operations on the company, department,
and agent configuration stored in the settings system.  All mutations
are serialised through a module-level ``asyncio.Lock`` which is safe
for the single-process, single-event-loop Litestar deployment model.
"""

import asyncio
import json
import math
from typing import Any

from synthorg.api.dto_org import (  # noqa: TC001
    CreateAgentOrgRequest,
    CreateDepartmentRequest,
    ReorderAgentsRequest,
    ReorderDepartmentsRequest,
    UpdateAgentOrgRequest,
    UpdateCompanyRequest,
    UpdateDepartmentRequest,
)
from synthorg.api.errors import ApiValidationError, ConflictError, NotFoundError
from synthorg.config.schema import AgentConfig
from synthorg.core.company import Department
from synthorg.core.enums import SeniorityLevel
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_AGENT_CREATED,
    API_AGENT_DELETED,
    API_AGENT_UPDATED,
    API_AGENTS_REORDERED,
    API_COMPANY_UPDATED,
    API_DEPARTMENT_CREATED,
    API_DEPARTMENT_DELETED,
    API_DEPARTMENT_UPDATED,
    API_DEPARTMENTS_REORDERED,
    API_RESOURCE_CONFLICT,
    API_RESOURCE_NOT_FOUND,
    API_VALIDATION_FAILED,
)
from synthorg.settings.resolver import ConfigResolver  # noqa: TC001
from synthorg.settings.service import SettingsService  # noqa: TC001

logger = get_logger(__name__)

# Serialises all org config mutations.  Safe for single-process,
# single-event-loop deployment (see _dept_policy_lock in departments.py).
_org_lock = asyncio.Lock()

_BUDGET_PERCENT_CAP = 100.0


class OrgMutationService:
    """Read-modify-write mutations on company/department/agent config.

    Args:
        settings_service: Settings persistence layer.
        config_resolver: Config resolution (DB > env > YAML > code).
    """

    def __init__(
        self,
        settings_service: SettingsService,
        config_resolver: ConfigResolver,
    ) -> None:
        self._settings = settings_service
        self._resolver = config_resolver

    # ── Internal helpers ──────────────────────────────────────

    async def _read_departments(self) -> tuple[Department, ...]:
        return await self._resolver.get_departments()

    async def _write_departments(
        self,
        departments: tuple[Department, ...],
    ) -> None:
        """Serialise and persist the department list."""
        payload = json.dumps(
            [d.model_dump(mode="json") for d in departments],
            separators=(",", ":"),
        )
        await self._settings.set("company", "departments", payload)

    async def _read_agents(self) -> tuple[AgentConfig, ...]:
        return await self._resolver.get_agents()

    async def _write_agents(
        self,
        agents: tuple[AgentConfig, ...],
    ) -> None:
        """Serialise and persist the agent list."""
        payload = json.dumps(
            [a.model_dump(mode="json") for a in agents],
            separators=(",", ":"),
        )
        await self._settings.set("company", "agents", payload)

    def _find_department(
        self,
        departments: tuple[Department, ...],
        name: str,
    ) -> Department | None:
        """Case-insensitive department lookup."""
        lower = name.lower()
        for dept in departments:
            if dept.name.lower() == lower:
                return dept
        return None

    def _find_agent(
        self,
        agents: tuple[AgentConfig, ...],
        name: str,
    ) -> AgentConfig | None:
        """Case-insensitive agent lookup."""
        lower = name.lower()
        for agent in agents:
            if agent.name.lower() == lower:
                return agent
        return None

    def _validate_permutation(
        self,
        current_names: tuple[str, ...],
        requested_names: tuple[str, ...],
        entity: str,
    ) -> None:
        """Ensure requested names are an exact permutation of current."""
        current_set = frozenset(n.lower() for n in current_names)
        requested_set = frozenset(n.lower() for n in requested_names)
        if current_set != requested_set or len(requested_names) != len(
            current_names,
        ):
            msg = f"Reorder must be an exact permutation of existing {entity} names"
            logger.warning(
                API_VALIDATION_FAILED,
                entity=entity,
                current_names=list(current_names),
                requested_names=list(requested_names),
            )
            raise ApiValidationError(msg)

    def _check_budget_sum(
        self,
        departments: tuple[Department, ...],
    ) -> None:
        """Log a warning if department budgets exceed 100%."""
        total = math.fsum(d.budget_percent for d in departments)
        if total > _BUDGET_PERCENT_CAP:
            logger.warning(
                API_COMPANY_UPDATED,
                note="budget_percent_sum_exceeds_100",
                total=round(total, 2),
            )

    # ── Company ───────────────────────────────────────────────

    async def update_company(
        self,
        data: UpdateCompanyRequest,
    ) -> dict[str, Any]:
        """Update individual company scalar settings.

        Args:
            data: Partial update request.

        Returns:
            Dict of the updated field names and values.
        """
        updated: dict[str, Any] = {}
        async with _org_lock:
            if data.company_name is not None:
                await self._settings.set(
                    "company",
                    "company_name",
                    data.company_name,
                )
                updated["company_name"] = data.company_name
            if data.autonomy_level is not None:
                await self._settings.set(
                    "company",
                    "autonomy_level",
                    data.autonomy_level.value,
                )
                updated["autonomy_level"] = data.autonomy_level.value
            if data.budget_monthly is not None:
                await self._settings.set(
                    "company",
                    "total_monthly",
                    str(data.budget_monthly),
                )
                updated["budget_monthly"] = data.budget_monthly
            if data.communication_pattern is not None:
                await self._settings.set(
                    "company",
                    "communication_pattern",
                    data.communication_pattern,
                )
                updated["communication_pattern"] = data.communication_pattern
        logger.info(API_COMPANY_UPDATED, fields=list(updated.keys()))
        return updated

    # ── Departments ───────────────────────────────────────────

    async def create_department(
        self,
        data: CreateDepartmentRequest,
    ) -> Department:
        """Create a new department.

        Args:
            data: Department creation request.

        Returns:
            The created Department model.

        Raises:
            ConflictError: If a department with the same name exists.
        """
        async with _org_lock:
            departments = await self._read_departments()
            if self._find_department(departments, data.name):
                msg = f"Department {data.name!r} already exists"
                logger.warning(API_RESOURCE_CONFLICT, reason=msg, department=data.name)
                raise ConflictError(msg)

            dept = Department(
                name=data.name,
                head=data.head,
                budget_percent=data.budget_percent,
                autonomy_level=data.autonomy_level,
            )
            new_departments = (*departments, dept)
            self._check_budget_sum(new_departments)
            await self._write_departments(new_departments)

        logger.info(
            API_DEPARTMENT_CREATED,
            department=data.name,
            budget_percent=data.budget_percent,
        )
        return dept

    async def update_department(
        self,
        name: str,
        data: UpdateDepartmentRequest,
    ) -> Department:
        """Update an existing department.

        Args:
            name: Current department name.
            data: Partial update request.

        Returns:
            The updated Department model.

        Raises:
            NotFoundError: If the department does not exist.
        """
        async with _org_lock:
            departments = await self._read_departments()
            existing = self._find_department(departments, name)
            if existing is None:
                msg = f"Department {name!r} not found"
                raise NotFoundError(msg)

            updates: dict[str, Any] = {}
            if "head" in data.model_fields_set and data.head is not None:
                updates["head"] = data.head
            if "budget_percent" in data.model_fields_set:
                updates["budget_percent"] = data.budget_percent
            if (
                "autonomy_level" in data.model_fields_set
                and data.autonomy_level is not None
            ):
                updates["autonomy_level"] = data.autonomy_level
            if "teams" in data.model_fields_set:
                updates["teams"] = tuple(data.teams) if data.teams else ()
            if (
                "ceremony_policy" in data.model_fields_set
                and data.ceremony_policy is not None
            ):
                updates["ceremony_policy"] = data.ceremony_policy

            updated = existing.model_copy(update=updates, deep=True)
            new_departments = tuple(
                updated if d.name.lower() == name.lower() else d for d in departments
            )
            self._check_budget_sum(new_departments)
            await self._write_departments(new_departments)

        logger.info(
            API_DEPARTMENT_UPDATED,
            department=name,
            updated_fields=list(updates.keys()),
        )
        return updated

    async def delete_department(self, name: str) -> None:
        """Delete a department.

        Args:
            name: Department name to delete.

        Raises:
            NotFoundError: If the department does not exist.
            ConflictError: If the department has agents attached.
        """
        async with _org_lock:
            departments = await self._read_departments()
            existing = self._find_department(departments, name)
            if existing is None:
                msg = f"Department {name!r} not found"
                logger.warning(API_RESOURCE_NOT_FOUND, reason=msg, department=name)
                raise NotFoundError(msg)

            # Referential integrity: reject if agents are attached
            agents = await self._read_agents()
            attached = tuple(a for a in agents if a.department.lower() == name.lower())
            if attached:
                msg = (
                    f"Cannot delete department {name!r}: "
                    f"{len(attached)} agents attached"
                )
                logger.warning(
                    API_RESOURCE_CONFLICT,
                    reason=msg,
                    department=name,
                    agent_count=len(attached),
                )
                raise ConflictError(msg)

            new_departments = tuple(
                d for d in departments if d.name.lower() != name.lower()
            )
            await self._write_departments(new_departments)

        logger.info(API_DEPARTMENT_DELETED, department=name)

    async def reorder_departments(
        self,
        data: ReorderDepartmentsRequest,
    ) -> tuple[Department, ...]:
        """Reorder departments.

        Args:
            data: Ordered list of department names.

        Returns:
            The reordered departments tuple.

        Raises:
            ApiValidationError: If names are not an exact permutation.
        """
        async with _org_lock:
            departments = await self._read_departments()
            current_names = tuple(d.name for d in departments)
            self._validate_permutation(
                current_names,
                data.department_names,
                "department",
            )

            dept_by_lower = {d.name.lower(): d for d in departments}
            reordered = tuple(dept_by_lower[n.lower()] for n in data.department_names)
            await self._write_departments(reordered)

        logger.info(
            API_DEPARTMENTS_REORDERED,
            order=[d.name for d in reordered],
        )
        return reordered

    # ── Agents ────────────────────────────────────────────────

    async def create_agent(
        self,
        data: CreateAgentOrgRequest,
    ) -> AgentConfig:
        """Create a new agent in the org config.

        Args:
            data: Agent creation request.

        Returns:
            The created AgentConfig model.

        Raises:
            ApiValidationError: If the department does not exist.
            ConflictError: If an agent with the same name exists.
        """
        async with _org_lock:
            departments = await self._read_departments()
            if not self._find_department(departments, data.department):
                msg = f"Department {data.department!r} does not exist"
                logger.warning(
                    API_VALIDATION_FAILED, reason=msg, department=data.department
                )
                raise ApiValidationError(msg)

            agents = await self._read_agents()
            if self._find_agent(agents, data.name):
                msg = f"Agent {data.name!r} already exists"
                logger.warning(API_RESOURCE_CONFLICT, reason=msg, agent=data.name)
                raise ConflictError(msg)

            model_dict: dict[str, Any] = {}
            if data.model_provider is not None:
                model_dict = {
                    "provider": str(data.model_provider),
                    "model_id": str(data.model_id),
                }

            agent = AgentConfig(
                name=data.name,
                role=data.role,
                department=data.department,
                level=data.level,
                model=model_dict,
            )
            new_agents = (*agents, agent)
            await self._write_agents(new_agents)

        logger.info(
            API_AGENT_CREATED,
            agent=data.name,
            department=data.department,
            level=data.level.value,
        )
        return agent

    async def _validate_agent_update(
        self,
        name: str,
        data: UpdateAgentOrgRequest,
        agents: tuple[AgentConfig, ...],
    ) -> dict[str, Any]:
        """Validate agent update and collect field changes."""
        updates: dict[str, Any] = {}
        fields_set = data.model_fields_set

        if "name" in fields_set and data.name is not None:
            if self._find_agent(
                tuple(a for a in agents if a.name.lower() != name.lower()),
                str(data.name),
            ):
                msg = f"Agent {data.name!r} already exists"
                logger.warning(
                    API_RESOURCE_CONFLICT, reason=msg, agent_name=str(data.name)
                )
                raise ConflictError(msg)
            updates["name"] = data.name

        if "role" in fields_set and data.role is not None:
            updates["role"] = data.role

        if "department" in fields_set and data.department is not None:
            departments = await self._read_departments()
            if not self._find_department(departments, str(data.department)):
                msg = f"Department {data.department!r} does not exist"
                logger.warning(
                    API_VALIDATION_FAILED, reason=msg, department=str(data.department)
                )
                raise ApiValidationError(msg)
            updates["department"] = data.department

        if "level" in fields_set and data.level is not None:
            updates["level"] = data.level

        if "autonomy_level" in fields_set and data.autonomy_level is not None:
            updates["autonomy_level"] = data.autonomy_level

        return updates

    async def update_agent(
        self,
        name: str,
        data: UpdateAgentOrgRequest,
    ) -> AgentConfig:
        """Update an existing agent.

        Args:
            name: Current agent name.
            data: Partial update request.

        Returns:
            The updated AgentConfig model.

        Raises:
            NotFoundError: If the agent does not exist.
            ApiValidationError: If the target department does not exist.
            ConflictError: If an agent with the new name already exists.
        """
        async with _org_lock:
            agents = await self._read_agents()
            existing = self._find_agent(agents, name)
            if existing is None:
                msg = f"Agent {name!r} not found"
                raise NotFoundError(msg)

            updates = await self._validate_agent_update(name, data, agents)

            updated = existing.model_copy(update=updates, deep=True)
            new_agents = tuple(
                updated if a.name.lower() == name.lower() else a for a in agents
            )
            await self._write_agents(new_agents)

        logger.info(
            API_AGENT_UPDATED,
            agent=name,
            updated_fields=list(updates.keys()),
        )
        return updated

    async def delete_agent(self, name: str) -> None:
        """Delete an agent from the org config.

        Args:
            name: Agent name to delete.

        Raises:
            NotFoundError: If the agent does not exist.
            ConflictError: If the agent is the CEO (c_suite level).
        """
        async with _org_lock:
            agents = await self._read_agents()
            existing = self._find_agent(agents, name)
            if existing is None:
                msg = f"Agent {name!r} not found"
                raise NotFoundError(msg)

            if (
                existing.level == SeniorityLevel.C_SUITE
                and existing.role.lower() == "ceo"
            ):
                msg = (
                    f"Cannot delete c-suite agent {name!r} -- reassign or demote first"
                )
                raise ConflictError(msg)

            new_agents = tuple(a for a in agents if a.name.lower() != name.lower())
            await self._write_agents(new_agents)

        logger.info(API_AGENT_DELETED, agent=name)

    async def reorder_agents(
        self,
        dept_name: str,
        data: ReorderAgentsRequest,
    ) -> tuple[AgentConfig, ...]:
        """Reorder agents within a department.

        Args:
            dept_name: Department name.
            data: Ordered list of agent names.

        Returns:
            The reordered agents belonging to the department.

        Raises:
            NotFoundError: If the department does not exist.
            ApiValidationError: If names are not an exact permutation.
        """
        async with _org_lock:
            departments = await self._read_departments()
            if not self._find_department(departments, dept_name):
                msg = f"Department {dept_name!r} not found"
                logger.warning(API_RESOURCE_NOT_FOUND, reason=msg, department=dept_name)
                raise NotFoundError(msg)

            agents = await self._read_agents()
            dept_agents = tuple(
                a for a in agents if a.department.lower() == dept_name.lower()
            )
            current_names = tuple(a.name for a in dept_agents)
            self._validate_permutation(
                current_names,
                data.agent_names,
                "agent",
            )

            agent_by_lower = {a.name.lower(): a for a in dept_agents}
            reordered_dept = tuple(agent_by_lower[n.lower()] for n in data.agent_names)

            # Rebuild the full agent list preserving non-dept agent order.
            # Insert reordered dept agents at the position of the first
            # dept agent in the original list.
            new_agents: list[AgentConfig] = []
            dept_inserted = False
            dept_lower = dept_name.lower()
            for a in agents:
                if a.department.lower() == dept_lower:
                    if not dept_inserted:
                        new_agents.extend(reordered_dept)
                        dept_inserted = True
                else:
                    new_agents.append(a)
            if not dept_inserted:
                new_agents.extend(reordered_dept)

            await self._write_agents(tuple(new_agents))

        logger.info(
            API_AGENTS_REORDERED,
            department=dept_name,
            order=[a.name for a in reordered_dept],
        )
        return reordered_dept
