"""First-run setup controller -- status, templates, company, agent, complete."""

import json
from typing import TYPE_CHECKING, Any, Self

from litestar import Controller, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.status_codes import HTTP_201_CREATED
from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.api.dto import ApiResponse
from synthorg.api.errors import ApiValidationError, NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.enums import SeniorityLevel
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.setup import (
    SETUP_AGENT_CREATED,
    SETUP_AGENTS_READ_FALLBACK,
    SETUP_COMPANY_CREATED,
    SETUP_COMPLETED,
    SETUP_STATUS_CHECKED,
    SETUP_STATUS_SETTINGS_UNAVAILABLE,
    SETUP_TEMPLATES_LISTED,
)

if TYPE_CHECKING:
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)


# ── Request / Response DTOs ──────────────────────────────────


class SetupStatusResponse(BaseModel):
    """First-run setup status.

    Attributes:
        needs_admin: True if no admin user exists yet.
        needs_setup: True if setup has not been completed.
        has_providers: True if at least one provider is configured.
    """

    model_config = ConfigDict(frozen=True)

    needs_admin: bool
    needs_setup: bool
    has_providers: bool


class TemplateInfoResponse(BaseModel):
    """Summary of an available company template.

    Attributes:
        name: Template identifier.
        display_name: Human-readable name.
        description: Short description.
        source: Where the template was found.
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr
    display_name: NotBlankStr
    description: str
    source: str


class SetupCompanyRequest(BaseModel):
    """Company creation payload for first-run setup.

    Attributes:
        company_name: Company display name.
        template_name: Optional template to apply (None = blank company).
    """

    model_config = ConfigDict(frozen=True)

    company_name: NotBlankStr = Field(max_length=200)
    template_name: str | None = Field(default=None, max_length=100)


class SetupCompanyResponse(BaseModel):
    """Company creation result.

    Attributes:
        company_name: The company name that was set.
        template_applied: Name of the template that was applied, if any.
        department_count: Number of departments created.
    """

    model_config = ConfigDict(frozen=True)

    company_name: str
    template_applied: str | None
    department_count: int


class SetupAgentRequest(BaseModel):
    """Agent creation payload for first-run setup.

    Attributes:
        name: Agent display name.
        role: Agent role name.
        level: Seniority level.
        personality_preset: Personality preset name.
        model_provider: Provider name for the agent's model.
        model_id: Model identifier from that provider.
        department: Department to assign the agent to.
        budget_limit_monthly: Optional monthly budget limit in USD.
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr = Field(max_length=200)
    role: NotBlankStr = Field(max_length=100)
    level: SeniorityLevel = Field(default=SeniorityLevel.MID)
    personality_preset: str = Field(default="pragmatic_builder", max_length=100)
    model_provider: NotBlankStr = Field(max_length=100)
    model_id: NotBlankStr = Field(max_length=200)
    department: NotBlankStr = Field(default="engineering", max_length=100)
    budget_limit_monthly: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _validate_preset_exists(self) -> Self:
        """Validate the personality preset name at parse time."""
        from synthorg.templates.presets import PERSONALITY_PRESETS  # noqa: PLC0415

        key = self.personality_preset.strip().lower()
        if key not in PERSONALITY_PRESETS:
            available = sorted(PERSONALITY_PRESETS)
            msg = (
                f"Unknown personality preset {self.personality_preset!r}. "
                f"Available: {available}"
            )
            raise ValueError(msg)
        return self


