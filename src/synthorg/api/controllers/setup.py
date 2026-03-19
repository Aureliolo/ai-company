"""First-run setup controller -- status, templates, company, agent, complete."""

import asyncio
import json
from typing import TYPE_CHECKING, Any, Literal, Self

from litestar import Controller, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.status_codes import HTTP_201_CREATED
from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.api.auth.config import AuthConfig
from synthorg.api.dto import ApiResponse
from synthorg.api.errors import ApiValidationError, ConflictError, NotFoundError
from synthorg.api.guards import HumanRole, require_read_access, require_write_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.enums import SeniorityLevel
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.setup import (
    SETUP_AGENT_CREATED,
    SETUP_AGENTS_CORRUPTED,
    SETUP_AGENTS_READ_FALLBACK,
    SETUP_ALREADY_COMPLETE,
    SETUP_COMPANY_CREATED,
    SETUP_COMPLETED,
    SETUP_MODEL_NOT_FOUND,
    SETUP_NO_AGENTS,
    SETUP_NO_COMPANY,
    SETUP_NO_PROVIDERS,
    SETUP_PROVIDER_NOT_FOUND,
    SETUP_STATUS_CHECKED,
    SETUP_STATUS_SETTINGS_DEFAULT_USED,
    SETUP_STATUS_SETTINGS_UNAVAILABLE,
    SETUP_TEMPLATE_INVALID,
    SETUP_TEMPLATE_NOT_FOUND,
    SETUP_TEMPLATES_LISTED,
)
from synthorg.persistence.errors import QueryError
from synthorg.settings.errors import SettingNotFoundError

if TYPE_CHECKING:
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)

# Derive from AuthConfig default to prevent silent divergence.
_DEFAULT_MIN_PASSWORD_LENGTH: int = AuthConfig.model_fields[
    "min_password_length"
].default

# Serializes read-modify-write on the agents settings blob.
_AGENT_LOCK = asyncio.Lock()


# ── Request / Response DTOs ──────────────────────────────────


class SetupStatusResponse(BaseModel):
    """First-run setup status.

    Attributes:
        needs_admin: True if no user with the CEO role exists yet.
        needs_setup: True if setup has not been completed.
        has_providers: True if at least one provider is configured.
        min_password_length: Backend-configured minimum password length.
    """

    model_config = ConfigDict(frozen=True)

    needs_admin: bool
    needs_setup: bool
    has_providers: bool
    min_password_length: int = Field(ge=8)


