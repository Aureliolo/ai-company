"""Concurrency regression tests for ApprovalStore.

Covers the TOCTOU gaps in ``save()``, ``save_if_pending()``, ``add()`` and
the lazy expiration path. Two concurrent ``save(same_id)`` must result in
first-writer-wins semantics: exactly one call persists its payload, the
second returns ``None`` and logs ``API_APPROVAL_CONFLICT`` with
``error="concurrent_save"``.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from synthorg.api.approval_store import ApprovalStore
from synthorg.api.errors import ConflictError
from synthorg.core.approval import ApprovalItem
from synthorg.core.enums import ApprovalRiskLevel, ApprovalStatus
from synthorg.persistence.errors import ConstraintViolationError


def _now() -> datetime:
    return datetime.now(UTC)


def _make_item(
    *,
    approval_id: str = "approval-001",
    status: ApprovalStatus = ApprovalStatus.PENDING,
    decision_reason: str | None = None,
    decided_at: datetime | None = None,
    decided_by: str | None = None,
) -> ApprovalItem:
    return ApprovalItem(
        id=approval_id,
        action_type="code:merge",
        title="Test approval",
        description="A test approval item",
        requested_by="agent-dev",
        risk_level=ApprovalRiskLevel.MEDIUM,
        status=status,
        created_at=_now(),
        expires_at=None,
        decided_at=decided_at,
        decided_by=decided_by,
        decision_reason=decision_reason,
    )


class GatedRepo:
    """Fake approval repo that gates the first ``save`` call on an event.

    Lets tests deterministically reproduce the race where caller A is
    mid-write while caller B enters ``save()``.
    """

    def __init__(self) -> None:
        self.items: dict[str, ApprovalItem] = {}
        self.save_calls = 0
        self.gate = asyncio.Event()
        self.first_entered = asyncio.Event()
        self.gate_enabled = True

    async def get(self, approval_id: str) -> ApprovalItem | None:
        return self.items.get(approval_id)

    async def save(self, item: ApprovalItem) -> None:
        self.save_calls += 1
        if self.gate_enabled and self.save_calls == 1:
            self.first_entered.set()
            await self.gate.wait()
        self.items[item.id] = item

    async def list_items(
        self,
        *,
        status: ApprovalStatus | None = None,
        risk_level: ApprovalRiskLevel | None = None,
        action_type: str | None = None,
    ) -> tuple[ApprovalItem, ...]:
        del status, risk_level, action_type
        return tuple(self.items.values())


@pytest.mark.unit
class TestSaveConcurrency:
    """save() must guarantee first-writer-wins under concurrent callers."""

    async def test_concurrent_save_first_writer_wins(self) -> None:
        repo = GatedRepo()
        initial = _make_item()
        repo.items[initial.id] = initial
        store = ApprovalStore(repo=repo)  # type: ignore[arg-type]
        # Populate cache to avoid repo.get during save.
        await store.get(initial.id)

        updated_a = initial.model_copy(update={"decision_reason": "reason_a"})
        updated_b = initial.model_copy(update={"decision_reason": "reason_b"})

        with patch(
            "synthorg.api.approval_store.logger",
        ) as mock_logger:
            task_a = asyncio.create_task(store.save(updated_a))
            await repo.first_entered.wait()
            # Task A is parked inside repo.save waiting on the gate,
            # with its approval id already in ``_saves_in_flight`` and
            # the store lock released.  Awaiting the second save
            # directly here is deterministic: the store lock is free,
            # B observes the in-flight marker, logs the conflict and
            # returns ``None`` before we unblock A.
            result_b = await store.save(updated_b)
            repo.gate.set()
            result_a = await task_a

            # Exactly one winner, one rejection.
            winners = [r for r in (result_a, result_b) if r is not None]
            rejections = [r for r in (result_a, result_b) if r is None]
            assert len(winners) == 1
            assert len(rejections) == 1
            # The FWW contract is that the first caller wins.
            assert result_a is not None
            assert result_b is None

            # Stored payload matches the winner.
            stored = await store.get(initial.id)
            assert stored is not None
            assert stored.decision_reason == winners[0].decision_reason

            # Only one repo.save call happened.
            assert repo.save_calls == 1

            # Conflict log was emitted with the concurrent_save error tag.
            conflict_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if call.kwargs.get("error") == "concurrent_save"
            ]
            assert len(conflict_calls) == 1
            assert conflict_calls[0].kwargs["approval_id"] == initial.id

    async def test_sequential_saves_both_succeed(self) -> None:
        """Sequential saves both persist; in-flight only rejects overlap."""
        repo = GatedRepo()
        repo.gate_enabled = False  # no gating
        initial = _make_item()
        repo.items[initial.id] = initial
        store = ApprovalStore(repo=repo)  # type: ignore[arg-type]
        await store.get(initial.id)

        updated_a = initial.model_copy(update={"decision_reason": "first"})
        result_a = await store.save(updated_a)
        assert result_a is not None
        assert result_a.decision_reason == "first"

        updated_b = updated_a.model_copy(update={"decision_reason": "second"})
        result_b = await store.save(updated_b)
        assert result_b is not None
        assert result_b.decision_reason == "second"

        stored = await store.get(initial.id)
        assert stored is not None
        assert stored.decision_reason == "second"

    async def test_concurrent_save_first_writer_wins_cold_cache(self) -> None:
        """FWW still holds when the store starts with a cold cache.

        Both callers must pass through ``repo.get`` under the lock; the
        second must still detect the in-flight marker and return None.
        """
        repo = GatedRepo()
        initial = _make_item()
        repo.items[initial.id] = initial
        store = ApprovalStore(repo=repo)  # type: ignore[arg-type]
        # Do NOT pre-warm the cache -- both saves must load from repo.

        updated_a = initial.model_copy(update={"decision_reason": "a"})
        updated_b = initial.model_copy(update={"decision_reason": "b"})

        with patch("synthorg.api.approval_store.logger") as mock_logger:
            task_a = asyncio.create_task(store.save(updated_a))
            await repo.first_entered.wait()
            # Same deterministic pattern as the warm-cache variant:
            # A is parked in repo.save, B runs synchronously here,
            # hits the in-flight marker, returns None without blocking.
            result_b = await store.save(updated_b)
            repo.gate.set()
            result_a = await task_a

            winners = [r for r in (result_a, result_b) if r is not None]
            rejections = [r for r in (result_a, result_b) if r is None]
            assert len(winners) == 1
            assert len(rejections) == 1
            assert result_a is not None
            assert result_b is None
            assert repo.save_calls == 1
            conflict_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if call.kwargs.get("error") == "concurrent_save"
            ]
            assert len(conflict_calls) == 1

    async def test_save_in_flight_cleared_on_repo_error(self) -> None:
        """An exception in repo.save must clear in-flight so retries work."""

        class FailingRepo(GatedRepo):
            async def save(self, item: ApprovalItem) -> None:
                self.save_calls += 1
                if self.save_calls == 1:
                    msg = "boom"
                    raise ConstraintViolationError(msg, constraint="test")
                self.items[item.id] = item

        repo = FailingRepo()
        initial = _make_item()
        repo.items[initial.id] = initial
        store = ApprovalStore(repo=repo)  # type: ignore[arg-type]
        await store.get(initial.id)

        updated = initial.model_copy(update={"decision_reason": "first"})
        with pytest.raises(ConstraintViolationError):
            await store.save(updated)

        # In-flight set must be empty so the next save is not rejected.
        retry_result = await store.save(updated)
        assert retry_result is not None

    async def test_save_cancelled_after_repo_commit_invalidates_cache(
        self,
    ) -> None:
        """Cancellation after a committed repo write must evict the cache.

        Otherwise the next reader would serve the stale cached copy
        instead of the freshly committed repository state.
        """

        class CommittingThenCancellingRepo(GatedRepo):
            """Simulate a repo whose commit lands before cancellation."""

            async def save(self, item: ApprovalItem) -> None:
                # Commit first (the race window), then yield and let
                # the outer cancellation be delivered here.
                self.save_calls += 1
                self.items[item.id] = item
                await self.gate.wait()

        repo = CommittingThenCancellingRepo()
        initial = _make_item()
        repo.items[initial.id] = initial
        store = ApprovalStore(repo=repo)  # type: ignore[arg-type]
        await store.get(initial.id)  # warm the cache

        updated = initial.model_copy(update={"decision_reason": "cancelled"})
        task = asyncio.create_task(store.save(updated))
        await asyncio.sleep(0)  # let task enter repo.save and commit
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Repo has the new value; cache entry must have been evicted
        # so the next ``get`` reloads from the repository.
        assert repo.items[initial.id].decision_reason == "cancelled"
        assert initial.id not in store._items

        refreshed = await store.get(initial.id)
        assert refreshed is not None
        assert refreshed.decision_reason == "cancelled"


@pytest.mark.unit
class TestSaveIfPendingConcurrency:
    """save_if_pending: exactly one of two concurrent transitions wins."""

    async def test_concurrent_save_if_pending_exactly_one_wins(self) -> None:
        store = ApprovalStore()
        item = _make_item()
        await store.add(item)

        now = _now()
        approve = item.model_copy(
            update={
                "status": ApprovalStatus.APPROVED,
                "decided_at": now,
                "decided_by": "alice",
                "decision_reason": "looks good",
            },
        )
        reject = item.model_copy(
            update={
                "status": ApprovalStatus.REJECTED,
                "decided_at": now,
                "decided_by": "bob",
                "decision_reason": "nope",
            },
        )

        async with asyncio.TaskGroup() as tg:
            t_approve = tg.create_task(store.save_if_pending(approve))
            t_reject = tg.create_task(store.save_if_pending(reject))
        results = (t_approve.result(), t_reject.result())
        winners = [r for r in results if r is not None]
        losers = [r for r in results if r is None]
        assert len(winners) == 1
        assert len(losers) == 1

        stored = await store.get(item.id)
        assert stored is not None
        assert stored.status == winners[0].status


@pytest.mark.unit
class TestAddConcurrency:
    """add() must allow exactly one of two concurrent duplicates."""

    async def test_concurrent_add_same_id_exactly_one_succeeds(self) -> None:
        store = ApprovalStore()
        item_a = _make_item()
        item_b = _make_item()  # same id, same payload

        results = await asyncio.gather(
            store.add(item_a),
            store.add(item_b),
            return_exceptions=True,
        )
        # One succeeds (returns None), the other raises ConflictError.
        successes = [r for r in results if r is None]
        conflicts = [r for r in results if isinstance(r, ConflictError)]
        assert len(successes) == 1
        assert len(conflicts) == 1

        stored = await store.get(item_a.id)
        assert stored is not None


@pytest.mark.unit
class TestAddConstraintViolationPath:
    """add() surfaces repo constraint violations as ConflictError."""

    async def test_repo_constraint_violation_becomes_conflict_error(self) -> None:
        class ConstraintRepo(GatedRepo):
            async def save(self, item: ApprovalItem) -> None:
                del item
                self.save_calls += 1
                msg = "duplicate"
                raise ConstraintViolationError(msg, constraint="pk")

        repo = ConstraintRepo()
        store = ApprovalStore(repo=repo)  # type: ignore[arg-type]
        with pytest.raises(ConflictError, match="already exists"):
            await store.add(_make_item())


@pytest.mark.unit
class TestExpirationConcurrency:
    """Lazy expiration must not race with concurrent save() on the same item."""

    async def test_expiration_during_concurrent_save_serialised(self) -> None:
        store = ApprovalStore()
        now = _now()
        item = ApprovalItem(
            id="exp-concurrent",
            action_type="code:merge",
            title="Test",
            description="desc",
            requested_by="agent-dev",
            risk_level=ApprovalRiskLevel.LOW,
            status=ApprovalStatus.PENDING,
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
        store._items[item.id] = item

        # get() triggers expiration; save_if_pending sees non-PENDING stored state.
        async with asyncio.TaskGroup() as tg:
            get_task = tg.create_task(store.get(item.id))
            save_task = tg.create_task(
                store.save_if_pending(
                    item.model_copy(update={"status": ApprovalStatus.APPROVED}),
                ),
            )
        get_result = get_task.result()
        save_result = save_task.result()

        # After serialisation exactly one of these is true:
        #   (a) expiration won: get returns EXPIRED, save_if_pending returns None.
        #   (b) save won: get returns APPROVED (not expired), save returns APPROVED.
        assert get_result is not None
        if save_result is None:
            assert get_result.status == ApprovalStatus.EXPIRED
        else:
            assert save_result.status == ApprovalStatus.APPROVED
            assert get_result.status == ApprovalStatus.APPROVED
