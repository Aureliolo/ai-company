"""Tests for ToolInvocationTracker."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.tools.invocation_record import ToolInvocationRecord
from synthorg.tools.invocation_tracker import ToolInvocationTracker

_NOW = datetime(2026, 3, 24, 12, 0, 0, tzinfo=UTC)


def _make_record(
    *,
    agent_id: str = "agent-001",
    tool_name: str = "read_file",
    is_success: bool = True,
    timestamp: datetime = _NOW,
) -> ToolInvocationRecord:
    return ToolInvocationRecord(
        agent_id=agent_id,
        tool_name=tool_name,
        is_success=is_success,
        timestamp=timestamp,
    )


@pytest.mark.unit
class TestToolInvocationTracker:
    async def test_empty_tracker(self) -> None:
        tracker = ToolInvocationTracker()
        records = await tracker.get_records()
        assert records == ()

    async def test_record_and_retrieve(self) -> None:
        tracker = ToolInvocationTracker()
        record = _make_record()
        await tracker.record(record)

        records = await tracker.get_records()
        assert len(records) == 1
        assert records[0].agent_id == "agent-001"

    async def test_filter_by_agent_id(self) -> None:
        tracker = ToolInvocationTracker()
        await tracker.record(_make_record(agent_id="agent-001"))
        await tracker.record(_make_record(agent_id="agent-002"))

        records = await tracker.get_records(agent_id="agent-001")
        assert len(records) == 1
        assert records[0].agent_id == "agent-001"

    async def test_filter_by_time_range(self) -> None:
        tracker = ToolInvocationTracker()
        await tracker.record(
            _make_record(timestamp=_NOW - timedelta(hours=3)),
        )
        await tracker.record(
            _make_record(timestamp=_NOW - timedelta(hours=1)),
        )
        await tracker.record(_make_record(timestamp=_NOW))

        records = await tracker.get_records(
            start=_NOW - timedelta(hours=2),
            end=_NOW,
        )
        assert len(records) == 1

    async def test_combined_filters(self) -> None:
        tracker = ToolInvocationTracker()
        await tracker.record(
            _make_record(
                agent_id="agent-001",
                timestamp=_NOW - timedelta(hours=1),
            ),
        )
        await tracker.record(
            _make_record(
                agent_id="agent-002",
                timestamp=_NOW - timedelta(hours=1),
            ),
        )

        records = await tracker.get_records(
            agent_id="agent-001",
            start=_NOW - timedelta(hours=2),
            end=_NOW,
        )
        assert len(records) == 1
        assert records[0].agent_id == "agent-001"

    async def test_invalid_time_range(self) -> None:
        tracker = ToolInvocationTracker()
        with pytest.raises(ValueError, match=r"start.*must be before"):
            await tracker.get_records(start=_NOW, end=_NOW - timedelta(hours=1))

    async def test_equal_start_end_raises(self) -> None:
        tracker = ToolInvocationTracker()
        with pytest.raises(ValueError, match=r"start.*must be before"):
            await tracker.get_records(start=_NOW, end=_NOW)

    async def test_returns_immutable_tuple(self) -> None:
        tracker = ToolInvocationTracker()
        await tracker.record(_make_record())
        records = await tracker.get_records()
        assert isinstance(records, tuple)


# ── Eviction ────────────────────────────────────────────────


@pytest.mark.unit
class TestToolInvocationTrackerEviction:
    """FIFO eviction when record count exceeds max_records."""

    async def test_eviction_when_max_exceeded(self) -> None:
        tracker = ToolInvocationTracker(max_records=3)
        for i in range(5):
            await tracker.record(
                _make_record(
                    agent_id=f"agent-{i:03d}",
                    timestamp=_NOW + timedelta(seconds=i),
                ),
            )
        records = await tracker.get_records()
        assert len(records) == 3
        # Oldest two evicted (agent-000, agent-001)
        assert records[0].agent_id == "agent-002"
        assert records[2].agent_id == "agent-004"

    async def test_no_eviction_below_max(self) -> None:
        tracker = ToolInvocationTracker(max_records=10)
        for i in range(5):
            await tracker.record(
                _make_record(agent_id=f"agent-{i:03d}"),
            )
        records = await tracker.get_records()
        assert len(records) == 5

    @pytest.mark.parametrize("value", [0, -1], ids=["zero", "negative"])
    def test_max_records_invalid_rejected(self, value: int) -> None:
        with pytest.raises(ValueError, match="max_records must be >= 1"):
            ToolInvocationTracker(max_records=value)

    async def test_no_eviction_at_exact_max(self) -> None:
        tracker = ToolInvocationTracker(max_records=3)
        for i in range(3):
            await tracker.record(
                _make_record(agent_id=f"agent-{i:03d}"),
            )
        records = await tracker.get_records()
        assert len(records) == 3
        assert records[0].agent_id == "agent-000"
        assert records[2].agent_id == "agent-002"

    async def test_max_records_one_keeps_only_last(self) -> None:
        tracker = ToolInvocationTracker(max_records=1)
        await tracker.record(_make_record(agent_id="agent-first"))
        await tracker.record(_make_record(agent_id="agent-last"))
        records = await tracker.get_records()
        assert len(records) == 1
        assert records[0].agent_id == "agent-last"
