"""Provider controller -- CRUD, connection testing, and presets."""

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
    ProviderResponse,
    TestConnectionResponse,
    UpdateProviderRequest,
    to_provider_response,
)
from synthorg.api.dto import (
    TestConnectionRequest as ConnTestRequest,
)
from synthorg.api.errors import ApiValidationError, ConflictError, NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.config.schema import ProviderModelConfig  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_RESOURCE_CONFLICT,
    API_RESOURCE_NOT_FOUND,
    API_VALIDATION_FAILED,
)
from synthorg.providers.errors import (
    ProviderAlreadyExistsError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from synthorg.providers.presets import ProviderPreset, list_presets

logger = get_logger(__name__)


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
    ) -> ApiResponse[tuple[ProviderModelConfig, ...]]:
        """List models for a provider.

        Args:
            state: Application state.
            name: Provider name.

        Returns:
            Provider models envelope.

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
        return ApiResponse(data=provider.models)

    # ── Write endpoints (write access) ───────────────────────

    @post(
        "/",
        guards=[require_write_access],
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
        guards=[require_write_access],
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
        guards=[require_write_access],
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
        guards=[require_write_access],
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
        guards=[require_write_access],
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
        guards=[require_write_access],
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
