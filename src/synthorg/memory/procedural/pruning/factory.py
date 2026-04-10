"""Factory for building pruning strategies from configuration."""

from typing import TYPE_CHECKING

from synthorg.memory.procedural.pruning.hybrid_strategy import (
    HybridPruningStrategy,
)
from synthorg.memory.procedural.pruning.pareto_strategy import (
    ParetoPruningStrategy,
)
from synthorg.memory.procedural.pruning.ttl_strategy import TtlPruningStrategy
from synthorg.observability import get_logger
from synthorg.observability.events.procedural_memory import (
    PROCEDURAL_PRUNING_UNKNOWN_TYPE,
)

if TYPE_CHECKING:
    from synthorg.memory.procedural.pruning.config import PruningConfig
    from synthorg.memory.procedural.pruning.protocol import PruningStrategy

logger = get_logger(__name__)


def build_pruning_strategy(config: PruningConfig) -> PruningStrategy:
    """Build a pruning strategy from configuration.

    Args:
        config: Pruning strategy configuration.

    Returns:
        Configured pruning strategy instance.

    Raises:
        ValueError: If strategy type is unknown.
    """
    if config.type == "ttl":
        return TtlPruningStrategy(max_age_days=config.max_age_days)
    if config.type == "pareto":
        return ParetoPruningStrategy(max_entries=config.max_entries)
    if config.type == "hybrid":
        ttl = TtlPruningStrategy(max_age_days=config.max_age_days)
        pareto = ParetoPruningStrategy(max_entries=config.max_entries)
        return HybridPruningStrategy(ttl_strategy=ttl, pareto_strategy=pareto)
    msg = f"Unknown pruning strategy type: {config.type}"  # type: ignore[unreachable]
    logger.warning(PROCEDURAL_PRUNING_UNKNOWN_TYPE, type=config.type)
    raise ValueError(msg)
