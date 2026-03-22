"""Tests for sink routing (logger name filters)."""

import logging

import pytest

from synthorg.observability.sinks import _SINK_ROUTING, _LoggerNameFilter


def _make_record(name: str) -> logging.LogRecord:
    """Create a minimal LogRecord with the given logger name."""
    return logging.LogRecord(
        name=name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test",
        args=(),
        exc_info=None,
    )


@pytest.mark.unit
class TestLoggerNameFilter:
    def test_no_filters_accepts_all(self) -> None:
        f = _LoggerNameFilter()
        assert f.filter(_make_record("anything"))
        assert f.filter(_make_record("synthorg.core.task"))

    def test_include_accepts_matching(self) -> None:
        f = _LoggerNameFilter(
            include_prefixes=("synthorg.security.",),
        )
        assert f.filter(_make_record("synthorg.security.audit"))
        assert not f.filter(_make_record("synthorg.core.task"))

    def test_include_rejects_non_matching(self) -> None:
        f = _LoggerNameFilter(
            include_prefixes=("synthorg.budget.",),
        )
        assert not f.filter(_make_record("synthorg.engine.run"))

    def test_exclude_rejects_matching(self) -> None:
        f = _LoggerNameFilter(
            exclude_prefixes=("synthorg.noisy.",),
        )
        assert not f.filter(_make_record("synthorg.noisy.debug"))
        assert f.filter(_make_record("synthorg.core.task"))

    def test_exclude_takes_precedence_over_include(self) -> None:
        f = _LoggerNameFilter(
            include_prefixes=("synthorg.",),
            exclude_prefixes=("synthorg.noisy.",),
        )
        assert not f.filter(_make_record("synthorg.noisy.debug"))
        assert f.filter(_make_record("synthorg.core.task"))

    def test_multiple_include_prefixes(self) -> None:
        f = _LoggerNameFilter(
            include_prefixes=("synthorg.budget.", "synthorg.providers."),
        )
        assert f.filter(_make_record("synthorg.budget.tracker"))
        assert f.filter(_make_record("synthorg.providers.litellm"))
        assert not f.filter(_make_record("synthorg.core.task"))


@pytest.mark.unit
class TestSinkRoutingTable:
    def test_audit_routes_security(self) -> None:
        assert "audit.log" in _SINK_ROUTING
        assert "synthorg.security." in _SINK_ROUTING["audit.log"]

    def test_cost_usage_routes_budget_and_providers(self) -> None:
        assert "cost_usage.log" in _SINK_ROUTING
        prefixes = _SINK_ROUTING["cost_usage.log"]
        assert "synthorg.budget." in prefixes
        assert "synthorg.providers." in prefixes

    def test_agent_activity_routes_engine_and_core(self) -> None:
        assert "agent_activity.log" in _SINK_ROUTING
        prefixes = _SINK_ROUTING["agent_activity.log"]
        assert "synthorg.engine." in prefixes
        assert "synthorg.core." in prefixes

    def test_access_routes_api(self) -> None:
        assert "access.log" in _SINK_ROUTING
        assert "synthorg.api." in _SINK_ROUTING["access.log"]

    @pytest.mark.parametrize(
        ("sink", "prefix"),
        [
            ("audit.log", "synthorg.hr."),
            ("audit.log", "synthorg.observability."),
            ("agent_activity.log", "synthorg.communication."),
            ("agent_activity.log", "synthorg.tools."),
            ("agent_activity.log", "synthorg.memory."),
            ("persistence.log", "synthorg.persistence."),
            ("configuration.log", "synthorg.settings."),
            ("configuration.log", "synthorg.config."),
            ("backup.log", "synthorg.backup."),
        ],
        ids=[
            "audit-hr",
            "audit-observability",
            "activity-communication",
            "activity-tools",
            "activity-memory",
            "persistence-persistence",
            "configuration-settings",
            "configuration-config",
            "backup-backup",
        ],
    )
    def test_sink_routes_prefix(self, sink: str, prefix: str) -> None:
        assert prefix in _SINK_ROUTING[sink]

    def test_routing_table_has_exactly_expected_sinks(self) -> None:
        assert set(_SINK_ROUTING.keys()) == {
            "audit.log",
            "cost_usage.log",
            "agent_activity.log",
            "access.log",
            "persistence.log",
            "configuration.log",
            "backup.log",
        }

    def test_catchall_sinks_not_in_routing(self) -> None:
        for name in ("synthorg.log", "errors.log", "debug.log"):
            assert name not in _SINK_ROUTING