class SetupAgentResponse(BaseModel):
    """Agent creation result.

    Attributes:
        name: Agent display name.
        role: Agent role.
        department: Assigned department.
        model_provider: LLM provider name.
        model_id: Model identifier.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    role: str
    department: str
    model_provider: str
    model_id: str


# ── Controller ───────────────────────────────────────────────


class SetupController(Controller):
    """First-run setup wizard endpoints."""

    path = "/setup"
    tags = ("setup",)

    @get("/status")
    async def get_status(
        self,
        state: State,
    ) -> ApiResponse[SetupStatusResponse]:
        """Check whether first-run setup is needed.

        This endpoint is unauthenticated so the frontend can determine
        whether to show the setup wizard before any user exists.

        Args:
            state: Application state.

        Returns:
            Setup status envelope.
        """
        app_state: AppState = state.app_state
        persistence = app_state.persistence

        user_count = await persistence.users.count()
        needs_admin = user_count == 0

        settings_svc = app_state.settings_service
        try:
            entry = await settings_svc.get_entry("api", "setup_complete")
            needs_setup = entry.value != "true"
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                SETUP_STATUS_SETTINGS_UNAVAILABLE,
                exc_info=True,
            )
            needs_setup = True

        has_providers = (
            app_state.has_provider_registry and len(app_state.provider_registry) > 0
        )

        logger.debug(
            SETUP_STATUS_CHECKED,
            needs_admin=needs_admin,
            needs_setup=needs_setup,
            has_providers=has_providers,
        )

        return ApiResponse(
            data=SetupStatusResponse(
                needs_admin=needs_admin,
                needs_setup=needs_setup,
                has_providers=has_providers,
            ),
        )

    @get(
        "/templates",
        guards=[require_read_access],
    )
    async def get_templates(
        self,
        state: State,  # noqa: ARG002
    ) -> ApiResponse[tuple[TemplateInfoResponse, ...]]:
        """List available company templates for setup.

        Args:
            state: Application state.

        Returns:
            Template list envelope.
        """
        from synthorg.templates.loader import list_templates  # noqa: PLC0415

        templates = list_templates()
        result = tuple(
            TemplateInfoResponse(
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                source=t.source,
            )
            for t in templates
        )

        logger.debug(SETUP_TEMPLATES_LISTED, count=len(result))
        return ApiResponse(data=result)

    @post(
        "/company",
        status_code=HTTP_201_CREATED,
        guards=[require_write_access],
    )
    async def create_company(
        self,
        data: SetupCompanyRequest,
        state: State,
    ) -> ApiResponse[SetupCompanyResponse]:
        """Create company configuration during first-run setup.

        Persists the company name and optionally applies a template
        to create department structure.

        Args:
            data: Company creation payload.
            state: Application state.

        Returns:
            Company creation result envelope.
        """
        app_state: AppState = state.app_state
        settings_svc = app_state.settings_service

        # Set company name.
        await settings_svc.set("company", "company_name", data.company_name)

        department_count = 0
        template_applied: str | None = None

        if data.template_name is not None:
            template_applied = data.template_name
            departments_json = _extract_template_departments(data.template_name)
            if departments_json:
                await settings_svc.set(
                    "company",
                    "departments",
                    departments_json,
                )
                department_count = len(json.loads(departments_json))

        logger.info(
            SETUP_COMPANY_CREATED,
            company_name=data.company_name,
            template=template_applied,
            department_count=department_count,
        )

        return ApiResponse(
            data=SetupCompanyResponse(
                company_name=data.company_name,
                template_applied=template_applied,
                department_count=department_count,
            ),
        )

    @post(
        "/agent",
        status_code=HTTP_201_CREATED,
        guards=[require_write_access],
    )
    async def create_agent(
        self,
        data: SetupAgentRequest,
        state: State,
    ) -> ApiResponse[SetupAgentResponse]:
        """Create the first agent during first-run setup.

        Builds an agent configuration and persists it to the
        company settings.

        Args:
            data: Agent creation payload.
            state: Application state.

        Returns:
            Agent creation result envelope.
        """
        app_state: AppState = state.app_state
        settings_svc = app_state.settings_service

        # Validate provider exists via management service.
        provider_mgmt = app_state.provider_management
        providers = await provider_mgmt.list_providers()
        if data.model_provider not in providers:
            msg = f"Provider {data.model_provider!r} not found"
            raise NotFoundError(msg)

        # Validate model exists in the provider.
        provider_config = providers[data.model_provider]
        model_ids = {m.id for m in provider_config.models}
        if data.model_id not in model_ids:
            msg = (
                f"Model {data.model_id!r} not found in provider {data.model_provider!r}"
            )
            raise ApiValidationError(msg)

        # Build agent config dict (matches config.schema.AgentConfig).
        from synthorg.templates.presets import (  # noqa: PLC0415
            get_personality_preset,
        )

        personality_dict = get_personality_preset(data.personality_preset)
        agent_config: dict[str, Any] = {
            "name": data.name,
            "role": data.role,
            "department": data.department,
            "level": data.level.value,
            "personality": personality_dict,
            "model": {
                "provider": data.model_provider,
                "model_id": data.model_id,
            },
        }
        if data.budget_limit_monthly is not None:
            agent_config["budget_limit_monthly"] = data.budget_limit_monthly

        # Create new list with the agent appended (immutability convention).
        existing_agents = await _get_existing_agents(settings_svc)
        updated_agents = [*existing_agents, agent_config]
        await settings_svc.set(
            "company",
            "agents",
            json.dumps(updated_agents),
        )

        logger.info(
            SETUP_AGENT_CREATED,
            agent_name=data.name,
            role=data.role,
            provider=data.model_provider,
            model=data.model_id,
        )

        return ApiResponse(
            data=SetupAgentResponse(
                name=data.name,
                role=data.role,
                department=data.department,
                model_provider=data.model_provider,
                model_id=data.model_id,
            ),
        )

    @post(
        "/complete",
        guards=[require_write_access],
    )
    async def complete_setup(
        self,
        state: State,
    ) -> ApiResponse[dict[str, bool]]:
        """Mark first-run setup as complete.

        Validates that at least one provider is configured before
        allowing completion.

        Args:
            state: Application state.

        Returns:
            Success envelope.
        """
        app_state: AppState = state.app_state

        if not app_state.has_provider_registry or len(app_state.provider_registry) == 0:
            msg = "At least one provider must be configured before completing setup"
            raise ApiValidationError(msg)

        settings_svc = app_state.settings_service
        await settings_svc.set("api", "setup_complete", "true")

        logger.info(SETUP_COMPLETED)

        return ApiResponse(data={"setup_complete": True})


# ── Helpers ──────────────────────────────────────────────────


def _extract_template_departments(template_name: str) -> str:
    """Load a template and extract its departments as a JSON string.

    Args:
        template_name: Template name to load.

    Returns:
        JSON array of department dicts, or empty string if template
        has no departments.

    Raises:
        NotFoundError: If the template does not exist.
        ApiValidationError: If the template cannot be parsed.
    """
    from synthorg.templates.errors import (  # noqa: PLC0415
        TemplateNotFoundError,
        TemplateRenderError,
        TemplateValidationError,
    )
    from synthorg.templates.loader import load_template  # noqa: PLC0415

    try:
        loaded = load_template(template_name)
    except TemplateNotFoundError as exc:
        msg = f"Template {template_name!r} not found"
        raise NotFoundError(msg) from exc
    except (TemplateRenderError, TemplateValidationError) as exc:
        msg = f"Template {template_name!r} is invalid: {exc}"
        raise ApiValidationError(msg) from exc

    departments = loaded.template.departments
    if not departments:
        return ""

    # Convert TemplateDepartmentConfig objects to JSON-serializable dicts.
    dept_list: list[dict[str, Any]] = []
    for d in departments:
        entry: dict[str, Any] = {"name": getattr(d, "name", "")}
        budget = getattr(d, "budget_percent", 0)
        if budget is not None:
            entry["budget_percent"] = budget
        dept_list.append(entry)
    return json.dumps(dept_list) if dept_list else ""


async def _get_existing_agents(
    settings_svc: SettingsService,
) -> list[dict[str, Any]]:
    """Read the current agents list from settings.

    Args:
        settings_svc: Settings service instance.

    Returns:
        Mutable list of agent config dicts (empty if none set).
    """
    try:
        entry = await settings_svc.get_entry("company", "agents")
        if entry.value is not None:
            parsed = json.loads(entry.value)
            if isinstance(parsed, list):
                return parsed
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.debug(SETUP_AGENTS_READ_FALLBACK, reason="no_existing_agents")
    return []