class TemplateInfoResponse(BaseModel):
    """Summary of an available company template.

    Attributes:
        name: Template identifier.
        display_name: Human-readable name.
        description: Short description.
        source: Where the template was found (builtin or user).
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr
    display_name: NotBlankStr
    description: str
    source: Literal["builtin", "user"]


class SetupCompanyRequest(BaseModel):
    """Company creation payload for first-run setup.

    Attributes:
        company_name: Company display name.
        template_name: Optional template to apply (None = blank company).
    """

    model_config = ConfigDict(frozen=True)

    company_name: NotBlankStr = Field(max_length=200)
    template_name: NotBlankStr | None = Field(default=None, max_length=100)


class SetupCompanyResponse(BaseModel):
    """Company creation result.

    Attributes:
        company_name: The company name that was set.
        template_applied: Name of the template that was applied, if any.
        department_count: Number of departments created.
    """

    model_config = ConfigDict(frozen=True)

    company_name: NotBlankStr
    template_applied: NotBlankStr | None
    department_count: int = Field(ge=0)


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
    personality_preset: NotBlankStr = Field(default="pragmatic_builder", max_length=100)
    model_provider: NotBlankStr = Field(max_length=100)
    model_id: NotBlankStr = Field(max_length=200)
    department: NotBlankStr = Field(default="engineering", max_length=100)
    budget_limit_monthly: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _validate_preset_exists(self) -> Self:
        """Validate that the personality preset name exists in the registry."""
        from synthorg.templates.presets import PERSONALITY_PRESETS  # noqa: PLC0415

        key = self.personality_preset.strip().lower()
        if key not in PERSONALITY_PRESETS:
            available = sorted(PERSONALITY_PRESETS)
            msg = (
                f"Unknown personality preset {self.personality_preset!r}. "
                f"Available: {available}"
            )
            raise ValueError(msg)
        # Store the canonical (normalized) key so downstream code sees a
        # consistent value that matches what PERSONALITY_PRESETS expects.
        object.__setattr__(self, "personality_preset", key)
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

    name: NotBlankStr
    role: NotBlankStr
    department: NotBlankStr
    model_provider: NotBlankStr
    model_id: NotBlankStr


class SetupCompleteResponse(BaseModel):
    """Setup completion result.

    Attributes:
        setup_complete: Always True on success.
    """

    model_config = ConfigDict(frozen=True)

    setup_complete: bool


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
        All other setup endpoints require authentication via guards.

        Args:
            state: Application state.

        Returns:
            Setup status envelope.
        """
        app_state: AppState = state.app_state
        persistence = app_state.persistence

        try:
            admin_count = await persistence.users.count_by_role(HumanRole.CEO)
        except QueryError:
            logger.warning(
                SETUP_STATUS_SETTINGS_UNAVAILABLE,
                exc_info=True,
            )
            admin_count = 0
        needs_admin = admin_count == 0

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

        min_password_length = _DEFAULT_MIN_PASSWORD_LENGTH
        raw_pw_value: str | None = None
        try:
            pw_entry = await settings_svc.get_entry("api", "min_password_length")
            raw_pw_value = pw_entry.value
            parsed = int(raw_pw_value)
            min_password_length = max(parsed, _DEFAULT_MIN_PASSWORD_LENGTH)
        except MemoryError, RecursionError:
            raise
        except SettingNotFoundError:
            logger.debug(
                SETUP_STATUS_SETTINGS_DEFAULT_USED,
                setting="min_password_length",
            )
        except ValueError:
            logger.warning(
                SETUP_STATUS_SETTINGS_UNAVAILABLE,
                setting="min_password_length",
                reason="non_integer_value",
                raw=raw_pw_value,
            )
        except Exception:
            logger.warning(
                SETUP_STATUS_SETTINGS_UNAVAILABLE,
                setting="min_password_length",
                exc_info=True,
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
                min_password_length=min_password_length,
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
        to create department structure. Calling this endpoint again
        overwrites the previously set company name and departments.

        Args:
            data: Company creation payload.
            state: Application state.

        Returns:
            Company creation result envelope.

        Raises:
            ConflictError: If setup has already been completed.
        """
        app_state: AppState = state.app_state
        settings_svc = app_state.settings_service
        await _check_setup_not_complete(settings_svc)

        # Validate template first (may raise) before persisting anything.
        department_count = 0
        template_applied: str | None = None
        departments_json = ""

        if data.template_name is not None:
            template_applied = data.template_name
            departments_json = _extract_template_departments(data.template_name)
            if departments_json:
                department_count = len(json.loads(departments_json))

        # Persist company name and departments atomically after validation.
        await settings_svc.set("company", "company_name", data.company_name)
        # Always write departments -- clears stale data from previous runs.
        await settings_svc.set(
            "company",
            "departments",
            departments_json or "[]",
        )

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
        """Create an agent during first-run setup.

        Validates the provider and model, builds an agent configuration,
        and appends it to the company settings.

        Args:
            data: Agent creation payload.
            state: Application state.

        Returns:
            Agent creation result envelope.

        Raises:
            ConflictError: If setup has already been completed.
            NotFoundError: If the provider does not exist.
            ApiValidationError: If the model is not in the provider.
        """
        app_state: AppState = state.app_state
        settings_svc = app_state.settings_service
        await _check_setup_not_complete(settings_svc)

        providers = await app_state.provider_management.list_providers()
        _validate_provider_and_model(providers, data)
        agent_config = _build_agent_config(data)

        # Serialize the read-modify-write so concurrent requests
        # cannot overwrite each other's appended agents.
        async with _AGENT_LOCK:
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
    ) -> ApiResponse[SetupCompleteResponse]:
        """Mark first-run setup as complete.

        Validates that a company, at least one agent, and at least one
        provider are configured before allowing completion.

        Args:
            state: Application state.

        Returns:
            Success envelope.

        Raises:
            ConflictError: If setup has already been completed.
            ApiValidationError: If company, agents, or providers are missing.
        """
        app_state: AppState = state.app_state
        settings_svc = app_state.settings_service
        await _check_setup_not_complete(settings_svc)

        # Verify company has been created.
        has_company = False
        try:
            entry = await settings_svc.get_entry("company", "company_name")
            has_company = bool(entry.value and entry.value.strip())
        except MemoryError, RecursionError:
            raise
        except SettingNotFoundError:
            pass
        if not has_company:
            msg = "A company must be created before completing setup"
            logger.warning(SETUP_NO_COMPANY)
            raise ApiValidationError(msg)

        # Verify at least one agent has been created.
        existing_agents = await _get_existing_agents(settings_svc)
        if not existing_agents:
            msg = "At least one agent must be created before completing setup"
            logger.warning(SETUP_NO_AGENTS)
            raise ApiValidationError(msg)

        # Verify at least one provider is configured.
        if not app_state.has_provider_registry or len(app_state.provider_registry) == 0:
            msg = "At least one provider must be configured before completing setup"
            logger.warning(SETUP_NO_PROVIDERS)
            raise ApiValidationError(msg)

        await settings_svc.set("api", "setup_complete", "true")

        logger.info(SETUP_COMPLETED)

        return ApiResponse(data=SetupCompleteResponse(setup_complete=True))


# ── Helpers ──────────────────────────────────────────────────


async def _check_setup_not_complete(settings_svc: SettingsService) -> None:
    """Raise ConflictError if setup has already been completed.

    Args:
        settings_svc: Settings service instance.

    Raises:
        ConflictError: If the setup_complete flag is already true.
    """
    is_complete = await _is_setup_complete(settings_svc)
    if is_complete:
        logger.warning(SETUP_ALREADY_COMPLETE)
        msg = "Setup has already been completed"
        raise ConflictError(msg)


async def _is_setup_complete(settings_svc: SettingsService) -> bool:
    """Check whether setup has been completed.

    Args:
        settings_svc: Settings service instance.

    Returns:
        True if setup_complete is "true", False otherwise or on error.
    """
    try:
        entry = await settings_svc.get_entry("api", "setup_complete")
    except MemoryError, RecursionError:
        raise
    except SettingNotFoundError:
        # Key does not exist yet -- setup has not been completed.
        return False
    else:
        return entry.value == "true"


def _validate_provider_and_model(
    providers: dict[str, Any],
    data: SetupAgentRequest,
) -> None:
    """Validate that the provider and model exist in the given providers dict.

    Args:
        providers: Provider name -> config mapping from management service.
        data: Agent creation payload.

    Raises:
        NotFoundError: If the provider does not exist.
        ApiValidationError: If the model is not found in the provider.
    """
    if data.model_provider not in providers:
        msg = f"Provider {data.model_provider!r} not found"
        logger.warning(
            SETUP_PROVIDER_NOT_FOUND,
            provider=data.model_provider,
        )
        raise NotFoundError(msg)

    provider_config = providers[data.model_provider]
    model_ids = {m.id for m in provider_config.models}
    if data.model_id not in model_ids:
        msg = f"Model {data.model_id!r} not found in provider {data.model_provider!r}"
        logger.warning(
            SETUP_MODEL_NOT_FOUND,
            provider=data.model_provider,
            model=data.model_id,
        )
        raise ApiValidationError(msg)


def _build_agent_config(data: SetupAgentRequest) -> dict[str, Any]:
    """Build an agent config dict for settings persistence.

    Args:
        data: Validated agent creation payload.

    Returns:
        Agent configuration dict suitable for JSON serialization.
    """
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
    return agent_config


def _extract_template_departments(template_name: str) -> str:
    """Load a template and extract its departments as a JSON string.

    Args:
        template_name: Template name to load.

    Returns:
        JSON array of department dicts, or empty string if template
        has no departments.

    Raises:
        NotFoundError: If the template does not exist.
        ApiValidationError: If the template fails to render or validate.
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
        logger.warning(
            SETUP_TEMPLATE_NOT_FOUND,
            template=template_name,
        )
        raise NotFoundError(msg) from exc
    except (TemplateRenderError, TemplateValidationError) as exc:
        msg = f"Template {template_name!r} is invalid: {exc}"
        logger.warning(
            SETUP_TEMPLATE_INVALID,
            template=template_name,
            error=str(exc),
        )
        raise ApiValidationError(msg) from exc

    departments = loaded.template.departments
    if not departments:
        return ""

    dept_list: list[dict[str, Any]] = []
    for d in departments:
        entry: dict[str, Any] = {"name": d.name, "budget_percent": d.budget_percent}
        dept_list.append(entry)
    return json.dumps(dept_list) if dept_list else ""


async def _get_existing_agents(
    settings_svc: SettingsService,
) -> list[dict[str, Any]]:
    """Read the current agents list from settings.

    Only the "entry not found" case yields an empty list. JSON parse
    errors and non-list values are surfaced so ``create_agent`` does
    not silently overwrite corrupted data.

    Args:
        settings_svc: Settings service instance.

    Returns:
        List of agent config dicts (empty if entry is absent or None).

    Raises:
        ApiValidationError: If the stored value is not valid JSON or
            not a JSON array.
    """
    try:
        entry = await settings_svc.get_entry("company", "agents")
    except MemoryError, RecursionError:
        raise
    except SettingNotFoundError:
        logger.debug(SETUP_AGENTS_READ_FALLBACK, reason="entry_not_found")
        return []

    try:
        parsed = json.loads(entry.value)
    except json.JSONDecodeError as exc:
        logger.warning(
            SETUP_AGENTS_CORRUPTED,
            reason="invalid_json",
            exc_info=True,
        )
        msg = "Stored agents list is not valid JSON"
        raise ApiValidationError(msg) from exc

    if not isinstance(parsed, list):
        logger.warning(
            SETUP_AGENTS_CORRUPTED,
            reason="non_list_json",
            raw_type=type(parsed).__name__,
        )
        msg = f"Stored agents list is {type(parsed).__name__}, expected list"
        raise ApiValidationError(msg)

    return parsed
