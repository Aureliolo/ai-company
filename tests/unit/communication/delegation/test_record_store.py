"""Tests for DelegationRecordStore."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.communication.delegation.models import DelegationRecord
from synthorg.communication.delegation.record_store import (
    DelegationRecordStore,
)

_NOW = datetime(2026, 3, 24, 12, 0, 0, tzinfo=UTC)


def _make_record(  # noqa: PLR0913
    *,
    delegation_id: str = "del-001",
    delegator_id: str = "agent-manager",
    delegatee_id: str = "agent-worker",
    original_task_id: str = "task-parent",
    delegated_task_id: str = "del-abc123",
    timestamp: datetime = _NOW,
) -> DelegationRecord:
    return DelegationRecord(
        delegation_id=delegation_id,
        delegator_id=delegator_id,
        delegatee_id=delegatee_id,
        original_task_id=original_task_id,
        delegated_task_id=delegated_task_id,
        timestamp=timestamp,
    )


@pytest.mark.unit
class TestDelegationRecordStore:
    async def test_empty_store(self) -> None:
        store = DelegationRecordStore()
        records = await store.get_all_records()
        assert records == ()

    async def test_record_sync_and_retrieve(self) -> None:
        store = DelegationRecordStore()
        record = _make_record()
        store.record_sync(record)

        records = await store.get_all_records()
        assert len(records) == 1
        assert records[0].delegation_id == "del-001"

    async def test_filter_as_delegator(self) -> None:
        store = DelegationRecordStore()
        store.record_sync(
            _make_record(delegator_id="alice", delegatee_id="bob"),
        )
        store.record_sync(
            _make_record(
                delegation_id="del-002",
                delegator_id="bob",
                delegatee_id="charlie",
            ),
        )

        records = await store.get_records_as_delegator("alice")
        assert len(records) == 1
        assert records[0].delegator_id == "alice"

    async def test_filter_as_delegatee(self) -> None:
        store = DelegationRecordStore()
        store.record_sync(
            _make_record(delegator_id="alice", delegatee_id="bob"),
        )
        store.record_sync(
            _make_record(
                delegation_id="del-002",
                delegator_id="bob",
                delegatee_id="charlie",
            ),
        )

        records = await store.get_records_as_delegatee("bob")
        assert len(records) == 1
        assert records[0].delegatee_id == "bob"

    async def test_time_range_filtering(self) -> None:
        store = DelegationRecordStore()
        store.record_sync(
            _make_record(
                delegation_id="del-old",
                timestamp=_NOW - timedelta(hours=3),
            ),
        )
        store.record_sync(
            _make_record(
                delegation_id="del-mid",
                timestamp=_NOW - timedelta(hours=1),
            ),
        )
        store.record_sync(
            _make_record(delegation_id="del-new", timestamp=_NOW),
        )

        records = await store.get_all_records(
            start=_NOW - timedelta(hours=2),
            end=_NOW,
        )
        assert len(records) == 1
        assert records[0].delegation_id == "del-mid"

    async def test_get_all_records_returns_all(self) -> None:
        store = DelegationRecordStore()
        store.record_sync(_make_record(delegation_id="del-001"))
        store.record_sync(_make_record(delegation_id="del-002"))

        records = await store.get_all_records()
        assert len(records) == 2

    async def test_invalid_time_range(self) -> None:
        store = DelegationRecordStore()
        with pytest.raises(ValueError, match=r"start.*must be before"):
            await store.get_all_records(
                start=_NOW,
                end=_NOW - timedelta(hours=1),
            )

    async def test_equal_start_end_raises(self) -> None:
        store = DelegationRecordStore()
        with pytest.raises(ValueError, match=r"start.*must be before"):
            await store.get_all_records(start=_NOW, end=_NOW)

    async def test_returns_immutable_tuple(self) -> None:
        store = DelegationRecordStore()
        store.record_sync(_make_record())
        records = await store.get_all_records()
        assert isinstance(records, tuple)

    async def test_delegator_time_range_filtering(self) -> None:
        """Time range filtering works on get_records_as_delegator."""
        store = DelegationRecordStore()
        store.record_sync(
            _make_record(
                delegation_id="del-old",
                delegator_id="alice",
                timestamp=_NOW - timedelta(hours=3),
            ),
        )
        store.record_sync(
            _make_record(
                delegation_id="del-mid",
                delegator_id="alice",
                timestamp=_NOW - timedelta(hours=1),
            ),
        )

        # Half-open interval: start <= ts < end
        records = await store.get_records_as_delegator(
            "alice",
            start=_NOW - timedelta(hours=2),
            end=_NOW,
        )
        assert len(records) == 1
        assert records[0].delegation_id == "del-mid"

    async def test_delegatee_time_range_filtering(self) -> None:
        """Time range filtering works on get_records_as_delegatee."""
        store = DelegationRecordStore()
        store.record_sync(
            _make_record(
                delegation_id="del-old",
                delegatee_id="bob",
                timestamp=_NOW - timedelta(hours=3),
            ),
        )
        store.record_sync(
            _make_record(
                delegation_id="del-mid",
                delegatee_id="bob",
                timestamp=_NOW - timedelta(hours=1),
            ),
        )

        # Half-open interval: start <= ts < end
        records = await store.get_records_as_delegatee(
            "bob",
            start=_NOW - timedelta(hours=2),
            end=_NOW,
        )
        assert len(records) == 1
        assert records[0].delegation_id == "del-mid"


# ── Eviction ────────────────────────────────────────────────


@pytest.mark.unit
class TestDelegationRecordStoreEviction:
    """FIFO eviction when record count exceeds max_records."""

    async def test_eviction_when_max_exceeded(self) -> None:
        store = DelegationRecordStore(max_records=3)
        for i in range(5):
            store.record_sync(
                _make_record(
                    delegation_id=f"del-{i:03d}",
                    timestamp=_NOW + timedelta(seconds=i),
                ),
            )
        records = await store.get_all_records()
        assert len(records) == 3
        # Oldest two evicted
        assert records[0].delegation_id == "del-002"
        assert records[2].delegation_id == "del-004"

    async def test_no_eviction_below_max(self) -> None:
        store = DelegationRecordStore(max_records=10)
        for i in range(5):
            store.record_sync(
                _make_record(delegation_id=f"del-{i:03d}"),
            )
        records = await store.get_all_records()
        assert len(records) == 5

    def test_max_records_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_records must be >= 1"):
            DelegationRecordStore(max_records=0)

    def test_max_records_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_records must be >= 1"):
            DelegationRecordStore(max_records=-1)
