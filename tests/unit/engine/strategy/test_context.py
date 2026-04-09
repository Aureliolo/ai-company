"""Unit tests for strategic context providers."""

import pytest

from synthorg.engine.strategy.context import (
    CompositeContextProvider,
    ConfigContextProvider,
    MemoryContextProvider,
    build_context,
)
from synthorg.engine.strategy.models import (
    ContextSource,
    StrategicContextConfig,
    StrategyConfig,
)


class TestConfigContextProvider:
    """Tests for ConfigContextProvider."""

    @pytest.mark.unit
    def test_reads_from_config(self, default_strategy_config: StrategyConfig) -> None:
        provider = ConfigContextProvider()
        ctx = provider.provide(config=default_strategy_config)
        assert ctx.maturity_stage == "growth"
        assert ctx.industry == "technology"
        assert ctx.competitive_position == "challenger"

    @pytest.mark.unit
    def test_custom_config(self) -> None:
        config = StrategyConfig(
            context=StrategicContextConfig(
                maturity_stage="seed",
                industry="fintech",
                competitive_position="niche",
            ),
        )
        provider = ConfigContextProvider()
        ctx = provider.provide(config=config)
        assert ctx.maturity_stage == "seed"
        assert ctx.industry == "fintech"
        assert ctx.competitive_position == "niche"


class TestMemoryContextProvider:
    """Tests for MemoryContextProvider (placeholder)."""

    @pytest.mark.unit
    def test_falls_back_to_config(
        self,
        default_strategy_config: StrategyConfig,
    ) -> None:
        fallback = ConfigContextProvider()
        provider = MemoryContextProvider(fallback=fallback)
        ctx = provider.provide(config=default_strategy_config)
        assert ctx.maturity_stage == "growth"


class TestCompositeContextProvider:
    """Tests for CompositeContextProvider."""

    @pytest.mark.unit
    def test_returns_first_success(
        self,
        default_strategy_config: StrategyConfig,
    ) -> None:
        provider = CompositeContextProvider(
            providers=(ConfigContextProvider(),),
        )
        ctx = provider.provide(config=default_strategy_config)
        assert ctx.maturity_stage == "growth"

    @pytest.mark.unit
    def test_empty_providers_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            CompositeContextProvider(providers=())


class TestBuildContext:
    """Tests for the build_context convenience factory."""

    @pytest.mark.unit
    def test_config_source(self) -> None:
        config = StrategyConfig(
            context=StrategicContextConfig(source=ContextSource.CONFIG),
        )
        ctx = build_context(config)
        assert ctx.maturity_stage == "growth"

    @pytest.mark.unit
    def test_memory_source(self) -> None:
        config = StrategyConfig(
            context=StrategicContextConfig(source=ContextSource.MEMORY),
        )
        ctx = build_context(config)
        # Falls back to config since memory is a placeholder.
        assert ctx.maturity_stage == "growth"

    @pytest.mark.unit
    def test_composite_source(self) -> None:
        config = StrategyConfig(
            context=StrategicContextConfig(source=ContextSource.COMPOSITE),
        )
        ctx = build_context(config)
        assert ctx.maturity_stage == "growth"
