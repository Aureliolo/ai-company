"""Tests for the in-memory evolution outcome store."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.meta.evolution.outcome_store import (
    InMemoryEvolutionOutcomeStore,
)
from synthorg.meta.evolution.outcome_store_protocol import (
    EvolutionOutcomeStore,
)


async def _populate(
    store: InMemoryEvolutionOutcomeStore,
    *,
    agent_id: str = "agent-1",
    axis: str = "prompt_tuning",
    applied: bool = True,
    proposed_at: datetime | None = None,
) -> None:
    await store.record(
        agent_id=NotBlankStr(agent_id),
        axis=NotBlankStr(axis),
        applied=applied,
        proposed_at=proposed_at or datetime.now(UTC) - timedelta(minutes=30),
    )


@pytest.mark.unit
class TestInMemoryEvolutionOutcomeStoreProtocol:
    """The in-memory impl satisfies the EvolutionOutcomeStore protocol."""

    def test_satisfies_protocol(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        assert isinstance(store, EvolutionOutcomeStore)


@pytest.mark.unit
class TestInMemoryEvolutionOutcomeStoreCapacity:
    """Ring-buffer bounds and eviction."""

    def test_rejects_non_positive_capacity(self) -> None:
        with pytest.raises(ValueError, match="max_results must be >= 1"):
            InMemoryEvolutionOutcomeStore(max_results=0)

    async def test_evicts_oldest_when_full(self) -> None:
        store = InMemoryEvolutionOutcomeStore(max_results=2)
        now = datetime.now(UTC)
        for i in range(5):
            await store.record(
                agent_id=NotBlankStr(f"agent-{i}"),
                axis=NotBlankStr("prompt_tuning"),
                applied=True,
                proposed_at=now - timedelta(minutes=i),
            )
        assert await store.count() == 2

    async def test_clear_resets_buffer(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        await _populate(store)
        assert await store.count() == 1
        await store.clear()
        assert await store.count() == 0


@pytest.mark.unit
class TestInMemoryEvolutionOutcomeStoreWindowing:
    """query / summarize filter by [since, until)."""

    async def test_query_rejects_naive_datetimes(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        with pytest.raises(ValueError, match="timezone-aware"):
            await store.query(
                since=datetime(2026, 4, 1),  # noqa: DTZ001 - intentional naive
                until=datetime.now(UTC),
            )

    async def test_query_rejects_inverted_window(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="earlier"):
            await store.query(
                since=now,
                until=now - timedelta(hours=1),
            )

    async def test_query_newest_first(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        now = datetime.now(UTC)
        await store.record(
            agent_id=NotBlankStr("a1"),
            axis=NotBlankStr("prompt_tuning"),
            applied=True,
            proposed_at=now - timedelta(hours=1),
        )
        await store.record(
            agent_id=NotBlankStr("a2"),
            axis=NotBlankStr("prompt_tuning"),
            applied=False,
            proposed_at=now - timedelta(minutes=5),
        )
        records = await store.query(
            since=now - timedelta(hours=2),
            until=now + timedelta(minutes=1),
        )
        assert records[0].agent_id == "a2"
        assert records[1].agent_id == "a1"


@pytest.mark.unit
class TestInMemoryEvolutionOutcomeStoreSummarize:
    """summarize produces an OrgEvolutionSummary."""

    async def test_empty_summary_when_no_records(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        now = datetime.now(UTC)
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert summary.total_proposals == 0
        assert summary.recent_outcomes == ()
        assert summary.approval_rate == 0.0

    async def test_approval_rate_and_most_adapted(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        now = datetime.now(UTC)
        proposed_at = now - timedelta(minutes=30)
        # 3 x prompt_tuning (2 applied), 1 x config_tuning (1 applied) -> 3/4.
        for agent in ("a", "b", "c"):
            await store.record(
                agent_id=NotBlankStr(agent),
                axis=NotBlankStr("prompt_tuning"),
                applied=agent != "c",  # c rejected, a and b applied
                proposed_at=proposed_at,
            )
        await store.record(
            agent_id=NotBlankStr("d"),
            axis=NotBlankStr("config_tuning"),
            applied=True,
            proposed_at=proposed_at,
        )
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now + timedelta(minutes=1),
        )
        assert summary.total_proposals == 4
        assert summary.approval_rate == pytest.approx(0.75)
        assert summary.most_adapted_axis == "prompt_tuning"

    async def test_most_adapted_ties_break_alphabetically(self) -> None:
        """Equal-count axes resolve alphabetically for determinism."""
        store = InMemoryEvolutionOutcomeStore()
        now = datetime.now(UTC)
        proposed_at = now - timedelta(minutes=30)
        for axis in ("prompt_tuning", "config_tuning"):
            await store.record(
                agent_id=NotBlankStr(f"agent-{axis}"),
                axis=NotBlankStr(axis),
                applied=True,
                proposed_at=proposed_at,
            )
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now + timedelta(minutes=1),
        )
        assert summary.most_adapted_axis == "config_tuning"

    async def test_recent_outcomes_cap(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        now = datetime.now(UTC)
        proposed_at = now - timedelta(minutes=30)
        for idx in range(7):
            await store.record(
                agent_id=NotBlankStr(f"a-{idx}"),
                axis=NotBlankStr("prompt_tuning"),
                applied=True,
                proposed_at=proposed_at,
            )
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now + timedelta(minutes=1),
            max_recent=3,
        )
        assert len(summary.recent_outcomes) == 3
        assert summary.total_proposals == 7

    async def test_rejects_invalid_max_recent(self) -> None:
        store = InMemoryEvolutionOutcomeStore()
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="max_recent"):
            await store.summarize(
                since=now - timedelta(hours=1),
                until=now,
                max_recent=0,
            )
