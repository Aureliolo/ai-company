"""Conformance tests for ``ProjectCostAggregateRepository``.

Covers atomic increment semantics and lookup parity between SQLite and
Postgres. PST-1 adds ``project_cost_aggregates`` to the
``PersistenceBackend`` protocol so conformance tests can drive both
backends behind the same fixture.
"""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.persistence.protocol import PersistenceBackend

pytestmark = pytest.mark.integration


class TestProjectCostAggregateRepository:
    async def test_get_missing_returns_none(self, backend: PersistenceBackend) -> None:
        result = await backend.project_cost_aggregates.get(
            NotBlankStr("never-touched"),
        )
        assert result is None

    async def test_increment_creates_row(self, backend: PersistenceBackend) -> None:
        aggregate = await backend.project_cost_aggregates.increment(
            NotBlankStr("proj-001"),
            cost=0.25,
            input_tokens=100,
            output_tokens=50,
        )
        assert aggregate.project_id == "proj-001"
        assert aggregate.total_cost == pytest.approx(0.25)
        assert aggregate.total_input_tokens == 100
        assert aggregate.total_output_tokens == 50
        assert aggregate.record_count == 1

    async def test_increment_accumulates(self, backend: PersistenceBackend) -> None:
        await backend.project_cost_aggregates.increment(
            NotBlankStr("proj-001"),
            cost=0.10,
            input_tokens=50,
            output_tokens=25,
        )
        updated = await backend.project_cost_aggregates.increment(
            NotBlankStr("proj-001"),
            cost=0.15,
            input_tokens=30,
            output_tokens=20,
        )

        assert updated.total_cost == pytest.approx(0.25)
        assert updated.total_input_tokens == 80
        assert updated.total_output_tokens == 45
        assert updated.record_count == 2

    async def test_get_after_increment(self, backend: PersistenceBackend) -> None:
        await backend.project_cost_aggregates.increment(
            NotBlankStr("proj-002"),
            cost=1.00,
            input_tokens=1000,
            output_tokens=500,
        )

        fetched = await backend.project_cost_aggregates.get(NotBlankStr("proj-002"))
        assert fetched is not None
        assert fetched.total_cost == pytest.approx(1.00)

    async def test_increments_are_project_scoped(
        self, backend: PersistenceBackend
    ) -> None:
        await backend.project_cost_aggregates.increment(
            NotBlankStr("alpha"),
            cost=0.50,
            input_tokens=10,
            output_tokens=5,
        )
        await backend.project_cost_aggregates.increment(
            NotBlankStr("beta"),
            cost=2.00,
            input_tokens=40,
            output_tokens=20,
        )

        alpha = await backend.project_cost_aggregates.get(NotBlankStr("alpha"))
        beta = await backend.project_cost_aggregates.get(NotBlankStr("beta"))
        assert alpha is not None
        assert beta is not None
        assert alpha.total_cost == pytest.approx(0.50)
        assert beta.total_cost == pytest.approx(2.00)
