"""Model auto-discovery for local LLM providers.

Queries provider endpoints to discover available models when a preset
is created with no explicit model list (e.g. Ollama, LM Studio, vLLM).
"""

import ipaddress
import json
from typing import Any, Final
from urllib.parse import urlparse

import httpx

from synthorg.config.schema import ProviderModelConfig
from synthorg.observability import get_logger
from synthorg.observability.events.provider import (
    PROVIDER_DISCOVERY_FAILED,
    PROVIDER_MODELS_DISCOVERED,
)

logger = get_logger(__name__)

_DISCOVERY_TIMEOUT_SECONDS: Final[float] = 10.0

_ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})

# Private, loopback, link-local, and reserved networks.
_BLOCKED_NETWORKS: Final[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]] = (
    ipaddress.IPv4Network("0.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("100.64.0.0/10"),
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.0.0.0/24"),
    ipaddress.IPv4Network("192.0.2.0/24"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv6Network("::/128"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("fe80::/10"),
)


def _validate_discovery_url(url: str) -> str | None:
    """Validate a URL for SSRF safety before making a discovery request.

    Only allows http/https schemes and rejects literal private IPs.

    Args:
        url: URL to validate.

    Returns:
        Error message if invalid, or None if safe.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return "unparseable URL"

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return f"scheme {parsed.scheme!r} not allowed; use http or https"

    hostname = parsed.hostname
    if not hostname:
        return "URL has no hostname"

    try:
        addr = ipaddress.ip_address(hostname)
        # Unwrap IPv6-mapped IPv4 for consistent checking.
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                return f"address {hostname!r} is in a blocked network range"
    except ValueError:
        pass  # Not a literal IP -- hostname will be resolved by httpx.

    return None


async def discover_models(
    base_url: str,
    preset_name: str | None = None,
) -> tuple[ProviderModelConfig, ...]:
    """Discover available models from a provider endpoint.

    For Ollama presets, queries ``GET {base_url}/api/tags``.
    For standard-API providers (LM Studio, vLLM, or unknown),
    queries ``GET {base_url}/models``.

    Args:
        base_url: Provider base URL (e.g. ``http://localhost:11434``
            for Ollama, ``http://localhost:1234/v1`` for LM Studio).
        preset_name: Preset identifier hint for endpoint selection.

    Returns:
        Tuple of discovered model configs, or empty tuple on failure.
    """
    if preset_name == "ollama":
        return await _discover_ollama(base_url)
    return await _discover_standard_api(base_url, preset_name)


async def _discover_ollama(
    base_url: str,
) -> tuple[ProviderModelConfig, ...]:
    """Discover models from Ollama's ``/api/tags`` endpoint.

    Args:
        base_url: Ollama server URL.

    Returns:
        Discovered models, or empty tuple on failure.
    """
    url = f"{base_url.rstrip('/')}/api/tags"
    data = await _fetch_json(url, "ollama")
    if data is None:
        return ()

    raw_models = data.get("models")
    if not isinstance(raw_models, list):
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset="ollama",
            reason="unexpected_response_structure",
            url=url,
        )
        return ()

    models: list[ProviderModelConfig] = []
    for entry in raw_models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        models.append(
            ProviderModelConfig(
                id=f"ollama/{name}",
            ),
        )

    logger.info(
        PROVIDER_MODELS_DISCOVERED,
        preset="ollama",
        model_count=len(models),
    )
    return tuple(models)


async def _discover_standard_api(
    base_url: str,
    preset_name: str | None,
) -> tuple[ProviderModelConfig, ...]:
    """Discover models from a standard ``/models`` endpoint.

    Used for LM Studio, vLLM, and unknown providers that expose
    an ``/models`` listing endpoint.

    Args:
        base_url: Provider base URL.
        preset_name: Preset name for logging context.

    Returns:
        Discovered models, or empty tuple on failure.
    """
    url = f"{base_url.rstrip('/')}/models"
    data = await _fetch_json(url, preset_name)
    if data is None:
        return ()

    raw_data = data.get("data")
    if not isinstance(raw_data, list):
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="unexpected_response_structure",
            url=url,
        )
        return ()

    models: list[ProviderModelConfig] = []
    for entry in raw_data:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        models.append(
            ProviderModelConfig(id=model_id),
        )

    logger.info(
        PROVIDER_MODELS_DISCOVERED,
        preset=preset_name,
        model_count=len(models),
    )
    return tuple(models)


async def _fetch_json(
    url: str,
    preset_name: str | None,
) -> dict[str, Any] | None:
    """Fetch JSON from a URL with timeout and error handling.

    Validates the URL for SSRF safety before making the request.

    Args:
        url: Full URL to fetch.
        preset_name: Preset name for logging context.

    Returns:
        Parsed JSON dict, or ``None`` on any failure.
    """
    ssrf_error = _validate_discovery_url(url)
    if ssrf_error:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="blocked_url",
            url=url,
            detail=ssrf_error,
        )
        return None

    try:
        async with httpx.AsyncClient(
            timeout=_DISCOVERY_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                logger.warning(
                    PROVIDER_DISCOVERY_FAILED,
                    preset=preset_name,
                    reason="unexpected_json_type",
                    url=url,
                )
                return None
            return result
    except httpx.ConnectError:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="connection_refused",
            url=url,
        )
    except httpx.TimeoutException:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="timeout",
            url=url,
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="http_error",
            url=url,
            status_code=exc.response.status_code,
        )
    except json.JSONDecodeError:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="invalid_json_response",
            url=url,
        )
    except Exception:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="unexpected_error",
            url=url,
            exc_info=True,
        )
    return None
