"""Company configuration controller."""

import asyncio
from typing import Any

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_read_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.company import Department  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.settings import SETTINGS_FETCH_FAILED

logger = get_logger(__name__)


class CompanyController(Controller):
    """Read-only access to company configuration."""

    path = "/company"
    tags = ("company",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def get_company(
        self,
        state: State,
    ) -> ApiResponse[dict[str, Any]]:
        """Return a curated subset of company configuration.

        Returns an explicit field dict to control the response
        shape and avoid exposing internal configuration details.

        Args:
            state: Application state.

        Returns:
            Company configuration envelope.
        """
        app_state: AppState = state.app_state
        resolver = app_state.config_resolver
        try:
            async with asyncio.TaskGroup() as tg:
                t_name = tg.create_task(resolver.get_str("company", "company_name"))
                t_agents = tg.create_task(resolver.get_agents())
                t_depts = tg.create_task(resolver.get_departments())
        except ExceptionGroup as eg:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace="company",
                key="_composed",
                error_count=len(eg.exceptions),
                exc_info=True,
            )
            raise eg.exceptions[0] from eg
        data: dict[str, Any] = {
            "company_name": t_name.result(),
            "agents": [a.model_dump(mode="json") for a in t_agents.result()],
            "departments": [d.model_dump(mode="json") for d in t_depts.result()],
        }
        return ApiResponse(data=data)

    @get("/departments")
    async def list_departments(
        self,
        state: State,
    ) -> ApiResponse[tuple[Department, ...]]:
        """List departments (convenience alias).

        Args:
            state: Application state.

        Returns:
            Departments envelope.
        """
        app_state: AppState = state.app_state
        departments = await app_state.config_resolver.get_departments()
        return ApiResponse(data=departments)
