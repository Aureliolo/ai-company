"""Parametrized conformance tests for ``CustomRuleRepository``.

Runs against both SQLite and Postgres via the ``backend`` fixture so
SQLite-vs-Postgres divergence is caught on every commit. The tests
assert the contract of the shared helpers in
``synthorg.persistence._shared.custom_rule`` -- altitude round-trip,
UTC timestamp normalisation, and enum coercion.
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from synthorg.meta.models import ProposalAltitude, RuleSeverity
from synthorg.meta.rules.custom import Comparator, CustomRuleDefinition
from synthorg.persistence.errors import ConstraintViolationError
from synthorg.persistence.protocol import PersistenceBackend


def _rule(
    *,
    rule_id: UUID | None = None,
    name: str = "rule-x",
    altitudes: tuple[ProposalAltitude, ...] = (
        ProposalAltitude.CONFIG_TUNING,
        ProposalAltitude.PROMPT_TUNING,
    ),
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> CustomRuleDefinition:
    now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    return CustomRuleDefinition(
        id=rule_id or uuid4(),
        name=name,
        description="alerts when total spend exceeds threshold",
        metric_path="budget.total_spend",
        comparator=Comparator.GT,
        threshold=99.5,
        severity=RuleSeverity.WARNING,
        target_altitudes=altitudes,
        enabled=True,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


@pytest.mark.integration
class TestCustomRuleRepositoryConformance:
    async def test_save_and_get_round_trip(
        self,
        backend: PersistenceBackend,
    ) -> None:
        rule = _rule()
        await backend.custom_rules.save(rule)

        fetched = await backend.custom_rules.get(str(rule.id))
        assert fetched == rule

    async def test_upsert_on_id_conflict(
        self,
        backend: PersistenceBackend,
    ) -> None:
        rule = _rule(name="original")
        await backend.custom_rules.save(rule)

        updated = rule.model_copy(update={"description": "updated description"})
        await backend.custom_rules.save(updated)

        fetched = await backend.custom_rules.get(str(rule.id))
        assert fetched is not None
        assert fetched.description == "updated description"

    async def test_duplicate_name_raises_constraint_violation(
        self,
        backend: PersistenceBackend,
    ) -> None:
        first = _rule(name="shared-name")
        second = _rule(rule_id=uuid4(), name="shared-name")
        await backend.custom_rules.save(first)
        with pytest.raises(ConstraintViolationError):
            await backend.custom_rules.save(second)

    async def test_altitudes_round_trip_preserves_order(
        self,
        backend: PersistenceBackend,
    ) -> None:
        altitudes = (
            ProposalAltitude.PROMPT_TUNING,
            ProposalAltitude.CONFIG_TUNING,
            ProposalAltitude.ARCHITECTURE,
        )
        rule = _rule(altitudes=altitudes)
        await backend.custom_rules.save(rule)
        fetched = await backend.custom_rules.get(str(rule.id))
        assert fetched is not None
        assert fetched.target_altitudes == altitudes

    async def test_non_utc_timestamps_normalised_on_round_trip(
        self,
        backend: PersistenceBackend,
    ) -> None:
        offset_tz = timezone(timedelta(hours=5))
        local_now = datetime(2026, 4, 24, 17, 0, tzinfo=offset_tz)
        rule = _rule(created_at=local_now, updated_at=local_now)
        await backend.custom_rules.save(rule)

        fetched = await backend.custom_rules.get(str(rule.id))
        assert fetched is not None
        # Assert tzinfo AND the exact UTC instant for both timestamps
        # -- a backend that incorrectly shifted the wall-clock time
        # but kept the offset would still satisfy a tzinfo-only check.
        expected_utc = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
        assert fetched.created_at.tzinfo == UTC
        assert fetched.updated_at.tzinfo == UTC
        assert fetched.created_at == expected_utc
        assert fetched.updated_at == expected_utc

    async def test_get_missing_returns_none(
        self,
        backend: PersistenceBackend,
    ) -> None:
        result = await backend.custom_rules.get(str(uuid4()))
        assert result is None

    async def test_list_rules_returns_all(
        self,
        backend: PersistenceBackend,
    ) -> None:
        a = _rule(name="rule-a")
        b = _rule(name="rule-b")
        await backend.custom_rules.save(a)
        await backend.custom_rules.save(b)
        rules = await backend.custom_rules.list_rules()
        assert {r.name for r in rules} == {"rule-a", "rule-b"}

    async def test_delete_removes_rule(
        self,
        backend: PersistenceBackend,
    ) -> None:
        rule = _rule()
        await backend.custom_rules.save(rule)
        deleted = await backend.custom_rules.delete(str(rule.id))
        assert deleted is True
        assert await backend.custom_rules.get(str(rule.id)) is None

    async def test_delete_missing_returns_false(
        self,
        backend: PersistenceBackend,
    ) -> None:
        assert await backend.custom_rules.delete(str(uuid4())) is False
