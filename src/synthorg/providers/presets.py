"""Pre-defined provider presets for common LLM backends.

Presets provide sensible defaults for popular providers so users
can add them with minimal configuration (e.g. just an API key).
"""

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from synthorg.config.schema import ProviderModelConfig  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.providers.enums import AuthType


class ProviderPreset(BaseModel):
    """Immutable preset definition for a provider.

    Attributes:
        name: Machine-readable preset identifier.
        display_name: Human-readable display name.
        description: Short description of the provider.
        driver: Driver backend name.
        auth_type: Required authentication type.
        default_base_url: Default API base URL.
        candidate_urls: URLs to probe during auto-detection, in priority
            order.  The first reachable URL becomes the base URL.
        default_models: Pre-configured model definitions.
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr
    display_name: NotBlankStr
    description: NotBlankStr
    driver: NotBlankStr
    auth_type: AuthType
    default_base_url: NotBlankStr | None = None
    candidate_urls: tuple[NotBlankStr, ...] = ()
    default_models: tuple[ProviderModelConfig, ...] = ()


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        name="ollama",
        display_name="Ollama",
        description="Local LLM inference server",
        driver="litellm",
        auth_type=AuthType.NONE,
        default_base_url="http://localhost:11434",
        candidate_urls=(
            "http://host.docker.internal:11434",
            "http://172.17.0.1:11434",
            "http://localhost:11434",
        ),
        default_models=(),
    ),
    ProviderPreset(
        name="lm-studio",
        display_name="LM Studio",
        description="Local LLM development environment",
        driver="litellm",
        auth_type=AuthType.NONE,
        default_base_url="http://localhost:1234/v1",
        candidate_urls=(
            "http://host.docker.internal:1234/v1",
            "http://172.17.0.1:1234/v1",
            "http://localhost:1234/v1",
        ),
        default_models=(),
    ),
    ProviderPreset(
        name="openrouter",
        display_name="OpenRouter",
        description="Multi-provider API gateway",
        driver="litellm",
        auth_type=AuthType.API_KEY,
        default_base_url="https://openrouter.ai/api/v1",
        default_models=(),
    ),
    ProviderPreset(
        name="vllm",
        display_name="vLLM",
        description="High-throughput local inference engine",
        driver="litellm",
        auth_type=AuthType.NONE,
        default_base_url="http://localhost:8000/v1",
        candidate_urls=(
            "http://host.docker.internal:8000/v1",
            "http://172.17.0.1:8000/v1",
            "http://localhost:8000/v1",
        ),
        default_models=(),
    ),
)

_PRESET_LOOKUP: MappingProxyType[str, ProviderPreset] = MappingProxyType(
    {p.name: p for p in PROVIDER_PRESETS},
)


def get_preset(name: str) -> ProviderPreset | None:
    """Look up a preset by name.

    Args:
        name: Preset identifier (e.g. ``"ollama"``).

    Returns:
        The matching preset, or ``None`` if not found.
    """
    return _PRESET_LOOKUP.get(name)


def list_presets() -> tuple[ProviderPreset, ...]:
    """Return all available presets.

    Returns:
        Tuple of all provider presets.
    """
    return PROVIDER_PRESETS
