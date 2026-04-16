"""Unit tests for the cross-deployment analytics factory."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.meta.config import SelfImprovementConfig
from synthorg.meta.telemetry.collector import InMemoryAnalyticsCollector
from synthorg.meta.telemetry.config import CrossDeploymentAnalyticsConfig
from synthorg.meta.telemetry.emitter import HttpAnalyticsEmitter
from synthorg.meta.telemetry.factory import (
    build_analytics_collector,
    build_analytics_emitter,
    build_recommender,
)
from synthorg.meta.telemetry.recommender import DefaultThresholdRecommender

from .conftest import BUILTIN_RULE_NAMES

pytestmark = pytest.mark.unit


class TestBuildAnalyticsEmitter:
    """Tests for build_analytics_emitter()."""

    def test_returns_none_when_disabled(self) -> None:
        config = SelfImprovementConfig()
        result = build_analytics_emitter(
            config,
            builtin_rule_names=BUILTIN_RULE_NAMES,
        )
        assert result is None

    def test_returns_emitter_when_enabled(
        self,
        self_improvement_config: SelfImprovementConfig,
    ) -> None:
        result = build_analytics_emitter(
            self_improvement_config,
            builtin_rule_names=BUILTIN_RULE_NAMES,
        )
        assert isinstance(result, HttpAnalyticsEmitter)


class TestBuildAnalyticsCollector:
    """Tests for build_analytics_collector()."""

    def test_returns_none_when_disabled(self) -> None:
        config = SelfImprovementConfig()
        result = build_analytics_collector(config)
        assert result is None

    def test_returns_collector_when_enabled(self) -> None:
        analytics = CrossDeploymentAnalyticsConfig(
            enabled=True,
            collector_url=NotBlankStr("https://test.example"),
            deployment_id_salt=NotBlankStr("test-salt"),
            collector_enabled=True,
        )
        config = SelfImprovementConfig(cross_deployment_analytics=analytics)
        result = build_analytics_collector(config)
        assert isinstance(result, InMemoryAnalyticsCollector)


class TestBuildRecommender:
    """Tests for build_recommender()."""

    def test_returns_recommender(self) -> None:
        config = SelfImprovementConfig()
        result = build_recommender(config)
        assert isinstance(result, DefaultThresholdRecommender)

    def test_uses_config_values(self) -> None:
        analytics = CrossDeploymentAnalyticsConfig(
            enabled=True,
            collector_url=NotBlankStr("https://test.example"),
            deployment_id_salt=NotBlankStr("test-salt"),
            min_deployments_for_pattern=5,
            recommendation_min_observations=20,
        )
        config = SelfImprovementConfig(
            cross_deployment_analytics=analytics,
        )
        result = build_recommender(config)
        assert result._min_deployments == 5
        assert result._min_observations == 20
