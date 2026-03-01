"""Tests for sink routing (logger name filters)."""

import logging

import pytest

from ai_company.observability.sinks import _SINK_ROUTING, _LoggerNameFilter

pytestmark = pytest.mark.timeout(30)


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
        assert f.filter(_make_record("ai_company.core.task"))

    def test_include_accepts_matching(self) -> None:
        f = _LoggerNameFilter(
            include_prefixes=("ai_company.security.",),
        )
        assert f.filter(_make_record("ai_company.security.audit"))
        assert not f.filter(_make_record("ai_company.core.task"))

    def test_include_rejects_non_matching(self) -> None:
        f = _LoggerNameFilter(
            include_prefixes=("ai_company.budget.",),
        )
        assert not f.filter(_make_record("ai_company.engine.run"))

    def test_exclude_rejects_matching(self) -> None:
        f = _LoggerNameFilter(
            exclude_prefixes=("ai_company.noisy.",),
        )
        assert not f.filter(_make_record("ai_company.noisy.debug"))
        assert f.filter(_make_record("ai_company.core.task"))

    def test_exclude_takes_precedence_over_include(self) -> None:
        f = _LoggerNameFilter(
            include_prefixes=("ai_company.",),
            exclude_prefixes=("ai_company.noisy.",),
        )
        assert not f.filter(_make_record("ai_company.noisy.debug"))
        assert f.filter(_make_record("ai_company.core.task"))

    def test_multiple_include_prefixes(self) -> None:
        f = _LoggerNameFilter(
            include_prefixes=("ai_company.budget.", "ai_company.providers."),
        )
        assert f.filter(_make_record("ai_company.budget.tracker"))
        assert f.filter(_make_record("ai_company.providers.litellm"))
        assert not f.filter(_make_record("ai_company.core.task"))


@pytest.mark.unit
class TestSinkRoutingTable:
    def test_audit_routes_security(self) -> None:
        assert "audit.log" in _SINK_ROUTING
        assert "ai_company.security." in _SINK_ROUTING["audit.log"]

    def test_cost_usage_routes_budget_and_providers(self) -> None:
        assert "cost_usage.log" in _SINK_ROUTING
        prefixes = _SINK_ROUTING["cost_usage.log"]
        assert "ai_company.budget." in prefixes
        assert "ai_company.providers." in prefixes

    def test_agent_activity_routes_engine_and_core(self) -> None:
        assert "agent_activity.log" in _SINK_ROUTING
        prefixes = _SINK_ROUTING["agent_activity.log"]
        assert "ai_company.engine." in prefixes
        assert "ai_company.core." in prefixes

    def test_catchall_sinks_not_in_routing(self) -> None:
        for name in ("ai_company.log", "errors.log", "debug.log"):
            assert name not in _SINK_ROUTING
