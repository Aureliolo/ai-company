"""Provider management service -- runtime CRUD for LLM providers.

Orchestrates config validation, persistence via SettingsService,
and hot-reload of ProviderRegistry + ModelRouter in AppState.
"""

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

from synthorg.api.dto import (
    CreateFromPresetRequest,
    CreateProviderRequest,
    TestConnectionRequest,
    TestConnectionResponse,
    UpdateProviderRequest,
)
from synthorg.config.schema import ProviderConfig, ProviderModelConfig
from synthorg.observability import get_logger
from synthorg.observability.events.provider import (
    PROVIDER_ALREADY_EXISTS,
    PROVIDER_CONNECTION_TESTED,
    PROVIDER_CREATED,
    PROVIDER_DELETED,
    PROVIDER_NOT_FOUND,
    PROVIDER_UPDATED,
    PROVIDER_VALIDATION_FAILED,
)
from synthorg.providers.discovery import discover_models
from synthorg.providers.enums import AuthType, MessageRole
from synthorg.providers.errors import (
    ProviderAlreadyExistsError,
    ProviderError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from synthorg.providers.models import ChatMessage
from synthorg.providers.presets import get_preset
from synthorg.providers.registry import ProviderRegistry

if TYPE_CHECKING:
    from synthorg.api.state import AppState
    from synthorg.config.schema import RootConfig
    from synthorg.providers.routing.router import ModelRouter
    from synthorg.settings.resolver import ConfigResolver
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)


