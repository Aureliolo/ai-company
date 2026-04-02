"""Embedding model selection based on LMEB rankings.

Provides auto-selection of embedding models from connected providers
using LMEB (Long-horizon Memory Embedding Benchmark) scores, with
deployment tier inference and configurable overrides.
"""

from synthorg.memory.embedding.rankings import (
    LMEB_RANKINGS,
    DeploymentTier,
    EmbeddingModelRanking,
)
from synthorg.memory.embedding.resolve import resolve_embedder_config
from synthorg.memory.embedding.selector import (
    infer_deployment_tier,
    select_embedding_model,
)

__all__ = [
    "LMEB_RANKINGS",
    "DeploymentTier",
    "EmbeddingModelRanking",
    "infer_deployment_tier",
    "resolve_embedder_config",
    "select_embedding_model",
]
