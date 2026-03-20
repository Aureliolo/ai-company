"""Model auto-discovery for LLM providers.

Discovers available models from provider endpoints in two scenarios:
(1) auto-discovery when a preset is created with no explicit model list
(e.g. Ollama, LM Studio, vLLM), and (2) on-demand discovery for
existing providers via the ``POST /{name}/discover-models`` endpoint.
"""

import ipaddress
import json
import socket
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

    Allows http/https schemes only and blocks private/reserved IP
    addresses -- both literal IPs in the URL and resolved addresses
    for hostnames (DNS rebinding protection).  Hostnames like
    ``localhost`` are resolved via ``socket.getaddrinfo`` and checked
    against the same blocked-network list.

    Args:
        url: URL to validate.

    Returns:
        Error message if invalid, or None if safe.
    """
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return f"scheme {parsed.scheme!r} not allowed; use http or https"

    hostname = parsed.hostname
    if not hostname:
        return "URL has no hostname"

    return _check_blocked_address(hostname)


def _check_blocked_address(hostname: str) -> str | None:
    """Check whether a hostname resolves to a blocked network range.

    Handles both literal IPs and DNS names.

    Args:
        hostname: Hostname or IP address string.

    Returns:
        Error message if blocked, or None if safe.
    """
    # Fast path: literal IP address.
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        pass  # Not a literal IP -- resolve via DNS below.
    else:
        return _check_ip_blocked(addr, hostname)

    # Resolve hostname and check all returned addresses.
    return _check_resolved_hostname(hostname)


def _check_ip_blocked(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    label: str,
) -> str | None:
    """Check a single IP against blocked networks.

    Args:
        addr: IP address to check.
        label: Display label for error messages.

    Returns:
        Error message if blocked, or None if safe.
    """
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    for network in _BLOCKED_NETWORKS:
        if addr in network:
            return f"address {label!r} is in a blocked network range"
    return None


def _check_resolved_hostname(hostname: str) -> str | None:
    """Resolve a hostname and check all addresses against blocked networks.

    Args:
        hostname: DNS hostname to resolve.

    Returns:
        Error message if any resolved address is blocked, or None if safe.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return f"hostname {hostname!r} could not be resolved"

    for _, _, _, _, sockaddr in infos:
        try:
            addr = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        result = _check_ip_blocked(addr, hostname)
        if result is not None:
            return (
                f"hostname {hostname!r} resolves to {sockaddr[0]!r} in a blocked range"
            )

    return None


async def discover_models(
    base_url: str,
    preset_name: str | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[ProviderModelConfig, ...]:
    """Discover available models from a provider endpoint.

    For Ollama presets, queries ``GET {base_url}/api/tags``.
    For standard-API providers (LM Studio, vLLM, or unknown),
    queries ``GET {base_url}/models``.

    Args:
        base_url: Provider base URL (e.g. ``http://localhost:11434``
            for Ollama, ``http://localhost:1234/v1`` for LM Studio).
        preset_name: Preset identifier hint for endpoint selection.
        headers: Optional auth headers to include in the request.

    Returns:
        Tuple of discovered model configs, or empty tuple on failure.
    """
    if preset_name == "ollama":
        return await _discover_ollama(base_url, headers=headers)
    return await _discover_standard_api(base_url, preset_name, headers=headers)


async def _discover_ollama(
    base_url: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[ProviderModelConfig, ...]:
    """Discover models from Ollama's ``/api/tags`` endpoint.

    Args:
        base_url: Ollama server URL.
        headers: Optional auth headers.

    Returns:
        Discovered models, or empty tuple on failure.
    """
    url = f"{base_url.rstrip('/')}/api/tags"
    data = await _fetch_json(url, "ollama", headers=headers)
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
    skipped = 0
    for entry in raw_models:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            skipped += 1
            continue
        models.append(
            ProviderModelConfig(
                id=f"ollama/{name}",
            ),
        )

    if skipped and not models:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset="ollama",
            reason="all_entries_malformed",
            total_entries=len(raw_models),
            skipped=skipped,
        )
    elif skipped:
        logger.debug(
            PROVIDER_DISCOVERY_FAILED,
            preset="ollama",
            reason="some_entries_malformed",
            skipped=skipped,
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
    *,
    headers: dict[str, str] | None = None,
) -> tuple[ProviderModelConfig, ...]:
    """Discover models from a standard ``/models`` endpoint.

    Used for LM Studio, vLLM, and unknown providers that expose
    an ``/models`` listing endpoint.

    Args:
        base_url: Provider base URL.
        preset_name: Preset name for logging context.
        headers: Optional auth headers.

    Returns:
        Discovered models, or empty tuple on failure.
    """
    url = f"{base_url.rstrip('/')}/models"
    data = await _fetch_json(url, preset_name, headers=headers)
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
    skipped = 0
    for entry in raw_data:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            skipped += 1
            continue
        models.append(
            ProviderModelConfig(id=model_id),
        )

    if skipped and not models:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="all_entries_malformed",
            total_entries=len(raw_data),
            skipped=skipped,
        )
    elif skipped:
        logger.debug(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="some_entries_malformed",
            skipped=skipped,
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
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Fetch JSON from a URL with timeout and error handling.

    Validates the URL for SSRF safety before making the request.

    Args:
        url: Full URL to fetch.
        preset_name: Preset name for logging context.
        headers: Optional auth headers to include.

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
        return await _do_fetch_json(url, headers)
    except MemoryError, RecursionError:
        raise
    except httpx.HTTPStatusError as exc:
        reason = "http_error"
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason=reason,
            url=url,
            status_code=exc.response.status_code,
        )
    except httpx.ConnectError:
        _log_fetch_failure(preset_name, "connection_refused", url)
    except httpx.TimeoutException:
        _log_fetch_failure(preset_name, "timeout", url)
    except json.JSONDecodeError:
        _log_fetch_failure(preset_name, "invalid_json_response", url)
    except Exception:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="unexpected_error",
            url=url,
            exc_info=True,
        )
    return None


async def _do_fetch_json(
    url: str,
    headers: dict[str, str] | None,
) -> dict[str, Any] | None:
    """Execute the HTTP GET and parse JSON response.

    Args:
        url: URL to fetch.
        headers: Optional request headers.

    Returns:
        Parsed JSON dict, or ``None`` for non-dict responses.
    """
    async with httpx.AsyncClient(
        timeout=_DISCOVERY_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        response = await client.get(url, headers=headers or {})
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            logger.warning(
                PROVIDER_DISCOVERY_FAILED,
                preset=None,
                reason="unexpected_json_type",
                url=url,
            )
            return None
        return result


def _log_fetch_failure(
    preset_name: str | None,
    reason: str,
    url: str,
) -> None:
    """Log a discovery fetch failure with a standard structure."""
    logger.warning(
        PROVIDER_DISCOVERY_FAILED,
        preset=preset_name,
        reason=reason,
        url=url,
    )
