"""Model auto-discovery and URL probing for LLM providers.

Three capabilities:

1. Auto-discovery when a preset is created with no explicit model list
   (e.g. Ollama, LM Studio, vLLM).
2. On-demand discovery for existing providers via the
   ``POST /{name}/discover-models`` endpoint.
3. URL probing: given a preset's candidate URLs, tries each in
   priority order and returns the first reachable one with discovered
   model count (single round-trip per candidate).
"""

import asyncio
import ipaddress
import json
import socket
from typing import Any, Final, NamedTuple
from urllib.parse import urlparse, urlunparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from synthorg.config.schema import ProviderModelConfig
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.provider import (
    PROVIDER_DISCOVERY_FAILED,
    PROVIDER_MODELS_DISCOVERED,
    PROVIDER_PROBE_COMPLETED,
    PROVIDER_PROBE_HIT,
    PROVIDER_PROBE_MISS,
    PROVIDER_PROBE_STARTED,
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


class _SsrfCheckResult(NamedTuple):
    """Result of SSRF URL validation.

    Attributes:
        error: Error message if the URL is unsafe, or None if safe.
        pinned_ip: Resolved IP to connect to, preventing DNS rebinding
            between validation and the actual HTTP request.
    """

    error: str | None
    pinned_ip: str | None


def _redact_url(url: str) -> str:
    """Strip userinfo and query parameters from a URL for safe logging."""
    parsed = urlparse(url)
    safe_netloc = parsed.hostname or ""
    if parsed.port:
        safe_netloc = f"{safe_netloc}:{parsed.port}"
    redacted_query = "<redacted>" if parsed.query else ""
    return urlunparse(parsed._replace(netloc=safe_netloc, query=redacted_query))


async def _validate_discovery_url(url: str) -> _SsrfCheckResult:
    """Validate a URL for SSRF safety before making a discovery request.

    Allows http/https schemes only and blocks private/reserved IP
    addresses -- both literal IPs in the URL and resolved addresses
    for hostnames (DNS rebinding protection).  Hostnames like
    ``localhost`` are resolved via ``socket.getaddrinfo`` (offloaded
    to a thread executor to avoid blocking the event loop) and checked
    against the same blocked-network list.

    On success, returns the resolved IP so the caller can pin the
    connection to that address (preventing DNS rebinding between
    validation and the actual HTTP request).

    Args:
        url: URL to validate.

    Returns:
        Check result with error message or pinned IP.
    """
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return _SsrfCheckResult(
            f"scheme {parsed.scheme!r} not allowed; use http or https",
            None,
        )

    hostname = parsed.hostname
    if not hostname:
        return _SsrfCheckResult("URL has no hostname", None)

    return await _check_blocked_address(hostname)


async def _check_blocked_address(hostname: str) -> _SsrfCheckResult:
    """Check whether a hostname resolves to a blocked network range.

    Handles both literal IPs and DNS names.  DNS resolution is
    offloaded to a thread executor to avoid blocking the event loop.

    Args:
        hostname: Hostname or IP address string.

    Returns:
        Check result with error or the safe resolved IP.
    """
    # Fast path: literal IP address (no I/O).
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        pass  # Not a literal IP -- resolve via DNS below.
    else:
        return _check_ip_blocked(addr, hostname)

    # Resolve hostname and check all returned addresses.
    return await asyncio.to_thread(_check_resolved_hostname, hostname)


def _check_ip_blocked(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    label: str,
) -> _SsrfCheckResult:
    """Check a single IP against blocked networks.

    Args:
        addr: IP address to check.
        label: Display label for error messages.

    Returns:
        Check result with error or the safe IP string.
    """
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    for network in _BLOCKED_NETWORKS:
        if addr in network:
            return _SsrfCheckResult(
                f"address {label!r} is in a blocked network range",
                None,
            )
    return _SsrfCheckResult(None, str(addr))


def _check_resolved_hostname(hostname: str) -> _SsrfCheckResult:
    """Resolve a hostname and check all addresses against blocked networks.

    Args:
        hostname: DNS hostname to resolve.

    Returns:
        Check result with error or the first safe resolved IP.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return _SsrfCheckResult(
            f"hostname {hostname!r} could not be resolved",
            None,
        )

    for _, _, _, _, sockaddr in infos:
        try:
            addr = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        result = _check_ip_blocked(addr, hostname)
        if result.error is not None:
            return _SsrfCheckResult(
                f"hostname {hostname!r} resolves to {sockaddr[0]!r} in a blocked range",
                None,
            )
        # First safe address -- pin to it.
        return _SsrfCheckResult(None, str(addr))

    return _SsrfCheckResult(f"hostname {hostname!r} has no resolvable addresses", None)


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
            url=_redact_url(url),
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
            url=_redact_url(url),
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


def _build_pinned_url(
    original_url: str,
    pinned_ip: str,
) -> tuple[str, str]:
    """Build a URL with hostname replaced by a resolved IP.

    Args:
        original_url: Original URL with hostname.
        pinned_ip: Resolved IP address to connect to.

    Returns:
        Tuple of (pinned_url, original_hostname) for Host header.
    """
    parsed = urlparse(original_url)
    original_host = parsed.hostname or ""
    port = parsed.port
    # IPv6 literal must be bracketed in URLs.
    ip_part = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip
    pinned_netloc = f"{ip_part}:{port}" if port else ip_part
    pinned_url = urlunparse(parsed._replace(netloc=pinned_netloc))
    return pinned_url, original_host


async def _fetch_json(
    url: str,
    preset_name: str | None,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Fetch JSON from a URL with timeout and error handling.

    Validates the URL for SSRF safety before making the request.
    Uses the resolved IP from validation to pin the connection,
    preventing DNS rebinding between validation and the HTTP request.

    Args:
        url: Full URL to fetch.
        preset_name: Preset name for logging context.
        headers: Optional auth headers to include.

    Returns:
        Parsed JSON dict, or ``None`` on any failure.
    """
    safe_url = _redact_url(url)
    check = await _validate_discovery_url(url)
    if check.error is not None:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="blocked_url",
            url=safe_url,
            detail=check.error,
        )
        return None

    # Pin connection to the validated IP to prevent DNS rebinding.
    pinned_ip = check.pinned_ip
    if pinned_ip is None:
        # Defensive: should not happen when error is None.
        logger.error(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="ssrf_check_inconsistency",
            url=safe_url,
            detail="SSRF check passed but returned no pinned IP",
        )
        return None
    pinned_url, original_host = _build_pinned_url(url, pinned_ip)

    try:
        return await _do_fetch_json(
            pinned_url,
            headers,
            host_header=original_host,
            preset_name=preset_name,
        )
    except MemoryError, RecursionError:
        raise
    except httpx.HTTPStatusError as exc:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="http_error",
            url=safe_url,
            status_code=exc.response.status_code,
        )
    except httpx.ConnectError:
        _log_fetch_failure(preset_name, "connection_refused", safe_url)
    except httpx.TimeoutException:
        _log_fetch_failure(preset_name, "timeout", safe_url)
    except json.JSONDecodeError:
        _log_fetch_failure(preset_name, "invalid_json_response", safe_url)
    except Exception:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="unexpected_error",
            url=safe_url,
            exc_info=True,
        )
    return None


