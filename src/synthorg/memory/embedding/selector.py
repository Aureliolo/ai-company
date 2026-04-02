"""Embedding model selection from available models using LMEB rankings.

Provides two functions:

- ``select_embedding_model``: intersects discovered models with LMEB
  rankings and returns the highest-ranked match.
- ``infer_deployment_tier``: infers the deployment tier from the
  provider preset name and GPU availability.
"""

from synthorg.memory.embedding.rankings import (
    LMEB_RANKINGS,
    DeploymentTier,
    EmbeddingModelRanking,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)

# Provider preset names that indicate local/self-hosted deployment.
_LOCAL_PRESETS: frozenset[str] = frozenset(
    {
        "ollama",
        "lm-studio",
        "vllm",
    }
)


def select_embedding_model(
    available_models: tuple[str, ...],
    *,
    deployment_tier: DeploymentTier | None = None,
) -> EmbeddingModelRanking | None:
    """Select the best embedding model from available models.

    Intersects the LMEB-ranked models with ``available_models``
    using case-insensitive substring matching (Ollama model names
    include version tags like ``:latest``).  Returns the
    highest-ranked match, or ``None`` if no LMEB-ranked model is
    available.

    Args:
        available_models: Model identifiers discovered from the
            provider (e.g. via ``/api/tags`` or ``/models``).
        deployment_tier: Optional tier filter.  When set, only
            models from the specified tier are considered.

    Returns:
        The highest-ranked matching model, or ``None``.
    """
    candidates = LMEB_RANKINGS
    if deployment_tier is not None:
        candidates = tuple(r for r in candidates if r.tier == deployment_tier)
    available_lower = tuple(m.lower() for m in available_models)
    for ranking in candidates:
        ranking_id_lower = ranking.model_id.lower()
        for available in available_lower:
            if ranking_id_lower in available or available in ranking_id_lower:
                return ranking
    return None


def infer_deployment_tier(
    provider_preset_name: str | None,
    *,
    has_gpu: bool | None = None,
) -> DeploymentTier:
    """Infer the deployment tier from provider context.

    Args:
        provider_preset_name: Provider preset identifier (e.g.
            ``"ollama"``, ``"lm-studio"``).  ``None`` or unknown
            names default to ``GPU_CONSUMER``.
        has_gpu: Whether the host has a GPU.  Only meaningful for
            local providers.  ``None`` means unknown (assumes GPU
            available for local providers).

    Returns:
        The inferred deployment tier.
    """
    if provider_preset_name is None:
        return DeploymentTier.GPU_CONSUMER
    name_lower = provider_preset_name.lower()
    if name_lower in _LOCAL_PRESETS:
        if has_gpu is False:
            return DeploymentTier.CPU
        return DeploymentTier.GPU_CONSUMER
    return DeploymentTier.GPU_FULL
