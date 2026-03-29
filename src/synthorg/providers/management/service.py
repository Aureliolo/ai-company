"""Provider management service -- runtime CRUD for LLM providers.

Orchestrates config validation, persistence via SettingsService,
and hot-reload of ProviderRegistry + ModelRouter in AppState.
"""

import asyncio
import json
import time
from typing import TYPE_CHECKING

from synthorg.api.dto import (
    CreateFromPresetRequest,
    CreateProviderRequest,
    TestConnectionRequest,
    TestConnectionResponse,
    UpdateProviderRequest,
)
from synthorg.config.schema import ProviderConfig, ProviderModelConfig  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.provider import (
    PROVIDER_ALREADY_EXISTS,
    PROVIDER_CONNECTION_TESTED,
    PROVIDER_CREATED,
    PROVIDER_DELETED,
    PROVIDER_DISCOVERY_FAILED,
    PROVIDER_DISCOVERY_SELF_CONNECTION_BLOCKED,
    PROVIDER_NOT_FOUND,
    PROVIDER_UPDATED,
    PROVIDER_VALIDATION_FAILED,
)
from synthorg.providers.discovery import discover_models
from synthorg.providers.discovery_policy import (
    ProviderDiscoveryPolicy,
    is_url_allowed,
)
from synthorg.providers.enums import AuthType, MessageRole
from synthorg.providers.errors import (
    ProviderAlreadyExistsError,
    ProviderError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from synthorg.providers.management._helpers import (
    apply_update,
    build_discovery_headers,
    build_provider_config,
    infer_preset_hint,
    models_from_litellm,
    serialize_providers,
)
from synthorg.providers.management.allowlist import DiscoveryAllowlistManager
from synthorg.providers.models import ChatMessage
from synthorg.providers.presets import ProviderPreset, get_preset
from synthorg.providers.registry import ProviderRegistry
from synthorg.providers.url_utils import is_self_url, redact_url

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
        self._allowlist = DiscoveryAllowlistManager(
            settings_service=settings_service,
            config_resolver=config_resolver,
        )

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

            new_config = build_provider_config(request)
            new_providers = {**providers, request.name: new_config}
            await self._validate_and_persist(new_providers)
            await self._allowlist.update_for_create(new_config)

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

            updated = apply_update(existing, request)
            new_providers = {**providers, name: updated}
            await self._validate_and_persist(new_providers)
            await self._allowlist.update_for_update(
                existing,
                updated,
                new_providers,
            )

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

            removed_config = providers[name]
            new_providers = {k: v for k, v in providers.items() if k != name}
            await self._validate_and_persist(new_providers)
            await self._allowlist.update_for_delete(
                removed_config,
                new_providers,
            )

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
            request: Test connection request (includes optional model selection).

        Returns:
            Connection test result with latency or error.

        Raises:
            ProviderNotFoundError: If the provider does not exist.
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
            return await self._probe_provider(name, config, model_id)
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
        except asyncio.CancelledError:
            raise
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

    async def _probe_provider(
        self,
        name: str,
        config: ProviderConfig,
        model_id: str,
    ) -> TestConnectionResponse:
        """Send a minimal completion request to verify connectivity.

        Args:
            name: Provider name for logging.
            config: Provider configuration.
            model_id: Model to test with.

        Returns:
            Successful connection test response.
        """
        from synthorg.providers.drivers.litellm_driver import (  # noqa: PLC0415
            LiteLLMDriver,
        )

        driver = LiteLLMDriver(name, config)
        messages = [ChatMessage(role=MessageRole.USER, content="ping")]
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

    async def create_from_preset(
        self,
        request: CreateFromPresetRequest,
    ) -> ProviderConfig:
        """Create a provider from a preset template.

        The request's ``auth_type`` overrides the preset default when
        provided.  When the effective auth type is ``AuthType.NONE``
        and a base URL is available but no models are given, attempts
        auto-discovery before creating the provider.

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

        if request.models is not None:
            models = request.models
        else:
            litellm_models = models_from_litellm(preset.litellm_provider)
            models = litellm_models or preset.default_models
        base_url = request.base_url or preset.default_base_url
        auth_type = request.auth_type or preset.auth_type
        models = await self._maybe_discover_preset_models(
            preset,
            base_url,
            models,
            auth_type=auth_type,
        )
        create_request = CreateProviderRequest(
            name=request.name,
            driver=preset.driver,
            litellm_provider=preset.litellm_provider,
            auth_type=auth_type,
            api_key=request.api_key,
            subscription_token=request.subscription_token,
            tos_accepted=request.tos_accepted,
            base_url=base_url,
            models=models,
        )
        return await self.create_provider(create_request)

    async def _maybe_discover_preset_models(
        self,
        preset: ProviderPreset,
        base_url: str | None,
        models: tuple[ProviderModelConfig, ...],
        *,
        auth_type: AuthType,
    ) -> tuple[ProviderModelConfig, ...]:
        """Auto-discover models for no-auth presets when none are provided.

        Only attempts discovery when the effective auth type is
        ``AuthType.NONE``, a base URL is available, and no models were
        explicitly provided.  The request's ``auth_type`` override is
        applied before this check.

        Args:
            preset: Resolved preset definition.
            base_url: Provider base URL (may be user-overridden).
            models: Explicitly provided models (may be empty).
            auth_type: Effective auth type (request override or preset default).

        Returns:
            Discovered models if any, otherwise the original models.
        """
        if models or auth_type != AuthType.NONE or not base_url:
            return models
        if self._is_self_connection(base_url):
            return models
        policy = await self._allowlist.load()
        trust = is_url_allowed(base_url, policy)
        discovered = await discover_models(
            base_url,
            preset.name,
            trust_url=trust,
        )
        return discovered or models

    async def discover_models_for_provider(
        self,
        name: str,
        *,
        preset_hint: str | None = None,
    ) -> tuple[ProviderModelConfig, ...]:
        """Discover and update models for an existing provider.

        Queries the provider's endpoint for available models and
        updates the provider configuration if models are found.
        Returns an empty tuple without querying if the provider has
        no ``base_url`` configured.  Auth headers are forwarded when
        available; discovery proceeds without them otherwise.

        Args:
            name: Provider name.
            preset_hint: Optional preset name hint for endpoint selection.
                Falls back to port-based inference when not provided.

        Returns:
            Tuple of discovered model configs (may be empty).

        Raises:
            ProviderNotFoundError: If the provider does not exist.
        """
        # Optimistic read (no lock): early-exit if base_url is None.
        # The authoritative check happens under the lock in
        # _apply_discovered_models, which re-reads and verifies base_url
        # has not changed before persisting discovered models.
        config = await self.get_provider(name)

        if config.base_url is None:
            logger.info(
                PROVIDER_DISCOVERY_FAILED,
                provider=name,
                reason="no_base_url",
            )
            return ()

        if self._is_self_connection(config.base_url):
            return ()

        resolved_hint = preset_hint or infer_preset_hint(config.base_url)
        headers = build_discovery_headers(config)
        policy = await self._allowlist.load()
        trust = is_url_allowed(config.base_url, policy)
        discovered = await discover_models(
            config.base_url,
            resolved_hint,
            headers=headers,
            trust_url=trust,
        )

        if discovered:
            applied = await self._apply_discovered_models(
                name,
                config.base_url,
                discovered,
            )
            if not applied:
                return ()

        return discovered

    def _is_self_connection(self, base_url: str) -> bool:
        """Check if a URL points at this backend and log a warning if so.

        Args:
            base_url: URL to check.

        Returns:
            True if the URL targets the backend, False otherwise.
        """
        backend_port = self._config.api.server.port
        if is_self_url(base_url, backend_port=backend_port):
            logger.warning(
                PROVIDER_DISCOVERY_SELF_CONNECTION_BLOCKED,
                url=redact_url(base_url),
                backend_port=backend_port,
            )
            return True
        return False

    async def get_discovery_policy(self) -> ProviderDiscoveryPolicy:
        """Return the current discovery allowlist policy.

        Returns:
            Current policy (seeded on first access if needed).
        """
        return await self._allowlist.load()

    async def add_custom_allowlist_entry(
        self,
        host_port: str,
    ) -> ProviderDiscoveryPolicy:
        """Add a custom host:port entry to the discovery allowlist.

        Args:
            host_port: Entry to add (e.g. ``"my-server:8080"``).

        Returns:
            Updated policy.
        """
        async with self._lock:
            return await self._allowlist.add_entry(host_port)

    async def remove_custom_allowlist_entry(
        self,
        host_port: str,
    ) -> ProviderDiscoveryPolicy:
        """Remove a host:port entry from the discovery allowlist.

        Args:
            host_port: Entry to remove.

        Returns:
            Updated policy.
        """
        async with self._lock:
            return await self._allowlist.remove_entry(host_port)

    async def _apply_discovered_models(
        self,
        name: str,
        original_base_url: str,
        discovered: tuple[ProviderModelConfig, ...],
    ) -> bool:
        """Atomically verify base_url and persist discovered models.

        Holds the service lock for the entire check-then-write to
        prevent TOCTOU races between re-reading the provider and
        applying the update.

        Args:
            name: Provider name.
            original_base_url: The base_url that was used for discovery.
            discovered: Models discovered from the provider endpoint.

        Returns:
            True if the models were persisted, False if aborted.
        """
        async with self._lock:
            providers = await self._config_resolver.get_provider_configs()
            existing = providers.get(name)
            if existing is None:
                logger.warning(
                    PROVIDER_DISCOVERY_FAILED,
                    provider=name,
                    reason="deleted_during_discovery",
                )
                return False
            if existing.base_url != original_base_url:
                logger.warning(
                    PROVIDER_DISCOVERY_FAILED,
                    provider=name,
                    reason="base_url_changed",
                )
                return False

            updated = apply_update(
                existing,
                UpdateProviderRequest(models=discovered),
            )
            new_providers = {**providers, name: updated}
            await self._validate_and_persist(new_providers)

            logger.info(
                PROVIDER_UPDATED,
                provider=name,
                driver=updated.driver,
                auth_type=updated.auth_type,
            )
        return True

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
            serialized = serialize_providers(new_providers)
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
