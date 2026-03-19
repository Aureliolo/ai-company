"""Model auto-discovery for local LLM providers.

Queries provider endpoints to discover available models when a preset
is created with no explicit model list (e.g. Ollama, LM Studio, vLLM).
"""

from typing import Any

import httpx

from synthorg.config.schema import ProviderModelConfig
from synthorg.observability import get_logger
from synthorg.observability.events.provider import (
    PROVIDER_DISCOVERY_FAILED,
    PROVIDER_MODELS_DISCOVERED,
)

logger = get_logger(__name__)

_DISCOVERY_TIMEOUT_SECONDS = 10.0


async def discover_models(
    base_url: str,
    preset_name: str | None = None,
) -> tuple[ProviderModelConfig, ...]:
    """Discover available models from a provider endpoint.

    For Ollama presets, queries ``GET {base_url}/api/tags``.
    For OpenAI-compatible providers (LM Studio, vLLM, or unknown),
    queries ``GET {base_url}/models``.

    Args:
        base_url: Provider base URL (e.g. ``http://localhost:11434``).
        preset_name: Preset identifier hint for endpoint selection.

    Returns:
        Tuple of discovered model configs, or empty tuple on failure.
    """
    if preset_name == "ollama":
        return await _discover_ollama(base_url)
    return await _discover_openai_compatible(base_url, preset_name)


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


async def _discover_openai_compatible(
    base_url: str,
    preset_name: str | None,
) -> tuple[ProviderModelConfig, ...]:
    """Discover models from an OpenAI-compatible ``/models`` endpoint.

    Used for LM Studio, vLLM, and unknown providers.

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

    Args:
        url: Full URL to fetch.
        preset_name: Preset name for logging context.

    Returns:
        Parsed JSON dict, or ``None`` on any failure.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_DISCOVERY_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
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
    except Exception:
        logger.warning(
            PROVIDER_DISCOVERY_FAILED,
            preset=preset_name,
            reason="unexpected_error",
            url=url,
            exc_info=True,
        )
    return None
