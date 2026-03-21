"""First-run setup controller -- status, templates, company, agent, complete."""

import asyncio
import json
from typing import TYPE_CHECKING, Any

from litestar import Controller, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.status_codes import HTTP_201_CREATED

from synthorg.api.auth.config import AuthConfig
from synthorg.api.controllers.setup_models import (
    SetupAgentRequest,
    SetupAgentResponse,
    SetupCompanyRequest,
    SetupCompanyResponse,
    SetupCompleteResponse,
    SetupStatusResponse,
    TemplateInfoResponse,
)
from synthorg.api.dto import ApiResponse
from synthorg.api.errors import ApiValidationError, ConflictError, NotFoundError
from synthorg.api.guards import HumanRole, require_read_access, require_write_access
from synthorg.api.state import AppState  # noqa: TC001
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
from synthorg.settings.enums import SettingSource
from synthorg.settings.errors import SettingNotFoundError

if TYPE_CHECKING:
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)

# Derive from AuthConfig default to prevent silent divergence.
_DEFAULT_MIN_PASSWORD_LENGTH: int = AuthConfig.model_fields[
    "min_password_length"
].default

# Module-level lock: one per worker process.  Safe under asyncio single-loop
# model.  Serializes read-modify-write on the agents settings blob.
_AGENT_LOCK = asyncio.Lock()


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
        settings_svc = app_state.settings_service

        needs_admin = await _check_needs_admin(app_state.persistence)
        needs_setup = await _check_needs_setup(settings_svc)
        has_providers = (
            app_state.has_provider_registry and len(app_state.provider_registry) > 0
        )
        async with asyncio.TaskGroup() as tg:
            co_task = tg.create_task(_check_has_company(settings_svc))
            ag_task = tg.create_task(_check_has_agents(settings_svc))
            pw_task = tg.create_task(
                _resolve_min_password_length(settings_svc),
            )
        has_company = co_task.result()
        has_agents = ag_task.result()
        min_password_length = pw_task.result()

        logger.debug(
            SETUP_STATUS_CHECKED,
            needs_admin=needs_admin,
            needs_setup=needs_setup,
            has_providers=has_providers,
            has_company=has_company,
            has_agents=has_agents,
        )
        return ApiResponse(
            data=SetupStatusResponse(
                needs_admin=needs_admin,
                needs_setup=needs_setup,
                has_providers=has_providers,
                has_company=has_company,
                has_agents=has_agents,
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

        Persists company name, description, and optionally applies a
        template.  Re-calling overwrites previous values.

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

        departments_json, department_count, template_applied = _resolve_template(
            data.template_name
        )
        description = _normalize_description(data.description)

        await _persist_company_settings(
            settings_svc,
            data.company_name,
            description,
            departments_json,
        )

        logger.info(
            SETUP_COMPANY_CREATED,
            company_name=data.company_name,
            description_present=description is not None,
            description_length=len(description) if description else 0,
            template=template_applied,
            department_count=department_count,
        )

        return ApiResponse(
            data=SetupCompanyResponse(
                company_name=data.company_name,
                description=description,
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

        Validates provider/model, builds agent config, and appends
        to company settings.

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

        # Verify company has been created (strict: propagate unexpected errors).
        has_company = await _check_has_company(settings_svc, strict=True)
        if not has_company:
            msg = "A company must be created before completing setup"
            logger.warning(SETUP_NO_COMPANY)
            raise ApiValidationError(msg)

        # Verify at least one agent has been created (strict: propagate errors).
        has_agents = await _check_has_agents(settings_svc, strict=True)
        if not has_agents:
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


async def _check_needs_admin(persistence: Any) -> bool:
    """Return True if no CEO-role user exists (fail-open on error)."""
    count: int | None = None
    try:
        count = await persistence.users.count_by_role(HumanRole.CEO)
    except QueryError:
        logger.warning(
            SETUP_STATUS_SETTINGS_UNAVAILABLE,
            context="admin_count",
            exc_info=True,
        )
        return True
    return count == 0 if count is not None else True


async def _check_needs_setup(settings_svc: SettingsService) -> bool:
    """Return True if setup is still needed (fail-open on error)."""
    try:
        entry = await settings_svc.get_entry("api", "setup_complete")
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            SETUP_STATUS_SETTINGS_UNAVAILABLE,
            exc_info=True,
        )
        return True
    else:
        return entry.value != "true"


async def _check_has_company(
    settings_svc: SettingsService,
    *,
    strict: bool = False,
) -> bool:
    """Check whether a company name has been explicitly created.

    Only values persisted to the database (i.e. saved by the user
    through the setup wizard) count.  YAML/code defaults like
    ``"SynthOrg"`` must not cause a fresh setup to report the
    company as already existing.

    Args:
        settings_svc: Settings service instance.
        strict: When True, propagate unexpected exceptions instead of
            returning False (use for validation gates, not status checks).

    Returns:
        True if a user-created company name exists, False otherwise.
    """
    try:
        entry = await settings_svc.get_entry("company", "company_name")
        if entry.source != SettingSource.DATABASE:
            logger.debug(
                SETUP_STATUS_SETTINGS_DEFAULT_USED,
                setting="company_name",
                source=entry.source,
            )
            return False
        return bool(entry.value and entry.value.strip())
    except MemoryError, RecursionError:
        raise
    except SettingNotFoundError:
        logger.debug(
            SETUP_STATUS_SETTINGS_DEFAULT_USED,
            setting="company_name",
        )
        return False
    except Exception:
        logger.warning(
            SETUP_STATUS_SETTINGS_UNAVAILABLE,
            setting="company_name",
            exc_info=True,
        )
        if strict:
            raise
        return False


async def _check_has_agents(
    settings_svc: SettingsService,
    *,
    strict: bool = False,
) -> bool:
    """Check whether any agents have been explicitly created.

    Only values persisted to the database (i.e. saved by the user
    through the setup wizard) count.  YAML/code defaults must not
    cause a fresh setup to report agents as already existing.

    Args:
        settings_svc: Settings service instance.
        strict: When True, propagate parsing/validation exceptions
            instead of returning False (use for validation gates).

    Returns:
        True if user-created agents exist, False otherwise.
    """
    try:
        entry = await settings_svc.get_entry("company", "agents")
    except MemoryError, RecursionError:
        raise
    except SettingNotFoundError:
        logger.debug(
            SETUP_STATUS_SETTINGS_DEFAULT_USED,
            setting="agents",
        )
        return False
    except Exception:
        logger.warning(
            SETUP_STATUS_SETTINGS_UNAVAILABLE,
            setting="agents",
            exc_info=True,
        )
        if strict:
            raise
        return False

    if entry.source != SettingSource.DATABASE:
        logger.debug(
            SETUP_STATUS_SETTINGS_DEFAULT_USED,
            setting="agents",
            source=entry.source,
        )
        return False
    if not entry.value:
        return False
    return _validate_agents_value(entry.value, strict=strict)


def _validate_agents_value(raw: str, *, strict: bool) -> bool:
    """Parse *raw* as JSON and return True if it is a non-empty list.

    When *strict* is True, raises ``ApiValidationError`` on corrupted
    data instead of returning False.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            SETUP_AGENTS_CORRUPTED,
            reason="invalid_json",
            exc_info=True,
        )
        if strict:
            msg = "Stored agents list is not valid JSON"
            raise ApiValidationError(msg) from None
        return False

    if not isinstance(parsed, list):
        logger.warning(
            SETUP_AGENTS_CORRUPTED,
            reason="non_list_json",
            raw_type=type(parsed).__name__,
        )
        if strict:
            msg = f"Stored agents list is {type(parsed).__name__}, expected list"
            raise ApiValidationError(msg)
        return False

    return bool(parsed)


async def _resolve_min_password_length(
    settings_svc: SettingsService,
) -> int:
    """Resolve the minimum password length from settings.

    Falls back to the ``AuthConfig`` default when the setting is absent,
    non-integer, or otherwise unreadable.

    Args:
        settings_svc: Settings service instance.

    Returns:
        Resolved minimum password length (never below the default).
    """
    raw_pw_value: str | None = None
    try:
        pw_entry = await settings_svc.get_entry("api", "min_password_length")
        raw_pw_value = pw_entry.value
        parsed = int(raw_pw_value)
        return max(parsed, _DEFAULT_MIN_PASSWORD_LENGTH)
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
    return _DEFAULT_MIN_PASSWORD_LENGTH


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


def _normalize_description(raw: str | None) -> str | None:
    """Strip whitespace from description, treating blank as None."""
    return (raw.strip() or None) if raw else None


def _resolve_template(
    template_name: str | None,
) -> tuple[str, int, str | None]:
    """Validate template and extract department data.

    Returns:
        Tuple of (departments_json, department_count, template_applied).
    """
    if template_name is None:
        return ("", 0, None)

    departments_json = _extract_template_departments(template_name)
    department_count = len(json.loads(departments_json)) if departments_json else 0
    return (departments_json, department_count, template_name)


async def _persist_company_settings(
    settings_svc: SettingsService,
    company_name: str,
    description: str | None,
    departments_json: str,
) -> None:
    """Write company name, description, and departments to settings.

    Always writes all three keys to clear stale data from previous runs.
    Stores ``""`` when description is None (settings values are strings);
    consumers should treat ``""`` as absent.
    """
    await settings_svc.set("company", "company_name", company_name)
    await settings_svc.set("company", "description", description or "")
    await settings_svc.set(
        "company",
        "departments",
        departments_json or "[]",
    )


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

    dept_list = [
        {"name": d.name, "budget_percent": d.budget_percent} for d in departments
    ]
    return json.dumps(dept_list)


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

    if entry.source != SettingSource.DATABASE:
        logger.debug(
            SETUP_AGENTS_READ_FALLBACK,
            reason="non_database_source",
            source=entry.source,
        )
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
