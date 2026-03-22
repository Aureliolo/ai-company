"""Private helpers for ProviderManagementService."""

from types import MappingProxyType
from typing import Any, Final
from urllib.parse import urlparse

from synthorg.api.dto import CreateProviderRequest, UpdateProviderRequest  # noqa: TC001
from synthorg.config.schema import ProviderConfig
from synthorg.observability import get_logger
from synthorg.observability.events.provider import PROVIDER_DISCOVERY_FAILED
from synthorg.providers.enums import AuthType

logger = get_logger(__name__)


def build_provider_config(
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


def apply_update(
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

    # api_key: only set/clear when the resulting auth type supports it
    final_auth_type = updates.get("auth_type", existing.auth_type)
    if final_auth_type in (AuthType.API_KEY, AuthType.OAUTH):
        if request.api_key is not None:
            updates["api_key"] = request.api_key
        elif request.clear_api_key:
            updates["api_key"] = None
    else:
        updates["api_key"] = None

    # Use model_validate (not model_copy) to run validators on the merged result
    merged = {**existing.model_dump(mode="python"), **updates}
    return ProviderConfig.model_validate(merged)


def serialize_providers(
    providers: dict[str, ProviderConfig],
) -> dict[str, Any]:
    """Serialize provider dict for JSON persistence.

    Args:
        providers: Provider configurations.

    Returns:
        JSON-safe dict of serialized provider configs.
    """
    return {name: config.model_dump(mode="json") for name, config in providers.items()}


PORT_TO_PRESET: Final[MappingProxyType[int, str]] = MappingProxyType(
    {
        11434: "ollama",
        1234: "lm-studio",
    }
)


def build_discovery_headers(
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
        logger.debug(
            PROVIDER_DISCOVERY_FAILED,
            reason="oauth_discovery_unsupported",
            auth_type=config.auth_type.value,
        )
    return None


def infer_preset_hint(base_url: str) -> str | None:
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
    return PORT_TO_PRESET.get(port)
