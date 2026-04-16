"""Unit tests for the in-memory analytics collector."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.meta.telemetry.collector import InMemoryAnalyticsCollector
from synthorg.meta.telemetry.models import AnonymizedOutcomeEvent

pytestmark = pytest.mark.unit


def _make_event(
    deployment_id: str = "deploy-a",
    source_rule: str = "coordination_overhead",
) -> AnonymizedOutcomeEvent:
    return AnonymizedOutcomeEvent(
        deployment_id=NotBlankStr(deployment_id),
        event_type="proposal_decision",
        timestamp=NotBlankStr("2026-04-16"),
        altitude=NotBlankStr("config_tuning"),
        source_rule=NotBlankStr(source_rule),
        decision="approved",
        confidence=0.7,
        enabled_altitudes=(NotBlankStr("config_tuning"),),
        sdk_version=NotBlankStr("0.6.8"),
    )


class TestInMemoryAnalyticsCollector:
    """Tests for InMemoryAnalyticsCollector."""

    async def test_ingest_returns_count(self) -> None:
        collector = InMemoryAnalyticsCollector()
        events = (_make_event(), _make_event())
        count = await collector.ingest(events)
        assert count == 2

    async def test_event_count_after_ingest(self) -> None:
        collector = InMemoryAnalyticsCollector()
        await collector.ingest((_make_event(),))
        await collector.ingest((_make_event(), _make_event()))
        assert collector.event_count == 3

    async def test_query_patterns_returns_empty_initially(self) -> None:
        collector = InMemoryAnalyticsCollector()
        patterns = await collector.query_patterns()
        assert patterns == ()

    async def test_query_patterns_after_ingestion(self) -> None:
        collector = InMemoryAnalyticsCollector()
        events = tuple(_make_event(deployment_id=f"d-{i}") for i in range(3))
        await collector.ingest(events)
        patterns = await collector.query_patterns(min_deployments=3)
        assert len(patterns) == 1
        assert patterns[0].deployment_count == 3

    async def test_query_patterns_respects_min_deployments(self) -> None:
        collector = InMemoryAnalyticsCollector()
        events = tuple(_make_event(deployment_id=f"d-{i}") for i in range(2))
        await collector.ingest(events)
        patterns = await collector.query_patterns(min_deployments=3)
        assert patterns == ()
