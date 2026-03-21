"""First-run setup controller.

Status, templates, company, agents, model update, complete.
"""

import asyncio
import json
from typing import TYPE_CHECKING, Any, NamedTuple

from litestar import Controller, get, post, put
from litestar.datastructures import State  # noqa: TC002
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED

from synthorg.api.auth.config import AuthConfig
from synthorg.api.controllers.setup_agents import (
    agent_dict_to_summary,
    agents_to_summaries,
    build_agent_config,
    departments_to_json,
    expand_template_agents,
    get_existing_agents,
    match_and_assign_models,
    normalize_description,
    validate_agents_value,
    validate_model_assignment,
    validate_provider_and_model,
)
from synthorg.api.controllers.setup_models import (
    SetupAgentRequest,
    SetupAgentResponse,
    SetupAgentsListResponse,
    SetupAgentSummary,
    SetupCompanyRequest,
    SetupCompanyResponse,
    SetupCompleteResponse,
    SetupStatusResponse,
    TemplateInfoResponse,
    UpdateAgentModelRequest,
)
from synthorg.api.dto import ApiResponse
from synthorg.api.errors import ApiValidationError, ConflictError, NotFoundError
from synthorg.api.guards import HumanRole, require_read_access, require_write_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.setup import (
    SETUP_AGENT_CREATED,
    SETUP_AGENT_INDEX_OUT_OF_RANGE,
    SETUP_AGENT_MODEL_UPDATED,
    SETUP_AGENTS_AUTO_CREATED,
    SETUP_AGENTS_LISTED,
    SETUP_ALREADY_COMPLETE,
    SETUP_COMPANY_CREATED,
    SETUP_COMPLETE_CHECK_ERROR,
    SETUP_COMPLETED,
    SETUP_NO_AGENTS,
    SETUP_NO_COMPANY,
    SETUP_NO_PROVIDERS,
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
    from synthorg.templates.loader import LoadedTemplate
    from synthorg.templates.schema import CompanyTemplate

logger = get_logger(__name__)

# Derive from AuthConfig default to prevent silent divergence.
_DEFAULT_MIN_PASSWORD_LENGTH: int = AuthConfig.model_fields[
    "min_password_length"
].default

# Module-level lock: serializes read-modify-write on agents settings.
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

        Persists company name, description, departments, and -- when a
        template is selected -- auto-creates all template agents with
        model assignments matched to the configured provider(s).

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

        template_result = _resolve_template(data.template_name)
        departments_json = template_result.departments_json
        department_count = template_result.department_count
        template_applied = template_result.template_applied
        description = normalize_description(data.description)

        await _persist_company_settings(
            settings_svc,
            data.company_name,
            description,
            departments_json,
        )

        agent_summaries: tuple[SetupAgentSummary, ...] = ()
        if template_result.template is not None:
            agent_summaries = await _auto_create_template_agents(
                template_result.template,
                app_state,
                settings_svc,
            )
            logger.info(
                SETUP_AGENTS_AUTO_CREATED,
                count=len(agent_summaries),
                template=template_applied,
            )
        else:
            # Blank path: clear any agents persisted by a previous
            # template selection so GET /setup/agents returns empty.
            await settings_svc.set("company", "agents", "[]")

        logger.info(
            SETUP_COMPANY_CREATED,
            company_name=data.company_name,
            description_present=description is not None,
            description_length=len(description) if description else 0,
            template=template_applied,
            department_count=department_count,
            agent_count=len(agent_summaries),
        )

        return ApiResponse(
            data=SetupCompanyResponse(
                company_name=data.company_name,
                description=description,
                template_applied=template_applied,
                department_count=department_count,
                agents=agent_summaries,
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

        Used for the "Start Blank" path where no template is selected
        and agents are added manually from the Review Org step.

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
        validate_provider_and_model(providers, data)
        agent_config = build_agent_config(data)

        async with _AGENT_LOCK:
            existing_agents = await get_existing_agents(settings_svc)
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

    @get(
        "/agents",
        guards=[require_read_access],
    )
    async def list_agents(
        self,
        state: State,
    ) -> ApiResponse[SetupAgentsListResponse]:
        """List agents currently configured during setup.

        Used by the Review Org step to display the current org and
        allow model reassignment.

        Args:
            state: Application state.

        Returns:
            Agents list envelope.
        """
        app_state: AppState = state.app_state
        settings_svc = app_state.settings_service

        agents = await get_existing_agents(settings_svc)
        summaries = agents_to_summaries(agents)

        logger.debug(SETUP_AGENTS_LISTED, count=len(summaries))
        return ApiResponse(
            data=SetupAgentsListResponse(agents=summaries),
        )

    @put(
        "/agents/{agent_index:int}/model",
        status_code=HTTP_200_OK,
        guards=[require_write_access],
    )
    async def update_agent_model(
        self,
        agent_index: int,
        data: UpdateAgentModelRequest,
        state: State,
    ) -> ApiResponse[SetupAgentSummary]:
        """Update a single agent's model assignment during setup.

        Args:
            agent_index: Zero-based index of the agent to update.
            data: New model assignment.
            state: Application state.

        Returns:
            Updated agent summary.

        Raises:
            ConflictError: If setup has already been completed.
            NotFoundError: If the agent index is out of range.
            ApiValidationError: If the provider/model is invalid.
        """
        app_state: AppState = state.app_state
        settings_svc = app_state.settings_service
        await _check_setup_not_complete(settings_svc)

        # Validate provider/model before acquiring the lock.
        providers = await app_state.provider_management.list_providers()
        validate_model_assignment(providers, data)

        async with _AGENT_LOCK:
            agents = await get_existing_agents(settings_svc)
            if agent_index < 0 or agent_index >= len(agents):
                if not agents:
                    msg = (
                        f"Agent index {agent_index} out of range (no agents configured)"
                    )
                else:
                    msg = (
                        f"Agent index {agent_index} out of range (0-{len(agents) - 1})"
                    )
                logger.warning(
                    SETUP_AGENT_INDEX_OUT_OF_RANGE,
                    agent_index=agent_index,
                    agent_count=len(agents),
                )
                raise NotFoundError(msg)

            updated_agent = {
                **agents[agent_index],
                "model": {
                    "provider": data.model_provider,
                    "model_id": data.model_id,
                },
            }
            agents = [
                *agents[:agent_index],
                updated_agent,
                *agents[agent_index + 1 :],
            ]
            await settings_svc.set(
                "company",
                "agents",
                json.dumps(agents),
            )

        logger.info(
            SETUP_AGENT_MODEL_UPDATED,
            agent_index=agent_index,
            provider=data.model_provider,
            model=data.model_id,
        )

        return ApiResponse(
            data=agent_dict_to_summary(agents[agent_index]),
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
    return validate_agents_value(entry.value, strict=strict)


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
    """Raise ConflictError if setup has already been completed."""
    is_complete = await _is_setup_complete(settings_svc)
    if is_complete:
        logger.warning(SETUP_ALREADY_COMPLETE)
        msg = "Setup has already been completed"
        raise ConflictError(msg)


async def _auto_create_template_agents(
    template: CompanyTemplate,
    app_state: AppState,
    settings_svc: SettingsService,
) -> tuple[SetupAgentSummary, ...]:
    """Expand template agents, match models, persist, and return summaries."""
    agents = expand_template_agents(template)
    providers = await app_state.provider_management.list_providers()
    agents = match_and_assign_models(agents, providers)

    async with _AGENT_LOCK:
        await settings_svc.set(
            "company",
            "agents",
            json.dumps(agents),
        )

    return agents_to_summaries(agents)


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
    except Exception:
        logger.error(
            SETUP_COMPLETE_CHECK_ERROR,
            exc_info=True,
        )
        raise
    else:
        return entry.value == "true"


class _TemplateResult(NamedTuple):
    departments_json: str
    department_count: int
    template_applied: str | None
    template: CompanyTemplate | None


def _resolve_template(template_name: str | None) -> _TemplateResult:
    """Validate template and extract department data + template object."""
    if template_name is None:
        return _TemplateResult("", 0, None, None)

    loaded = _load_template_safe(template_name)
    departments_json = departments_to_json(loaded.template.departments)
    return _TemplateResult(
        departments_json,
        len(loaded.template.departments),
        template_name,
        loaded.template,
    )


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


def _load_template_safe(template_name: str) -> LoadedTemplate:
    """Load a template by name with API-friendly error handling.

    Args:
        template_name: Template name to load.

    Returns:
        ``LoadedTemplate`` instance.

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
        return load_template(template_name)
    except TemplateNotFoundError as exc:
        msg = f"Template {template_name!r} not found"
        logger.warning(SETUP_TEMPLATE_NOT_FOUND, template=template_name)
        raise NotFoundError(msg) from exc
    except (TemplateRenderError, TemplateValidationError) as exc:
        msg = f"Template {template_name!r} is invalid: {exc}"
        logger.warning(
            SETUP_TEMPLATE_INVALID,
            template=template_name,
            error=str(exc),
        )
        raise ApiValidationError(msg) from exc
