"""Provider-specific response DTOs.

Split from ``dto.py`` to keep that file under the 800-line limit.
"""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.config.schema import ProviderModelConfig  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.providers.capabilities import ModelCapabilities  # noqa: TC001


class ProviderModelResponse(BaseModel):
    """Model config enriched with runtime capabilities.

    Attributes:
        id: Model identifier.
        alias: Short alias for routing rules.
        cost_per_1k_input: Cost per 1k input tokens.
        cost_per_1k_output: Cost per 1k output tokens.
        max_context: Maximum context window size in tokens.
        estimated_latency_ms: Estimated median latency in milliseconds.
        supports_tools: Whether the model supports tool/function calling.
        supports_vision: Whether the model accepts image inputs.
        supports_streaming: Whether the model supports streaming responses.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: NotBlankStr = Field(description="Model identifier")
    alias: NotBlankStr | None = Field(
        default=None,
        description="Short alias for routing rules",
    )
    cost_per_1k_input: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per 1k input tokens",
    )
    cost_per_1k_output: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per 1k output tokens",
    )
    max_context: int = Field(
        default=200_000,
        gt=0,
        description="Max context window in tokens",
    )
    estimated_latency_ms: int | None = Field(
        default=None,
        gt=0,
        le=300_000,
        description="Estimated median latency in ms",
    )
    supports_tools: bool = Field(
        default=False,
        description="Supports tool/function calling",
    )
    supports_vision: bool = Field(
        default=False,
        description="Accepts image inputs",
    )
    supports_streaming: bool = Field(
        default=True,
        description="Supports streaming responses",
    )


def to_provider_model_response(
    config: ProviderModelConfig,
    capabilities: ModelCapabilities | None = None,
) -> ProviderModelResponse:
    """Convert a ProviderModelConfig to an enriched response.

    When *capabilities* is provided, capability booleans are overlaid.
    Otherwise, defaults are used.

    Args:
        config: Model configuration from provider config.
        capabilities: Runtime capabilities from the driver layer.

    Returns:
        Enriched model response DTO.
    """
    return ProviderModelResponse(
        id=config.id,
        alias=config.alias,
        cost_per_1k_input=config.cost_per_1k_input,
        cost_per_1k_output=config.cost_per_1k_output,
        max_context=config.max_context,
        estimated_latency_ms=config.estimated_latency_ms,
        supports_tools=(
            capabilities.supports_tools if capabilities is not None else False
        ),
        supports_vision=(
            capabilities.supports_vision if capabilities is not None else False
        ),
        supports_streaming=(
            capabilities.supports_streaming if capabilities is not None else True
        ),
    )
