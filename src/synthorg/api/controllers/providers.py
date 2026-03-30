"""Provider controller -- CRUD, connection testing, and presets."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from litestar import Controller, delete, get, post, put
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter
from litestar.status_codes import HTTP_204_NO_CONTENT

from synthorg.api.dto import (
    ApiResponse,
    CreateFromPresetRequest,
    CreateProviderRequest,
    DiscoverModelsResponse,
    ProbePresetRequest,
    ProbePresetResponse,
    ProviderResponse,
    TestConnectionResponse,
    UpdateProviderRequest,
    to_provider_response,
)
from synthorg.api.dto import (
    TestConnectionRequest as ConnTestRequest,
)
from synthorg.api.dto_discovery import (
    AddAllowlistEntryRequest,
    DiscoveryPolicyResponse,
    RemoveAllowlistEntryRequest,
)
from synthorg.api.dto_providers import (
    ProviderModelResponse,
    to_provider_model_response,
)
from synthorg.api.errors import ApiValidationError, ConflictError, NotFoundError
from synthorg.api.guards import require_ceo_or_manager, require_read_access
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_MODEL_CAPABILITIES_LOOKUP_FAILED,
    API_PROVIDER_HEALTH_QUERIED,
    API_PROVIDER_USAGE_ENRICHMENT_FAILED,
    API_RESOURCE_CONFLICT,
    API_RESOURCE_NOT_FOUND,
    API_VALIDATION_FAILED,
)
from synthorg.providers.errors import (
    ProviderAlreadyExistsError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from synthorg.providers.health import ProviderHealthSummary  # noqa: TC001
from synthorg.providers.presets import ProviderPreset, get_preset, list_presets
from synthorg.providers.probing import probe_preset_urls

logger = get_logger(__name__)


async def _enrich_with_usage(
    summary: ProviderHealthSummary,
    app_state: AppState,
    name: str,
) -> ProviderHealthSummary:
    """Enrich a health summary with token/cost data from CostTracker.

    Args:
        summary: Base health summary from the health tracker.
        app_state: Application state.
        name: Provider name.

    Returns:
        Enriched summary (or unchanged if enrichment is unavailable).
    """
    if not app_state.has_cost_tracker:
        return summary
    try:
        now = datetime.now(UTC)
        usage = await app_state.cost_tracker.get_provider_usage(
            name,
            start=now - timedelta(hours=24),
            end=now,
        )
        return summary.model_copy(
            update={
                "total_tokens_24h": usage.total_tokens,
                "total_cost_24h": usage.total_cost,
            },
        )
    except MemoryError, RecursionError:
        raise
    except Exception as exc:
        logger.warning(
            API_PROVIDER_USAGE_ENRICHMENT_FAILED,
            provider=name,
            error=str(exc),
            error_type=type(exc).__qualname__,
        )
        return summary


class ProviderController(Controller):
    """LLM provider management: CRUD, test, and presets."""

    path = "/providers"
    tags = ("providers",)

    # ── Read endpoints (read access) ─────────────────────────

    @get(
        "/presets",
        guards=[require_read_access],
    )
    async def get_presets(
        self,
        state: State,  # noqa: ARG002
    ) -> ApiResponse[tuple[ProviderPreset, ...]]:
        """List all available provider presets.

        Args:
            state: Application state.

        Returns:
            Preset list envelope.
        """
        return ApiResponse(data=list_presets())

    @post(
        "/probe-preset",
        guards=[require_ceo_or_manager],
    )
    async def probe_preset(
        self,
        state: State,  # noqa: ARG002
        data: ProbePresetRequest,
    ) -> ApiResponse[ProbePresetResponse]:
        """Probe a preset's candidate URLs for reachability.

        Tries each candidate URL in priority order and returns the
        first one that responds, along with the number of models
        discovered.

        Args:
            state: Application state (injected by Litestar, unused).
            data: Probe request with preset name.

        Returns:
            Probe result envelope.

        Raises:
            ApiValidationError: If the preset is unknown.
        """
        preset = get_preset(data.preset_name)
        if preset is None:
            logger.warning(
                API_VALIDATION_FAILED,
                resource="preset",
                name=data.preset_name,
            )
            msg = f"Unknown preset: {data.preset_name!r}"
            raise ApiValidationError(msg)
        if not preset.candidate_urls:
            return ApiResponse(
                data=ProbePresetResponse(candidates_tried=0),
            )
        result = await probe_preset_urls(preset.name)
        return ApiResponse(
            data=ProbePresetResponse(
                url=result.url,
                model_count=result.model_count,
                candidates_tried=result.candidates_tried,
            ),
        )

    @get(
        "/",
        guards=[require_read_access],
    )
    async def list_providers(
        self,
        state: State,
    ) -> ApiResponse[dict[str, ProviderResponse]]:
        """List all configured providers (secrets stripped).

        Args:
            state: Application state.

        Returns:
            Provider responses envelope.
        """
        app_state: AppState = state.app_state
        providers = await app_state.config_resolver.get_provider_configs()
        safe = {name: to_provider_response(p) for name, p in providers.items()}
        return ApiResponse(data=safe)

    @get(
        "/{name:str}",
        guards=[require_read_access],
    )
    async def get_provider(
        self,
        state: State,
        name: PathName,
    ) -> ApiResponse[ProviderResponse]:
        """Get a provider by name (secrets stripped).

        Args:
            state: Application state.
            name: Provider name.

        Returns:
            Provider response envelope.

        Raises:
            NotFoundError: If the provider is not found.
        """
        app_state: AppState = state.app_state
        providers = await app_state.config_resolver.get_provider_configs()
        provider = providers.get(name)
        if provider is None:
            msg = f"Provider {name!r} not found"
            logger.warning(API_RESOURCE_NOT_FOUND, resource="provider", name=name)
            raise NotFoundError(msg)
        return ApiResponse(data=to_provider_response(provider))

    @get(
        "/{name:str}/models",
        guards=[require_read_access],
    )
    async def list_models(
        self,
        state: State,
        name: PathName,
    ) -> ApiResponse[tuple[ProviderModelResponse, ...]]:
        """List models for a provider with runtime capabilities.

        Args:
            state: Application state.
            name: Provider name.

        Returns:
            Provider models enriched with capability flags.

        Raises:
            NotFoundError: If the provider is not found.
        """
        app_state: AppState = state.app_state
        providers = await app_state.config_resolver.get_provider_configs()
        provider = providers.get(name)
        if provider is None:
            msg = f"Provider {name!r} not found"
            logger.warning(API_RESOURCE_NOT_FOUND, resource="provider", name=name)
            raise NotFoundError(msg)

        driver = None
        if app_state.has_provider_registry and name in app_state.provider_registry:
            driver = app_state.provider_registry.get(name)

        results: list[ProviderModelResponse] = []
        for model_config in provider.models:
            caps = None
            if driver is not None:
                try:
                    caps = await driver.get_model_capabilities(model_config.id)
                except MemoryError, RecursionError:
                    raise
                except Exception as exc:
                    logger.warning(
                        API_MODEL_CAPABILITIES_LOOKUP_FAILED,
                        provider=name,
                        model=model_config.id,
                        error=str(exc),
                        error_type=type(exc).__qualname__,
                    )
            results.append(to_provider_model_response(model_config, caps))
        return ApiResponse(data=tuple(results))

    @get(
        "/{name:str}/health",
        guards=[require_read_access],
    )
    async def get_provider_health(
        self,
        state: State,
        name: PathName,
    ) -> ApiResponse[ProviderHealthSummary]:
        """Get provider health summary.

        Returns health status, error rate, average response time,
        call count, total tokens, and total cost for the last 24
        hours.  Token and cost totals are enriched from the cost
        tracker when available.

        Args:
            state: Application state.
            name: Provider name.

        Returns:
            Provider health summary envelope.

        Raises:
            NotFoundError: If the provider is not found.
        """
        app_state: AppState = state.app_state
        providers = await app_state.config_resolver.get_provider_configs()
        if name not in providers:
            msg = f"Provider {name!r} not found"
            logger.warning(API_RESOURCE_NOT_FOUND, resource="provider", name=name)
            raise NotFoundError(msg)
        summary = await app_state.provider_health_tracker.get_summary(name)
        summary = await _enrich_with_usage(summary, app_state, name)
        logger.debug(
            API_PROVIDER_HEALTH_QUERIED,
            provider=name,
            health_status=summary.health_status.value,
            calls_24h=summary.calls_last_24h,
        )
        return ApiResponse(data=summary)

    # ── Write endpoints (write access) ───────────────────────

    @post(
        "/",
        guards=[require_ceo_or_manager],
    )
    async def create_provider(
        self,
        state: State,
        data: CreateProviderRequest,
    ) -> ApiResponse[ProviderResponse]:
        """Create a new provider.

        Args:
            state: Application state.
            data: Create provider request.

        Returns:
            Created provider response.

        Raises:
            ConflictError: If a provider with this name already exists.
            ApiValidationError: If the provider configuration fails
                validation.
        """
        app_state: AppState = state.app_state
        try:
            config = await app_state.provider_management.create_provider(data)
        except ProviderAlreadyExistsError as exc:
            logger.warning(
                API_RESOURCE_CONFLICT,
                resource="provider",
                name=data.name,
            )
            raise ConflictError(str(exc)) from exc
        except ProviderValidationError as exc:
            logger.warning(
                API_VALIDATION_FAILED,
                resource="provider",
                error=str(exc),
            )
            raise ApiValidationError(str(exc)) from exc
        return ApiResponse(data=to_provider_response(config))

    @post(
        "/from-preset",
        guards=[require_ceo_or_manager],
    )
    async def create_from_preset(
        self,
        state: State,
        data: CreateFromPresetRequest,
    ) -> ApiResponse[ProviderResponse]:
        """Create a provider from a preset.

        Args:
            state: Application state.
            data: Preset-based creation request.

        Returns:
            Created provider response.

        Raises:
            ConflictError: If a provider with this name already exists.
            ApiValidationError: If the preset is unknown or config
                validation fails.
        """
        app_state: AppState = state.app_state
        try:
            config = await app_state.provider_management.create_from_preset(
                data,
            )
        except ProviderAlreadyExistsError as exc:
            logger.warning(
                API_RESOURCE_CONFLICT,
                resource="provider",
                name=data.name,
            )
            raise ConflictError(str(exc)) from exc
        except ProviderValidationError as exc:
            logger.warning(
                API_VALIDATION_FAILED,
                resource="provider",
                error=str(exc),
            )
            raise ApiValidationError(str(exc)) from exc
        return ApiResponse(data=to_provider_response(config))

    @put(
        "/{name:str}",
        guards=[require_ceo_or_manager],
    )
    async def update_provider(
        self,
        state: State,
        name: PathName,
        data: UpdateProviderRequest,
    ) -> ApiResponse[ProviderResponse]:
        """Update an existing provider.

        Args:
            state: Application state.
            name: Provider name.
            data: Partial update request.

        Returns:
            Updated provider response.

        Raises:
            NotFoundError: If the provider does not exist.
            ApiValidationError: If the update fails validation.
        """
        app_state: AppState = state.app_state
        try:
            config = await app_state.provider_management.update_provider(
                name,
                data,
            )
        except ProviderNotFoundError as exc:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="provider",
                name=name,
            )
            raise NotFoundError(str(exc)) from exc
        except ProviderValidationError as exc:
            logger.warning(
                API_VALIDATION_FAILED,
                resource="provider",
                error=str(exc),
            )
            raise ApiValidationError(str(exc)) from exc
        return ApiResponse(data=to_provider_response(config))

    @delete(
        "/{name:str}",
        guards=[require_ceo_or_manager],
        status_code=HTTP_204_NO_CONTENT,
    )
    async def delete_provider(
        self,
        state: State,
        name: PathName,
    ) -> None:
        """Delete a provider.

        Args:
            state: Application state.
            name: Provider name.

        Raises:
            NotFoundError: If the provider does not exist.
        """
        app_state: AppState = state.app_state
        try:
            await app_state.provider_management.delete_provider(name)
        except ProviderNotFoundError as exc:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="provider",
                name=name,
            )
            raise NotFoundError(str(exc)) from exc

    @post(
        "/{name:str}/discover-models",
        guards=[require_ceo_or_manager],
    )
    async def discover_models(
        self,
        state: State,
        name: PathName,
        preset_hint: Annotated[str, Parameter(max_length=64)] | None = None,
    ) -> ApiResponse[DiscoverModelsResponse]:
        """Discover available models from a provider endpoint.

        Queries the provider's API for available models and updates
        the provider configuration with any discovered models.  When
        ``base_url`` is not configured, returns an empty result.

        Args:
            state: Application state.
            name: Provider name.
            preset_hint: Optional preset name to guide endpoint
                selection (e.g. ``"ollama"``).

        Returns:
            Discovery result with found models.

        Raises:
            NotFoundError: If the provider does not exist.
        """
        app_state: AppState = state.app_state
        mgmt = app_state.provider_management
        try:
            discovered = await mgmt.discover_models_for_provider(
                name,
                preset_hint=preset_hint,
            )
        except ProviderNotFoundError as exc:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="provider",
                name=name,
            )
            raise NotFoundError(str(exc)) from exc
        return ApiResponse(
            data=DiscoverModelsResponse(
                discovered_models=discovered,
                provider_name=name,
            ),
        )

    @post(
        "/{name:str}/test",
        guards=[require_ceo_or_manager],
    )
    async def test_connection(
        self,
        state: State,
        name: PathName,
        data: ConnTestRequest,
    ) -> ApiResponse[TestConnectionResponse]:
        """Test connectivity to a provider.

        Args:
            state: Application state.
            name: Provider name.
            data: Test connection request (includes optional model selection).

        Returns:
            Connection test result.

        Raises:
            NotFoundError: If the provider does not exist.
        """
        app_state: AppState = state.app_state
        try:
            result = await app_state.provider_management.test_connection(
                name,
                data,
            )
        except ProviderNotFoundError as exc:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="provider",
                name=name,
            )
            raise NotFoundError(str(exc)) from exc
        return ApiResponse(data=result)

    # ── Discovery allowlist (read + write access) ──────────────

    @get(
        "/discovery-policy",
        guards=[require_read_access],
    )
    async def get_discovery_policy(
        self,
        state: State,
    ) -> ApiResponse[DiscoveryPolicyResponse]:
        """Return the current provider discovery SSRF allowlist.

        Args:
            state: Application state.

        Returns:
            Current discovery policy envelope.
        """
        app_state: AppState = state.app_state
        policy = await app_state.provider_management.get_discovery_policy()
        return ApiResponse(
            data=DiscoveryPolicyResponse.model_validate(
                policy,
                from_attributes=True,
            ),
        )

    @post(
        "/discovery-policy/entries",
        guards=[require_ceo_or_manager],
    )
    async def add_allowlist_entry(
        self,
        state: State,
        data: AddAllowlistEntryRequest,
    ) -> ApiResponse[DiscoveryPolicyResponse]:
        """Add a custom host:port entry to the discovery allowlist.

        Args:
            state: Application state.
            data: Request with the host:port entry to add.

        Returns:
            Updated discovery policy envelope.
        """
        app_state: AppState = state.app_state
        policy = await app_state.provider_management.add_custom_allowlist_entry(
            data.host_port,
        )
        return ApiResponse(
            data=DiscoveryPolicyResponse.model_validate(
                policy,
                from_attributes=True,
            ),
        )

    @post(
        "/discovery-policy/remove-entry",
        guards=[require_ceo_or_manager],
    )
    async def remove_allowlist_entry(
        self,
        state: State,
        data: RemoveAllowlistEntryRequest,
    ) -> ApiResponse[DiscoveryPolicyResponse]:
        """Remove a host:port entry from the discovery allowlist.

        Args:
            state: Application state.
            data: Request with the host:port entry to remove.

        Returns:
            Updated discovery policy envelope.
        """
        app_state: AppState = state.app_state
        policy = await app_state.provider_management.remove_custom_allowlist_entry(
            data.host_port,
        )
        return ApiResponse(
            data=DiscoveryPolicyResponse.model_validate(
                policy,
                from_attributes=True,
            ),
        )
