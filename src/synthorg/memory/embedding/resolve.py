"""Embedder config resolution with priority chain.

Resolves a ``Mem0EmbedderConfig`` from the priority chain:

1. Settings override (runtime-editable via dashboard)
2. YAML config override (``CompanyMemoryConfig.embedder``)
3. Auto-selection from available models using LMEB rankings

Callers use ``resolve_embedder_config()`` instead of constructing
``Mem0EmbedderConfig`` manually.
"""

from synthorg.memory.backends.mem0.config import Mem0EmbedderConfig
from synthorg.memory.config import (
    CompanyMemoryConfig,  # noqa: TC001
    EmbedderOverrideConfig,  # noqa: TC001
)
from synthorg.memory.embedding.selector import (
    infer_deployment_tier,
    select_embedding_model,
)
from synthorg.memory.errors import MemoryConfigError
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_EMBEDDER_AUTO_SELECT_FAILED,
    MEMORY_EMBEDDER_AUTO_SELECTED,
)

logger = get_logger(__name__)


def _merge_override(
    override: EmbedderOverrideConfig | None,
    *,
    auto_provider: str | None,
    auto_model: str | None,
    auto_dims: int | None,
) -> tuple[str | None, str | None, int | None]:
    """Merge an override with auto-selected values.

    Override fields take precedence; ``None`` falls through to auto.
    """
    if override is None:
        return auto_provider, auto_model, auto_dims
    return (
        override.provider if override.provider is not None else auto_provider,
        override.model if override.model is not None else auto_model,
        override.dims if override.dims is not None else auto_dims,
    )


def resolve_embedder_config(
    memory_config: CompanyMemoryConfig,
    available_models: tuple[str, ...] = (),
    *,
    provider_preset_name: str | None = None,
    has_gpu: bool | None = None,
    settings_override: EmbedderOverrideConfig | None = None,
) -> Mem0EmbedderConfig:
    """Resolve the effective embedder configuration.

    Priority chain (highest first):

    1. ``settings_override`` (runtime settings from dashboard)
    2. ``memory_config.embedder`` (YAML config override)
    3. Auto-selection from ``available_models`` using LMEB rankings

    Args:
        memory_config: Company-wide memory configuration.
        available_models: Model identifiers discovered from the
            connected provider(s).
        provider_preset_name: Provider preset name for tier inference.
        has_gpu: Whether the host has a GPU (for tier inference).
        settings_override: Runtime settings override (highest priority).

    Returns:
        A fully-populated ``Mem0EmbedderConfig``.

    Raises:
        MemoryConfigError: If no embedding model can be resolved
            (no overrides and no LMEB match in available models).
    """
    # Auto-select from LMEB rankings as the base.
    auto_provider: str | None = None
    auto_model: str | None = None
    auto_dims: int | None = None

    tier = infer_deployment_tier(
        provider_preset_name,
        has_gpu=has_gpu,
    )
    # Try tier-filtered first, fall back to all tiers.
    ranking = select_embedding_model(
        available_models,
        deployment_tier=tier,
    )
    if ranking is None:
        ranking = select_embedding_model(available_models)
    if ranking is not None:
        auto_provider = ranking.model_id
        auto_model = ranking.model_id
        auto_dims = ranking.output_dims
        logger.info(
            MEMORY_EMBEDDER_AUTO_SELECTED,
            model_id=ranking.model_id,
            tier=tier.value,
            overall_score=ranking.overall,
            dims=ranking.output_dims,
        )

    # Apply YAML config override (second priority).
    provider, model, dims = _merge_override(
        memory_config.embedder,
        auto_provider=auto_provider,
        auto_model=auto_model,
        auto_dims=auto_dims,
    )

    # Apply settings override (highest priority).
    provider, model, dims = _merge_override(
        settings_override,
        auto_provider=provider,
        auto_model=model,
        auto_dims=dims,
    )

    if model is None or dims is None:
        logger.warning(
            MEMORY_EMBEDDER_AUTO_SELECT_FAILED,
            available_models=len(available_models),
            tier=tier.value,
            reason="no LMEB-ranked model available and no override",
        )
        msg = (
            "Could not resolve embedding model configuration: "
            "no LMEB-ranked model found in available models "
            "and no manual override provided"
        )
        raise MemoryConfigError(msg)

    if provider is None:
        provider = model

    return Mem0EmbedderConfig(
        provider=provider,
        model=model,
        dims=dims,
    )