class ProviderManagementService:
    """Runtime CRUD service for LLM providers.

    All mutating operations are serialized under an asyncio lock
    to prevent read-modify-write races on the provider config blob.

    Args:
        settings_service: Settings persistence layer.
        config_resolver: Typed config accessor.
        app_state: Application state for hot-reload swaps.
        config: Root company configuration.
    """

    def __init__(
        self,
        *,
        settings_service: SettingsService,
        config_resolver: ConfigResolver,
        app_state: AppState,
        config: RootConfig,
    ) -> None:
        self._settings_service = settings_service
        self._config_resolver = config_resolver
        self._app_state = app_state
        self._config = config
        self._lock = asyncio.Lock()

    async def list_providers(self) -> dict[str, ProviderConfig]:
        """List all configured providers.

        Returns:
            Provider configurations keyed by name.
        """
        return await self._config_resolver.get_provider_configs()

    async def get_provider(self, name: str) -> ProviderConfig:
        """Get a single provider by name.

        Args:
            name: Provider name.

        Returns:
            The provider configuration.

        Raises:
            ProviderNotFoundError: If the provider does not exist.
        """
        providers = await self._config_resolver.get_provider_configs()
        config = providers.get(name)
        if config is None:
            msg = f"Provider {name!r} not found"
            logger.warning(PROVIDER_NOT_FOUND, provider=name, error=msg)
            raise ProviderNotFoundError(msg)
        return config

    async def create_provider(
        self,
        request: CreateProviderRequest,
    ) -> ProviderConfig:
        """Create a new provider.

        Args:
            request: Create provider request with config fields.

        Returns:
            The created provider configuration.

        Raises:
            ProviderAlreadyExistsError: If a provider with this name
                already exists.
            ProviderValidationError: If the config fails validation.
        """
        async with self._lock:
            providers = await self._config_resolver.get_provider_configs()
            if request.name in providers:
                msg = f"Provider {request.name!r} already exists"
                logger.warning(
                    PROVIDER_ALREADY_EXISTS,
                    provider=request.name,
                    error=msg,
                )
                raise ProviderAlreadyExistsError(msg)

            new_config = _build_provider_config(request)
            new_providers = {**providers, request.name: new_config}
            await self._validate_and_persist(new_providers)

            logger.info(
                PROVIDER_CREATED,
                provider=request.name,
                driver=new_config.driver,
                auth_type=new_config.auth_type,
            )
            return new_config

    async def update_provider(
        self,
        name: str,
        request: UpdateProviderRequest,
    ) -> ProviderConfig:
        """Update an existing provider.

        Args:
            name: Provider name to update.
            request: Partial update request.

        Returns:
            The updated provider configuration.

        Raises:
            ProviderNotFoundError: If the provider does not exist.
            ProviderValidationError: If the update fails validation.
        """
        async with self._lock:
            providers = await self._config_resolver.get_provider_configs()
            existing = providers.get(name)
            if existing is None:
                msg = f"Provider {name!r} not found"
                logger.warning(PROVIDER_NOT_FOUND, provider=name, error=msg)
                raise ProviderNotFoundError(msg)

            updated = _apply_update(existing, request)
            new_providers = {**providers, name: updated}
            await self._validate_and_persist(new_providers)

            logger.info(
                PROVIDER_UPDATED,
                provider=name,
                driver=updated.driver,
                auth_type=updated.auth_type,
            )
            return updated

    async def delete_provider(self, name: str) -> None:
        """Delete a provider.

        Args:
            name: Provider name to delete.

        Raises:
            ProviderNotFoundError: If the provider does not exist.
        """
        async with self._lock:
            providers = await self._config_resolver.get_provider_configs()
            if name not in providers:
                msg = f"Provider {name!r} not found"
                logger.warning(PROVIDER_NOT_FOUND, provider=name, error=msg)
                raise ProviderNotFoundError(msg)

            new_providers = {k: v for k, v in providers.items() if k != name}
            await self._validate_and_persist(new_providers)

            logger.info(PROVIDER_DELETED, provider=name)

    async def test_connection(
        self,
        name: str,
        request: TestConnectionRequest,
    ) -> TestConnectionResponse:
        """Test connectivity to a provider.

        Builds a temporary driver and sends a minimal completion
        request.  The driver is not registered in AppState.

        Args:
            name: Provider name.
            request: Optional model selection.

        Returns:
            Connection test result with latency or error.
        """
        providers = await self._config_resolver.get_provider_configs()
        config = providers.get(name)
        if config is None:
            msg = f"Provider {name!r} not found"
            logger.warning(PROVIDER_NOT_FOUND, provider=name, error=msg)
            raise ProviderNotFoundError(msg)

        if not config.models:
            return TestConnectionResponse(
                success=False,
                error="Provider has no models configured",
            )

        model_id = request.model or config.models[0].id
        return await self._do_test_connection(name, config, model_id)

    async def _do_test_connection(
        self,
        name: str,
        config: ProviderConfig,
        model_id: str,
    ) -> TestConnectionResponse:
        """Execute the actual connection test probe.

        Args:
            name: Provider name.
            config: Provider configuration.
            model_id: Model ID to test.

        Returns:
            Connection test result.
        """
        try:
            from synthorg.providers.drivers.litellm_driver import (  # noqa: PLC0415
                LiteLLMDriver,
            )

            driver = LiteLLMDriver(name, config)
            messages = [
                ChatMessage(role=MessageRole.USER, content="ping"),
            ]
            start = time.monotonic()
            await driver.complete(messages, model_id)
            elapsed_ms = (time.monotonic() - start) * 1000

            logger.info(
                PROVIDER_CONNECTION_TESTED,
                provider=name,
                model=model_id,
                success=True,
                latency_ms=round(elapsed_ms, 1),
            )
            return TestConnectionResponse(
                success=True,
                latency_ms=round(elapsed_ms, 1),
                model_tested=model_id,
            )
        except ProviderError as exc:
            logger.warning(
                PROVIDER_CONNECTION_TESTED,
                provider=name,
                model=model_id,
                success=False,
                error=str(exc),
            )
            return TestConnectionResponse(
                success=False,
                error=str(exc),
                model_tested=model_id,
            )
        except Exception as exc:
            logger.error(
                PROVIDER_CONNECTION_TESTED,
                provider=name,
                model=model_id,
                success=False,
                error=str(exc),
                exc_info=True,
            )
            return TestConnectionResponse(
                success=False,
                error=f"Connection test failed: {type(exc).__name__}",
                model_tested=model_id,
            )

    async def create_from_preset(
        self,
        request: CreateFromPresetRequest,
    ) -> ProviderConfig:
        """Create a provider from a preset template.

        When the preset has ``auth_type=none`` and a base URL but no
        models, attempts auto-discovery before creating the provider.

        Args:
            request: Preset-based creation request.

        Returns:
            The created provider configuration.

        Raises:
            ProviderValidationError: If the preset is unknown.
            ProviderAlreadyExistsError: If the name is taken.
        """
        preset = get_preset(request.preset_name)
        if preset is None:
            msg = f"Unknown preset: {request.preset_name!r}"
            logger.warning(
                PROVIDER_VALIDATION_FAILED,
                preset=request.preset_name,
                error=msg,
            )
            raise ProviderValidationError(msg)

        models = request.models if request.models is not None else preset.default_models
        base_url = request.base_url or preset.default_base_url

        # Auto-discover models for no-auth presets with a base URL.
        if not models and preset.auth_type == AuthType.NONE and base_url:
            discovered = await discover_models(base_url, preset.name)
            if discovered:
                models = discovered

        create_request = CreateProviderRequest(
            name=request.name,
            driver=preset.driver,
            auth_type=preset.auth_type,
            api_key=request.api_key,
            base_url=base_url,
            models=models,
        )
        return await self.create_provider(create_request)

    async def discover_models_for_provider(
        self,
        name: str,
    ) -> tuple[ProviderModelConfig, ...]:
        """Discover and update models for an existing provider.

        Queries the provider's endpoint for available models and
        updates the provider configuration if models are found.

        Args:
            name: Provider name.

        Returns:
            Tuple of discovered model configs (may be empty).

        Raises:
            ProviderNotFoundError: If the provider does not exist.
        """
        config = await self.get_provider(name)

        if config.base_url is None:
            return ()

        # Infer preset hint from base URL patterns.
        preset_hint = _infer_preset_hint(config.base_url)
        discovered = await discover_models(config.base_url, preset_hint)

        if discovered:
            update_req = UpdateProviderRequest(models=discovered)
            await self.update_provider(name, update_req)

        return discovered

    async def _validate_and_persist(
        self,
        new_providers: dict[str, ProviderConfig],
    ) -> None:
        """Validate, persist, and hot-reload providers.

        Build both registry and router before persisting to prevent
        DB/AppState divergence on build failure.

        Args:
            new_providers: Complete new provider dict.

        Raises:
            ProviderValidationError: If registry or router build fails.
        """
        # 1. Validate: build registry + router before any I/O
        try:
            registry = ProviderRegistry.from_config(new_providers)
            router = self._build_router(new_providers)
        except Exception as exc:
            msg = f"Provider configuration validation failed: {exc}"
            logger.warning(
                PROVIDER_VALIDATION_FAILED,
                error=str(exc),
                provider_count=len(new_providers),
            )
            raise ProviderValidationError(msg) from exc

        # 2. Persist to settings
        try:
            serialized = _serialize_providers(new_providers)
            await self._settings_service.set(
                "providers",
                "configs",
                json.dumps(serialized),
            )
        except Exception as exc:
            msg = f"Failed to persist provider configuration: {type(exc).__name__}"
            logger.exception(
                PROVIDER_VALIDATION_FAILED,
                error=str(exc),
                provider_count=len(new_providers),
            )
            raise ProviderValidationError(msg) from exc

        # 3. Hot-reload: swap in AppState (both sync, no await gap)
        self._app_state.swap_provider_registry(registry)
        self._app_state.swap_model_router(router)

    def _build_router(
        self,
        providers: dict[str, ProviderConfig],
    ) -> ModelRouter:
        """Build a new ModelRouter from provider configs.

        Args:
            providers: Provider configurations.

        Returns:
            New ModelRouter instance.
        """
        from synthorg.providers.routing.router import (  # noqa: PLC0415
            ModelRouter,
        )

        return ModelRouter(
            routing_config=self._config.routing,
            providers=providers,
        )