async def _do_fetch_json(
    url: str,
    headers: dict[str, str] | None,
    *,
    host_header: str = "",
    preset_name: str | None = None,
) -> dict[str, Any] | None:
    """Execute the HTTP GET and parse JSON response.

    Args:
        url: URL to fetch (may be IP-pinned).
        headers: Optional request headers.
        host_header: Original hostname for the Host header (when
            the URL has been rewritten with a pinned IP).
        preset_name: Preset name for logging context.

    Returns:
        Parsed JSON dict, or ``None`` for non-dict responses.
    """
    merged_headers: dict[str, str] = {**(headers or {})}
    if host_header:
        merged_headers["Host"] = host_header
    async with httpx.AsyncClient(
        timeout=_DISCOVERY_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        response = await client.get(url, headers=merged_headers)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            logger.warning(
                PROVIDER_DISCOVERY_FAILED,
                preset=preset_name,
                reason="unexpected_json_type",
                url=_redact_url(url),
            )
            return None
        return result


def _log_fetch_failure(
    preset_name: str | None,
    reason: str,
    safe_url: str,
) -> None:
    """Log a discovery fetch failure with a standard structure."""
    logger.warning(
        PROVIDER_DISCOVERY_FAILED,
        preset=preset_name,
        reason=reason,
        url=safe_url,
    )


# ── Probe: try candidate URLs for a preset ──────────────────

_PROBE_TIMEOUT_SECONDS: Final[float] = 5.0


class ProbeResult(BaseModel):
    """Result of probing a preset's candidate URLs.

    Attributes:
        url: The reachable base URL, or ``None`` if all failed.
        model_count: Number of models discovered at the URL.
        candidates_tried: Number of candidate URLs attempted.
    """

    model_config = ConfigDict(frozen=True)

    url: NotBlankStr | None = None
    model_count: int = Field(default=0, ge=0)
    candidates_tried: int = Field(default=0, ge=0)


def _log_probe_miss(
    preset_name: str,
    reason: str,
    url: str,
    *,
    status_code: int | None = None,
    exc_info: bool = False,
) -> None:
    """Log a probe miss at DEBUG (or WARNING for unexpected errors).

    Args:
        preset_name: Preset name for context.
        reason: Short reason tag.
        url: URL that was probed (will be redacted).
        status_code: HTTP status code, if applicable.
        exc_info: Whether to include traceback.
    """
    level = logger.warning if exc_info else logger.debug
    kwargs: dict[str, Any] = {
        "preset": preset_name,
        "reason": reason,
        "url": _redact_url(url),
    }
    if status_code is not None:
        kwargs["status_code"] = status_code
    level(PROVIDER_PROBE_MISS, exc_info=exc_info, **kwargs)


async def _probe_and_fetch(
    url: str,
    preset_name: str,
) -> dict[str, Any] | None:
    """Probe a URL and return its JSON body in a single request.

    Uses a short timeout and does not validate SSRF -- the caller
    is responsible for using only preset-defined candidate URLs.
    Candidate URLs must come from the hardcoded preset definitions
    in ``presets.py`` (``PROVIDER_PRESETS``), never from user input.

    Args:
        url: Full URL to probe (model-listing endpoint --
            ``/api/tags`` for Ollama, ``/models`` for standard API).
        preset_name: Preset name for logging context.

    Returns:
        Parsed JSON dict on 2xx success, ``None`` otherwise.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_PROBE_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            response = await client.get(url)
            if not response.is_success:
                _log_probe_miss(
                    preset_name,
                    "http_error",
                    url,
                    status_code=response.status_code,
                )
                return None
            data = response.json()
            if not isinstance(data, dict):
                _log_probe_miss(preset_name, "unexpected_json_type", url)
                return None
            return data
    except MemoryError, RecursionError:
        raise
    except httpx.ConnectError:
        _log_probe_miss(preset_name, "connection_refused", url)
    except httpx.TimeoutException:
        _log_probe_miss(preset_name, "timeout", url)
    except json.JSONDecodeError:
        _log_probe_miss(preset_name, "invalid_json", url)
    except Exception:
        _log_probe_miss(preset_name, "unexpected_error", url, exc_info=True)
    return None


def _build_probe_endpoint(base_url: str, preset_name: str) -> str:
    """Build the model-listing endpoint URL for probing.

    Args:
        base_url: Provider base URL.
        preset_name: Preset name (determines endpoint path).

    Returns:
        Full URL to the model-listing endpoint.
    """
    stripped = base_url.rstrip("/")
    if preset_name == "ollama":
        return f"{stripped}/api/tags"
    return f"{stripped}/models"


def _build_probe_hit(
    data: dict[str, Any],
    url: str,
    idx: int,
    preset_name: str,
) -> ProbeResult | None:
    """Build a probe result from fetched data, or ``None`` on parse failure.

    If the JSON does not match the expected provider schema (e.g. an
    unrelated health-check response), this returns ``None`` so the
    caller continues probing the next candidate URL.

    Args:
        data: Parsed JSON response body.
        url: The reachable base URL.
        idx: 1-based index of this candidate in the list.
        preset_name: Preset name for parser selection and logging.

    Returns:
        Probe result on success, ``None`` if the payload is not a
        recognizable model-listing response.
    """
    if preset_name == "ollama":
        models = _parse_ollama_models(data)
    else:
        models = _parse_standard_models(data)

    if models is None:
        _log_probe_miss(preset_name, "unrecognized_schema", url)
        return None

    logger.info(
        PROVIDER_PROBE_HIT,
        preset=preset_name,
        url=_redact_url(url),
    )
    result = ProbeResult(
        url=url,
        model_count=len(models),
        candidates_tried=idx,
    )
    logger.info(
        PROVIDER_PROBE_COMPLETED,
        preset=preset_name,
        url=_redact_url(url),
        model_count=result.model_count,
        candidates_tried=result.candidates_tried,
    )
    return result


async def probe_preset_urls(
    candidate_urls: tuple[str, ...],
    preset_name: str,
) -> ProbeResult:
    """Probe candidate URLs for a preset and return the first reachable one.

    Tries each URL sequentially (short timeout per URL). For the first
    URL that responds, parses the model list from the same response
    (single round-trip per candidate).

    SSRF validation is intentionally skipped here because candidate URLs
    come from the hardcoded preset definitions (``PROVIDER_PRESETS`` in
    ``presets.py``), not user input.  The caller must validate the preset
    name against the preset registry before passing ``candidate_urls``
    to this function.

    Args:
        candidate_urls: URLs to probe in priority order.
        preset_name: Preset name for discovery endpoint selection
            and logging.

    Returns:
        Probe result with the reachable URL and model count,
        or an empty result if no URL responded.
    """
    logger.info(
        PROVIDER_PROBE_STARTED,
        preset=preset_name,
        candidate_count=len(candidate_urls),
    )

    for idx, url in enumerate(candidate_urls, start=1):
        probe_endpoint = _build_probe_endpoint(url, preset_name)

        data = await _probe_and_fetch(probe_endpoint, preset_name)
        if data is None:
            continue

        result = _build_probe_hit(data, url, idx, preset_name)
        if result is not None:
            return result

    logger.info(
        PROVIDER_PROBE_COMPLETED,
        preset=preset_name,
        url=None,
        model_count=0,
        candidates_tried=len(candidate_urls),
    )
    return ProbeResult(candidates_tried=len(candidate_urls))


def _parse_ollama_models(
    data: dict[str, Any],
) -> tuple[ProviderModelConfig, ...] | None:
    """Parse Ollama model list response.

    Args:
        data: Parsed JSON response from ``/api/tags``.

    Returns:
        Tuple of model configs, or ``None`` if the response does not
        contain a ``models`` list (unrecognized schema).
    """
    raw_models = data.get("models")
    if not isinstance(raw_models, list):
        return None
    models: list[ProviderModelConfig] = []
    for entry in raw_models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        models.append(ProviderModelConfig(id=f"ollama/{name}"))
    return tuple(models)


def _parse_standard_models(
    data: dict[str, Any],
) -> tuple[ProviderModelConfig, ...] | None:
    """Parse standard ``/models`` list response.

    Args:
        data: Parsed JSON response from ``/models``.

    Returns:
        Tuple of model configs, or ``None`` if the response does not
        contain a ``data`` list (unrecognized schema).
    """
    raw_data = data.get("data")
    if not isinstance(raw_data, list):
        return None
    models: list[ProviderModelConfig] = []
    for entry in raw_data:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        models.append(ProviderModelConfig(id=model_id))
    return tuple(models)
