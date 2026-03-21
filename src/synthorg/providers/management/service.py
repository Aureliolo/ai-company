"""Provider management service -- runtime CRUD for LLM providers.

Orchestrates config validation, persistence via SettingsService,
and hot-reload of ProviderRegistry + ModelRouter in AppState.
"""

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlparse

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
    PROVIDER_DISCOVERY_ALLOWLIST_SEEDED,
    PROVIDER_DISCOVERY_ALLOWLIST_UPDATED,
    PROVIDER_DISCOVERY_FAILED,
    PROVIDER_DISCOVERY_SELF_CONNECTION_BLOCKED,
    PROVIDER_NOT_FOUND,
    PROVIDER_UPDATED,
    PROVIDER_VALIDATION_FAILED,
)
from synthorg.providers.discovery import discover_models
from synthorg.providers.discovery_policy import (
    ProviderDiscoveryPolicy,
    build_seed_allowlist,
    extract_host_port,
    is_url_allowed,
)
from synthorg.providers.enums import AuthType, MessageRole
from synthorg.providers.errors import (
    ProviderAlreadyExistsError,
    ProviderError,
    ProviderNotFoundError,
    ProviderValidationError,
)
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
            await self._update_allowlist_for_create(new_config)

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
            await self._update_allowlist_for_update(
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
            await self._update_allowlist_for_delete(
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
        models = await self._maybe_discover_preset_models(
            preset,
            base_url,
            models,
        )

        create_request = CreateProviderRequest(
            name=request.name,
            driver=preset.driver,
            auth_type=preset.auth_type,
            api_key=request.api_key,
            base_url=base_url,
            models=models,
        )
        return await self.create_provider(create_request)

    async def _maybe_discover_preset_models(
        self,
        preset: ProviderPreset,
        base_url: str | None,
        models: tuple[ProviderModelConfig, ...],
    ) -> tuple[ProviderModelConfig, ...]:
        """Auto-discover models for no-auth presets when none are provided.

        Only attempts discovery when the preset uses ``AuthType.NONE``,
        a base URL is available, and no models were explicitly provided.
        Trust is determined by the discovery allowlist -- preset default
        URLs are seeded at startup, so they are automatically trusted.

        Args:
            preset: Resolved preset definition.
            base_url: Provider base URL (may be user-overridden).
            models: Explicitly provided models (may be empty).

        Returns:
            Discovered models if any, otherwise the original models.
        """
        if models or preset.auth_type != AuthType.NONE or not base_url:
            return models
        if self._is_self_connection(base_url):
            return models
        policy = await self._load_discovery_policy()
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
        no ``base_url`` configured or uses a non-``none`` auth type
        without credentials (auth headers are forwarded when available).

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

        resolved_hint = preset_hint or _infer_preset_hint(config.base_url)
        headers = _build_discovery_headers(config)
        policy = await self._load_discovery_policy()
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

    async def _load_discovery_policy(self) -> ProviderDiscoveryPolicy:
        """Load the current discovery policy from settings.

        If no persisted policy exists, seeds the allowlist from
        presets and installed providers, persists it, and returns
        the new policy.

        Returns:
            Current discovery policy.
        """
        result = await self._settings_service.get(
            "providers",
            "discovery_allowlist",
        )
        if result.value:
            try:
                data = json.loads(result.value)
                return ProviderDiscoveryPolicy.model_validate(data)
            except json.JSONDecodeError, ValueError:
                pass

        # Seed from presets + installed providers.
        providers = await self._config_resolver.get_provider_configs()
        seeds = build_seed_allowlist(providers)
        policy = ProviderDiscoveryPolicy(host_port_allowlist=seeds)
        await self._persist_discovery_policy(policy)
        logger.info(
            PROVIDER_DISCOVERY_ALLOWLIST_SEEDED,
            entry_count=len(policy.host_port_allowlist),
        )
        return policy

    async def _persist_discovery_policy(
        self,
        policy: ProviderDiscoveryPolicy,
    ) -> None:
        """Serialize and persist the discovery policy to settings.

        Args:
            policy: Policy to persist.
        """
        await self._settings_service.set(
            "providers",
            "discovery_allowlist",
            json.dumps(policy.model_dump(mode="json")),
        )

    async def _update_allowlist_for_create(
        self,
        config: ProviderConfig,
    ) -> None:
        """Add a newly created provider's host:port to the allowlist.

        Args:
            config: The created provider config.
        """
        if config.base_url is None:
            return
        hp = extract_host_port(config.base_url)
        if hp is None:
            return
        policy = await self._load_discovery_policy()
        if hp in policy.host_port_allowlist:
            return
        new_entries = (*policy.host_port_allowlist, hp)
        updated = ProviderDiscoveryPolicy(
            host_port_allowlist=new_entries,
            block_private_ips=policy.block_private_ips,
        )
        await self._persist_discovery_policy(updated)
        logger.info(
            PROVIDER_DISCOVERY_ALLOWLIST_UPDATED,
            action="add",
            host_port=hp,
            entry_count=len(updated.host_port_allowlist),
        )

    async def _update_allowlist_for_delete(
        self,
        removed_config: ProviderConfig,
        remaining_providers: dict[str, ProviderConfig],
    ) -> None:
        """Remove a deleted provider's host:port from the allowlist.

        Only removes the entry if no other provider still uses
        the same host:port.

        Args:
            removed_config: The deleted provider's config.
            remaining_providers: All remaining provider configs.
        """
        if removed_config.base_url is None:
            return
        hp = extract_host_port(removed_config.base_url)
        if hp is None:
            return
        # Check whether any remaining provider shares this host:port.
        for config in remaining_providers.values():
            if config.base_url is not None:
                other_hp = extract_host_port(config.base_url)
                if other_hp == hp:
                    return
        policy = await self._load_discovery_policy()
        if hp not in policy.host_port_allowlist:
            return
        new_entries = tuple(e for e in policy.host_port_allowlist if e != hp)
        updated = ProviderDiscoveryPolicy(
            host_port_allowlist=new_entries,
            block_private_ips=policy.block_private_ips,
        )
        await self._persist_discovery_policy(updated)
        logger.info(
            PROVIDER_DISCOVERY_ALLOWLIST_UPDATED,
            action="remove",
            host_port=hp,
            entry_count=len(updated.host_port_allowlist),
        )

    async def _update_allowlist_for_update(
        self,
        old_config: ProviderConfig,
        new_config: ProviderConfig,
        all_providers: dict[str, ProviderConfig],
    ) -> None:
        """Update the allowlist when a provider's base_url changes.

        Args:
            old_config: Previous provider config.
            new_config: Updated provider config.
            all_providers: All current provider configs (after update).
        """
        old_hp = extract_host_port(old_config.base_url) if old_config.base_url else None
        new_hp = extract_host_port(new_config.base_url) if new_config.base_url else None
        if old_hp == new_hp:
            return

        policy = await self._load_discovery_policy()
        entries = list(policy.host_port_allowlist)

        # Remove old entry if unshared.
        if old_hp is not None and old_hp in entries:
            shared = any(
                extract_host_port(c.base_url) == old_hp
                for c in all_providers.values()
                if c.base_url is not None
            )
            if not shared:
                entries = [e for e in entries if e != old_hp]

        # Add new entry if not present.
        if new_hp is not None and new_hp not in entries:
            entries.append(new_hp)

        updated = ProviderDiscoveryPolicy(
            host_port_allowlist=tuple(entries),
            block_private_ips=policy.block_private_ips,
        )
        await self._persist_discovery_policy(updated)
        logger.info(
            PROVIDER_DISCOVERY_ALLOWLIST_UPDATED,
            action="update",
            old_host_port=old_hp,
            new_host_port=new_hp,
            entry_count=len(updated.host_port_allowlist),
        )

    async def get_discovery_policy(self) -> ProviderDiscoveryPolicy:
        """Return the current discovery allowlist policy.

        Returns:
            Current policy (seeded on first access if needed).
        """
        return await self._load_discovery_policy()

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
            policy = await self._load_discovery_policy()
            normalized = host_port.lower()
            if normalized in policy.host_port_allowlist:
                return policy
            new_entries = (*policy.host_port_allowlist, normalized)
            updated = ProviderDiscoveryPolicy(
                host_port_allowlist=new_entries,
                block_private_ips=policy.block_private_ips,
            )
            await self._persist_discovery_policy(updated)
            logger.info(
                PROVIDER_DISCOVERY_ALLOWLIST_UPDATED,
                action="add_custom",
                host_port=normalized,
                entry_count=len(updated.host_port_allowlist),
            )
            return updated

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
            policy = await self._load_discovery_policy()
            normalized = host_port.lower()
            if normalized not in policy.host_port_allowlist:
                return policy
            new_entries = tuple(
                e for e in policy.host_port_allowlist if e != normalized
            )
            updated = ProviderDiscoveryPolicy(
                host_port_allowlist=new_entries,
                block_private_ips=policy.block_private_ips,
            )
            await self._persist_discovery_policy(updated)
            logger.info(
                PROVIDER_DISCOVERY_ALLOWLIST_UPDATED,
                action="remove_custom",
                host_port=normalized,
                entry_count=len(updated.host_port_allowlist),
            )
            return updated

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

            updated = _apply_update(
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

    # Use model_validate (not model_copy) to run validators on the merged result
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


_PORT_TO_PRESET: Final[dict[int, str]] = {
    11434: "ollama",
    1234: "lm-studio",
}


def _build_discovery_headers(
    config: ProviderConfig,
) -> dict[str, str] | None:
    """Build auth headers for model discovery from provider config.

    Returns headers appropriate for the provider's auth type, or
    ``None`` for ``AuthType.NONE`` or when credentials are absent.
    OAuth-based discovery is not yet supported (token acquisition
    requires a separate flow); a log message is emitted when skipped.

    Args:
        config: Provider configuration.

    Returns:
        Auth headers dict, or ``None``.
    """
    if config.auth_type == AuthType.API_KEY and config.api_key:
        return {"Authorization": f"Bearer {config.api_key}"}
    if (
        config.auth_type == AuthType.CUSTOM_HEADER
        and config.custom_header_name
        and config.custom_header_value
    ):
        return {config.custom_header_name: config.custom_header_value}
    if config.auth_type == AuthType.OAUTH:
        logger.info(
            PROVIDER_DISCOVERY_FAILED,
            reason="oauth_discovery_unsupported",
            auth_type=config.auth_type.value,
        )
    return None


def _infer_preset_hint(base_url: str) -> str | None:
    """Infer the preset name from a provider base URL.

    Uses port-based heuristics for common local providers.
    Recognized ports: 11434 (ollama), 1234 (lm-studio).

    Args:
        base_url: Provider base URL.

    Returns:
        Preset name hint, or ``None`` if unrecognized.
    """
    try:
        port = urlparse(base_url).port
    except ValueError:
        return None
    if port is None:
        return None
    return _PORT_TO_PRESET.get(port)
