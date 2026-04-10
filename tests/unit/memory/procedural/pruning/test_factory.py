"""Tests for pruning strategy factory."""

import pytest

from synthorg.memory.procedural.pruning.config import PruningConfig
from synthorg.memory.procedural.pruning.factory import build_pruning_strategy
from synthorg.memory.procedural.pruning.hybrid_strategy import (
    HybridPruningStrategy,
)
from synthorg.memory.procedural.pruning.pareto_strategy import (
    ParetoPruningStrategy,
)
from synthorg.memory.procedural.pruning.ttl_strategy import (
    TtlPruningStrategy,
)


@pytest.mark.unit
class TestBuildPruningStrategy:
    """build_pruning_strategy dispatches on config type."""

    def test_ttl_type(self) -> None:
        config = PruningConfig(type="ttl")
        strategy = build_pruning_strategy(config)
        assert isinstance(strategy, TtlPruningStrategy)

    def test_pareto_type(self) -> None:
        config = PruningConfig(type="pareto")
        strategy = build_pruning_strategy(config)
        assert isinstance(strategy, ParetoPruningStrategy)

    def test_hybrid_type(self) -> None:
        config = PruningConfig(type="hybrid")
        strategy = build_pruning_strategy(config)
        assert isinstance(strategy, HybridPruningStrategy)

    def test_default_is_ttl(self) -> None:
        config = PruningConfig()
        strategy = build_pruning_strategy(config)
        assert isinstance(strategy, TtlPruningStrategy)
