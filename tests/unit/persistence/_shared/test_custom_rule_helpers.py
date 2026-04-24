"""Tests for the shared custom-rule repository helpers."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
import structlog

from synthorg.meta.models import ProposalAltitude, RuleSeverity
from synthorg.meta.rules.custom import Comparator, CustomRuleDefinition
from synthorg.observability.events.meta import META_CUSTOM_RULE_FETCH_FAILED
from synthorg.persistence._shared.custom_rule import (
    _coerce_datetime,
    normalize_utc,
    row_to_custom_rule,
    serialize_altitudes,
)
from synthorg.persistence.errors import QueryError


def _rule(
    *,
    altitudes: tuple[ProposalAltitude, ...] = (
        ProposalAltitude.CONFIG_TUNING,
        ProposalAltitude.PROMPT_TUNING,
    ),
) -> CustomRuleDefinition:
    return CustomRuleDefinition(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="rule-x",
        description="alerts when widget count exceeds threshold",
        metric_path="budget.total_spend",
        comparator=Comparator.GT,
        threshold=99.5,
        severity=RuleSeverity.WARNING,
        target_altitudes=altitudes,
        enabled=True,
        created_at=datetime(2026, 4, 24, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 24, 12, 30, tzinfo=UTC),
    )


def _row_for(rule: CustomRuleDefinition, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": str(rule.id),
        "name": rule.name,
        "description": rule.description,
        "metric_path": rule.metric_path,
        "comparator": rule.comparator.value,
        "threshold": rule.threshold,
        "severity": rule.severity.value,
        "target_altitudes": [a.value for a in rule.target_altitudes],
        "enabled": rule.enabled,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }
    base.update(overrides)
    return base


@pytest.mark.unit
class TestNormalizeUtc:
    def test_naive_treated_as_utc(self) -> None:
        naive = datetime(2026, 4, 24, 12, 0)  # noqa: DTZ001  intentional naive
        result = normalize_utc(naive)
        assert result.tzinfo == UTC
        assert result == datetime(2026, 4, 24, 12, 0, tzinfo=UTC)

    def test_aware_converted_to_utc(self) -> None:
        offset_tz = timezone(timedelta(hours=5))
        aware = datetime(2026, 4, 24, 17, 0, tzinfo=offset_tz)
        result = normalize_utc(aware)
        assert result.tzinfo == UTC
        assert result == datetime(2026, 4, 24, 12, 0, tzinfo=UTC)

    def test_already_utc_unchanged(self) -> None:
        already = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
        result = normalize_utc(already)
        assert result == already
        assert result.tzinfo == UTC


@pytest.mark.unit
class TestSerializeAltitudes:
    def test_returns_string_values_in_input_order(self) -> None:
        rule = _rule(
            altitudes=(
                ProposalAltitude.PROMPT_TUNING,
                ProposalAltitude.CONFIG_TUNING,
                ProposalAltitude.ARCHITECTURE,
            ),
        )
        assert serialize_altitudes(rule) == [
            "prompt_tuning",
            "config_tuning",
            "architecture",
        ]

    def test_empty_when_no_altitudes(self) -> None:
        rule = _rule(altitudes=(ProposalAltitude.CONFIG_TUNING,))
        rule_no_alts = rule.model_copy(update={"target_altitudes": ()})
        assert serialize_altitudes(rule_no_alts) == []


@pytest.mark.unit
class TestRowToCustomRule:
    def test_postgres_shape_native_list_and_datetimes(self) -> None:
        rule = _rule()
        row = _row_for(rule)  # native list + native datetime
        loaded = row_to_custom_rule(row)
        assert loaded == rule

    def test_sqlite_shape_string_altitudes_and_iso_strings(self) -> None:
        rule = _rule()
        row = _row_for(
            rule,
            target_altitudes='["config_tuning", "prompt_tuning"]',
            created_at=rule.created_at.isoformat(),
            updated_at=rule.updated_at.isoformat(),
        )
        loaded = row_to_custom_rule(row)
        assert loaded.target_altitudes == rule.target_altitudes
        assert loaded.created_at == rule.created_at
        assert loaded.updated_at == rule.updated_at

    def test_naive_datetime_treated_as_utc(self) -> None:
        rule = _rule()
        naive_created = datetime(2026, 4, 24, 12, 0)  # noqa: DTZ001  intentional naive
        row = _row_for(rule, created_at=naive_created)
        loaded = row_to_custom_rule(row)
        assert loaded.created_at == datetime(2026, 4, 24, 12, 0, tzinfo=UTC)

    def test_invalid_uuid_raises_query_error(self) -> None:
        rule = _rule()
        row = _row_for(rule, id="not-a-uuid")
        with pytest.raises(QueryError):
            row_to_custom_rule(row)

    def test_invalid_enum_raises_query_error(self) -> None:
        rule = _rule()
        row = _row_for(rule, severity="catastrophic")
        with pytest.raises(QueryError):
            row_to_custom_rule(row)

    def test_logs_safe_description_on_failure(self) -> None:
        rule = _rule()
        row = _row_for(rule, severity="catastrophic")
        with (
            structlog.testing.capture_logs() as cap,
            pytest.raises(QueryError),
        ):
            row_to_custom_rule(row)
        events = [e for e in cap if e.get("event") == META_CUSTOM_RULE_FETCH_FAILED]
        assert len(events) == 1
        evt = events[0]
        assert evt["row_id"] == str(rule.id)
        assert "error_type" in evt
        assert "error" in evt


@pytest.mark.unit
class TestCoerceDatetime:
    def test_unsupported_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            _coerce_datetime(12345)