def _build_provider_config(
    request: CreateProviderRequest,
) -> ProviderConfig:
    """Build a ProviderConfig from a create request.

    Args:
        request: Create provider request.

    Returns:
        Frozen ProviderConfig.
    """
    return ProviderConfig(
        driver=request.driver,
        auth_type=request.auth_type,
        api_key=request.api_key,
        base_url=request.base_url,
        oauth_token_url=request.oauth_token_url,
        oauth_client_id=request.oauth_client_id,
        oauth_client_secret=request.oauth_client_secret,
        oauth_scope=request.oauth_scope,
        custom_header_name=request.custom_header_name,
        custom_header_value=request.custom_header_value,
        models=request.models,
    )


_UPDATE_FIELDS: tuple[str, ...] = (
    "driver",
    "base_url",
    "oauth_token_url",
    "oauth_client_id",
    "oauth_client_secret",
    "oauth_scope",
    "custom_header_name",
    "custom_header_value",
    "models",
)


def _apply_update(
    existing: ProviderConfig,
    request: UpdateProviderRequest,
) -> ProviderConfig:
    """Apply partial update fields to an existing config.

    When auth_type changes, orphaned credential fields from the
    old auth type are automatically cleared.

    Args:
        existing: Current provider configuration.
        request: Partial update request.

    Returns:
        New ProviderConfig with updates applied.
    """
    updates: dict[str, Any] = {}
    for field in _UPDATE_FIELDS:
        value = getattr(request, field)
        if value is not None:
            updates[field] = value

    # auth_type change: unconditionally clear incompatible credentials
    if request.auth_type is not None:
        updates["auth_type"] = request.auth_type
        if request.auth_type not in (AuthType.API_KEY, AuthType.OAUTH):
            updates["api_key"] = None
        if request.auth_type != AuthType.OAUTH:
            updates["oauth_client_secret"] = None
            updates["oauth_token_url"] = None
            updates["oauth_client_id"] = None
            updates["oauth_scope"] = None
        if request.auth_type != AuthType.CUSTOM_HEADER:
            updates["custom_header_name"] = None
            updates["custom_header_value"] = None

    # api_key has special clear_api_key semantics (overrides above)
    if request.api_key is not None:
        updates["api_key"] = request.api_key
    elif request.clear_api_key:
        updates["api_key"] = None

    # Re-validate the merged config (model_copy skips validators)
    merged = {**existing.model_dump(mode="python"), **updates}
    return ProviderConfig.model_validate(merged)


def _serialize_providers(
    providers: dict[str, ProviderConfig],
) -> dict[str, Any]:
    """Serialize provider dict for JSON persistence.

    Args:
        providers: Provider configurations.

    Returns:
        JSON-safe dict of serialized provider configs.
    """
    return {name: config.model_dump(mode="json") for name, config in providers.items()}


def _infer_preset_hint(base_url: str) -> str | None:
    """Infer the preset name from a provider base URL.

    Uses port-based heuristics for common local providers.

    Args:
        base_url: Provider base URL.

    Returns:
        Preset name hint, or ``None`` if unrecognized.
    """
    url_lower = base_url.lower()
    if ":11434" in url_lower:
        return "ollama"
    if ":1234" in url_lower:
        return "lm-studio"
    if ":8000" in url_lower:
        return "vllm"
    return None
