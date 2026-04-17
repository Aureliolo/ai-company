"""Tests for the human escalation resolution strategy (#1418)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from synthorg.communication.conflict_resolution.escalation.in_memory_store import (
    InMemoryEscalationStore,
)
from synthorg.communication.conflict_resolution.escalation.models import (
    EscalationStatus,
    RejectDecision,
    WinnerDecision,
)
from synthorg.communication.conflict_resolution.escalation.processors import (
    HybridDecisionProcessor,
    WinnerSelectProcessor,
)
from synthorg.communication.conflict_resolution.escalation.registry import (
    PendingFuturesRegistry,
)
from synthorg.communication.conflict_resolution.human_strategy import (
    HumanEscalationResolver,
)
from synthorg.communication.conflict_resolution.models import (
    ConflictResolutionOutcome,
)
from synthorg.communication.enums import ConflictResolutionStrategy

from .conftest import make_conflict


@pytest.mark.unit
class TestHumanEscalationDefaults:
    """With no arguments the resolver times out immediately."""

    async def test_returns_escalated_outcome(self) -> None:
        resolver = HumanEscalationResolver()
        conflict = make_conflict()
        resolution = await resolver.resolve(conflict)
        assert resolution.outcome == ConflictResolutionOutcome.ESCALATED_TO_HUMAN

    async def test_no_winning_agent(self) -> None:
        resolver = HumanEscalationResolver()
        conflict = make_conflict()
        resolution = await resolver.resolve(conflict)
        assert resolution.winning_agent_id is None
        assert resolution.winning_position is None

    async def test_decided_by_human(self) -> None:
        resolver = HumanEscalationResolver()
        conflict = make_conflict()
        resolution = await resolver.resolve(conflict)
        assert resolution.decided_by == "human"

    async def test_dissent_records_strategy(self) -> None:
        resolver = HumanEscalationResolver()
        conflict = make_conflict()
        resolution = await resolver.resolve(conflict)
        records = resolver.build_dissent_records(conflict, resolution)
        assert len(records) == 2
        assert records[0].strategy_used == ConflictResolutionStrategy.HUMAN
        assert ("escalation_reason", "human_review_required") in records[0].metadata
        dissenter_ids = {r.dissenting_agent_id for r in records}
        assert dissenter_ids == {"agent-a", "agent-b"}


@pytest.mark.unit
class TestHumanEscalationFullLoop:
    """End-to-end: escalate -> decide -> resolver wakes with decision."""

    async def test_winner_decision_resolves_awaiting_resolver(self) -> None:
        store = InMemoryEscalationStore()
        registry = PendingFuturesRegistry()
        resolver = HumanEscalationResolver(
            store=store,
            processor=WinnerSelectProcessor(),
            registry=registry,
            timeout_seconds=5,
        )
        conflict = make_conflict()

        async def _decide_after_enqueue() -> None:
            # Wait for the resolver to register its future.
            while True:
                rows, _ = await store.list_items(status=EscalationStatus.PENDING)
                if rows:
                    escalation_id = rows[0].id
                    break
                await asyncio.sleep(0.01)
            decision = WinnerDecision(
                winning_agent_id="agent-a",
                reasoning="Tie-breaking call by operator",
            )
            await store.apply_decision(
                escalation_id,
                decision=decision,
                decided_by="human:op-1",
            )
            await registry.resolve(escalation_id, decision)

        resolve_task = asyncio.create_task(resolver.resolve(conflict))
        decide_task = asyncio.create_task(_decide_after_enqueue())
        resolution, _ = await asyncio.gather(resolve_task, decide_task)

        assert resolution.outcome == ConflictResolutionOutcome.RESOLVED_BY_HUMAN
        assert resolution.winning_agent_id == "agent-a"
        # Decided rows are preserved in the store for audit.
        rows, total = await store.list_items(status=EscalationStatus.DECIDED)
        assert total == 1
        assert rows[0].decision == WinnerDecision(
            winning_agent_id="agent-a",
            reasoning="Tie-breaking call by operator",
        )

    async def test_reject_decision_with_hybrid_processor(self) -> None:
        store = InMemoryEscalationStore()
        registry = PendingFuturesRegistry()
        resolver = HumanEscalationResolver(
            store=store,
            processor=HybridDecisionProcessor(),
            registry=registry,
            timeout_seconds=5,
        )
        conflict = make_conflict()

        async def _reject() -> None:
            while True:
                rows, _ = await store.list_items(status=EscalationStatus.PENDING)
                if rows:
                    escalation_id = rows[0].id
                    break
                await asyncio.sleep(0.01)
            decision = RejectDecision(reasoning="Both proposals off-strategy")
            await store.apply_decision(
                escalation_id,
                decision=decision,
                decided_by="human:op-2",
            )
            await registry.resolve(escalation_id, decision)

        resolve_task = asyncio.create_task(resolver.resolve(conflict))
        await asyncio.gather(resolve_task, asyncio.create_task(_reject()))
        resolution = resolve_task.result()
        assert resolution.outcome == ConflictResolutionOutcome.REJECTED_BY_HUMAN
        assert resolution.winning_agent_id is None

    async def test_winner_select_rejects_reject_decision(self) -> None:
        processor = WinnerSelectProcessor()
        conflict = make_conflict()
        with pytest.raises(ValueError, match="only accepts 'winner'"):
            processor.process(
                conflict,
                RejectDecision(reasoning="no"),
                decided_by="human:op-x",
            )

    async def test_winner_select_rejects_unknown_agent(self) -> None:
        processor = WinnerSelectProcessor()
        conflict = make_conflict()
        with pytest.raises(ValueError, match="does not match"):
            processor.process(
                conflict,
                WinnerDecision(
                    winning_agent_id="agent-zzz",
                    reasoning="bad pick",
                ),
                decided_by="human:op-x",
            )

    async def test_timeout_returns_escalated_outcome(self) -> None:
        store = InMemoryEscalationStore()
        registry = PendingFuturesRegistry()
        resolver = HumanEscalationResolver(
            store=store,
            registry=registry,
            timeout_seconds=1,
        )
        conflict = make_conflict()
        resolution = await resolver.resolve(conflict)
        assert resolution.outcome == ConflictResolutionOutcome.ESCALATED_TO_HUMAN
        # The store row should be marked EXPIRED afterwards.
        rows, _ = await store.list_items(status=EscalationStatus.EXPIRED)
        assert len(rows) == 1

    async def test_sweeper_expires_stale_rows(self) -> None:
        store = InMemoryEscalationStore()
        conflict = make_conflict()
        from synthorg.communication.conflict_resolution.escalation.models import (
            Escalation,
        )

        past = datetime.now(UTC) - timedelta(seconds=10)
        escalation = Escalation(
            id="escalation-stale-0001",
            conflict=conflict,
            created_at=past,
            expires_at=past,
        )
        await store.create(escalation)
        expired = await store.mark_expired(datetime.now(UTC).isoformat())
        assert expired == ("escalation-stale-0001",)
        row = await store.get("escalation-stale-0001")
        assert row is not None
        assert row.status == EscalationStatus.EXPIRED
