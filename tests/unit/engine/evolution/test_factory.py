"""Tests for evolution factory assembly."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.engine.evolution.config import (
    EvolutionConfig,
    ProposerConfig,
    TriggerConfig,
)
from synthorg.engine.evolution.factory import build_evolution_service
from synthorg.engine.evolution.service import EvolutionService
from synthorg.hr.performance.tracker import PerformanceTracker
from synthorg.hr.registry import AgentRegistryService
from synthorg.versioning.service import VersioningService


def _build_service(
    config: EvolutionConfig | None = None,
    *,
    provider: MagicMock | None = None,
) -> EvolutionService:
    """Build a service from config with mock dependencies."""
    if config is None:
        config = EvolutionConfig()
    repo = AsyncMock()
    return build_evolution_service(
        config,
        registry=AgentRegistryService(),
        versioning=VersioningService(repo),
        tracker=PerformanceTracker(),
        provider=provider,
    )


class TestBuildEvolutionService:
    """build_evolution_service creates a valid service."""

    @pytest.mark.unit
    def test_default_config_builds(self) -> None:
        service = _build_service()
        assert isinstance(service, EvolutionService)

    @pytest.mark.unit
    def test_disabled_config_builds(self) -> None:
        config = EvolutionConfig(enabled=False)
        service = _build_service(config)
        assert isinstance(service, EvolutionService)

    @pytest.mark.unit
    def test_per_task_trigger(self) -> None:
        config = EvolutionConfig(
            triggers=TriggerConfig(types=("per_task",)),
        )
        service = _build_service(config)
        assert isinstance(service, EvolutionService)

    @pytest.mark.unit
    def test_composite_proposer_without_provider(self) -> None:
        """Without a provider, falls back to self_report."""
        config = EvolutionConfig(
            proposer=ProposerConfig(type="composite"),
        )
        service = _build_service(config)
        assert isinstance(service, EvolutionService)

    @pytest.mark.unit
    def test_separate_analyzer_with_provider(self) -> None:
        config = EvolutionConfig(
            proposer=ProposerConfig(type="separate_analyzer"),
        )
        provider = MagicMock()
        service = _build_service(config, provider=provider)
        assert isinstance(service, EvolutionService)
