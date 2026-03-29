"""Pre-defined provider presets for common LLM backends.

Presets provide sensible defaults for popular providers so users
can add them with minimal configuration (e.g. just an API key).
"""

import re
from types import MappingProxyType
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.config.schema import ProviderModelConfig
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.providers.enums import AuthType


class ProviderPreset(BaseModel):
    """Immutable preset definition for a provider.

    Attributes:
        name: Machine-readable preset identifier.
        display_name: Human-readable display name.
        description: Short description of the provider.
        driver: Driver backend name.
        litellm_provider: LiteLLM routing identifier (e.g. ``"anthropic"``).
        auth_type: Default authentication type.
        supported_auth_types: All auth types this preset supports.
            Shown in the UI so users can choose (e.g. API key or
            subscription for Anthropic).
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
    litellm_provider: NotBlankStr
    auth_type: AuthType
    supported_auth_types: tuple[AuthType, ...] = Field(
        default=(AuthType.API_KEY,),
        min_length=1,
    )
    default_base_url: NotBlankStr | None = None
    candidate_urls: tuple[NotBlankStr, ...] = ()
    default_models: tuple[ProviderModelConfig, ...] = ()

    @model_validator(mode="after")
    def _validate_auth_type_in_supported(self) -> Self:
        """Ensure default auth_type is in the supported set."""
        if self.auth_type not in self.supported_auth_types:
            msg = (
                f"auth_type {self.auth_type!r} not in "
                f"supported_auth_types {self.supported_auth_types!r}"
            )
            raise ValueError(msg)
        return self


# ── Cloud providers ────────────────────────────────────────────

_ANTHROPIC = ProviderPreset(
    name="anthropic",
    display_name="Anthropic",
    description="Claude models (Opus, Sonnet, Haiku)",
    driver="litellm",
    litellm_provider="anthropic",
    auth_type=AuthType.API_KEY,
    supported_auth_types=(AuthType.API_KEY, AuthType.SUBSCRIPTION),
    default_models=(
        ProviderModelConfig(
            id="claude-sonnet-4-6-20250514",
            alias="sonnet",
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            max_context=200_000,
        ),
        ProviderModelConfig(
            id="claude-haiku-4-5-20251001",
            alias="haiku",
            cost_per_1k_input=0.0008,
            cost_per_1k_output=0.004,
            max_context=200_000,
        ),
    ),
)

_OPENAI = ProviderPreset(
    name="openai",
    display_name="OpenAI",
    description="GPT and o-series models",
    driver="litellm",
    litellm_provider="openai",
    auth_type=AuthType.API_KEY,
    supported_auth_types=(AuthType.API_KEY,),
    default_models=(
        ProviderModelConfig(
            id="gpt-4.1",
            alias="gpt4",
            cost_per_1k_input=0.002,
            cost_per_1k_output=0.008,
            max_context=1_047_576,
        ),
        ProviderModelConfig(
            id="gpt-4.1-mini",
            alias="gpt4-mini",
            cost_per_1k_input=0.0004,
            cost_per_1k_output=0.0016,
            max_context=1_047_576,
        ),
        ProviderModelConfig(
            id="o3",
            alias="o3",
            cost_per_1k_input=0.002,
            cost_per_1k_output=0.008,
            max_context=200_000,
        ),
    ),
)

_GEMINI = ProviderPreset(
    name="gemini",
    display_name="Google AI Studio",
    description="Gemini models via Google AI",
    driver="litellm",
    litellm_provider="gemini",
    auth_type=AuthType.API_KEY,
    supported_auth_types=(AuthType.API_KEY,),
    default_models=(
        ProviderModelConfig(
            id="gemini-2.5-pro",
            alias="gemini-pro",
            cost_per_1k_input=0.00125,
            cost_per_1k_output=0.01,
            max_context=1_048_576,
        ),
        ProviderModelConfig(
            id="gemini-2.5-flash",
            alias="gemini-flash",
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            max_context=1_048_576,
        ),
    ),
)

_MISTRAL = ProviderPreset(
    name="mistral",
    display_name="Mistral AI",
    description="Mistral and Codestral models",
    driver="litellm",
    litellm_provider="mistral",
    auth_type=AuthType.API_KEY,
    supported_auth_types=(AuthType.API_KEY,),
    default_models=(),
)

_GROQ = ProviderPreset(
    name="groq",
    display_name="Groq",
    description="Ultra-fast inference (LPU)",
    driver="litellm",
    litellm_provider="groq",
    auth_type=AuthType.API_KEY,
    supported_auth_types=(AuthType.API_KEY,),
    default_models=(),
)

_DEEPSEEK = ProviderPreset(
    name="deepseek",
    display_name="DeepSeek",
    description="DeepSeek reasoning and chat models",
    driver="litellm",
    litellm_provider="deepseek",
    auth_type=AuthType.API_KEY,
    supported_auth_types=(AuthType.API_KEY,),
    default_models=(),
)

_AZURE_OPENAI = ProviderPreset(
    name="azure",
    display_name="Azure OpenAI",
    description="OpenAI models via Azure",
    driver="litellm",
    litellm_provider="azure",
    auth_type=AuthType.API_KEY,
    supported_auth_types=(AuthType.API_KEY,),
    # Azure requires a per-deployment base_url
    default_base_url=None,
    default_models=(),
)

# ── Self-hosted / local ────────────────────────────────────────

_OLLAMA = ProviderPreset(
    name="ollama",
    display_name="Ollama",
    description="Local LLM inference server",
    driver="litellm",
    litellm_provider="ollama",
    auth_type=AuthType.NONE,
    supported_auth_types=(AuthType.NONE,),
    default_base_url="http://localhost:11434",
    candidate_urls=(
        "http://host.docker.internal:11434",
        "http://172.17.0.1:11434",
        "http://localhost:11434",
    ),
    default_models=(),
)

_LM_STUDIO = ProviderPreset(
    name="lm-studio",
    display_name="LM Studio",
    description="Local LLM development environment",
    driver="litellm",
    litellm_provider="openai",
    auth_type=AuthType.NONE,
    supported_auth_types=(AuthType.NONE,),
    default_base_url="http://localhost:1234/v1",
    candidate_urls=(
        "http://host.docker.internal:1234/v1",
        "http://172.17.0.1:1234/v1",
        "http://localhost:1234/v1",
    ),
    default_models=(),
)

_VLLM = ProviderPreset(
    name="vllm",
    display_name="vLLM",
    description="High-throughput local inference engine",
    driver="litellm",
    litellm_provider="openai",
    auth_type=AuthType.NONE,
    supported_auth_types=(AuthType.NONE,),
    default_base_url="http://localhost:8000/v1",
    # candidate_urls intentionally empty: vLLM's default port (8000)
    # is a common collision risk (the SynthOrg backend formerly used
    # 8000).  Users must specify the vLLM URL explicitly or remap
    # vLLM to a non-colliding port.
    default_models=(),
)

# ── Gateways ───────────────────────────────────────────────────

_OPENROUTER = ProviderPreset(
    name="openrouter",
    display_name="OpenRouter",
    description="Multi-provider API gateway",
    driver="litellm",
    litellm_provider="openrouter",
    auth_type=AuthType.API_KEY,
    supported_auth_types=(AuthType.API_KEY,),
    default_base_url="https://openrouter.ai/api/v1",
    default_models=(),
)


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    # Cloud (alphabetical)
    _ANTHROPIC,
    _AZURE_OPENAI,
    _DEEPSEEK,
    _GEMINI,
    _GROQ,
    _MISTRAL,
    _OPENAI,
    # Self-hosted
    _LM_STUDIO,
    _OLLAMA,
    _VLLM,
    # Gateways
    _OPENROUTER,
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


# ── Model generation filters ─────────────────────────────────
# Provider-specific model generation allowlists for
# ``models_from_litellm()``.  Only models matching the pattern
# are included.  Providers not listed here include all models.
# Patterns must be updated when new major generations are released.
# Vendor-specific names are allowed here per CLAUDE.md:
# "provider presets (presets.py) which are user-facing runtime data".

MODEL_VERSION_FILTERS: Final[MappingProxyType[str, re.Pattern[str]]] = MappingProxyType(
    {
        "anthropic": re.compile(r"^claude-(opus|sonnet|haiku)-4-[56789]"),
    }
)
