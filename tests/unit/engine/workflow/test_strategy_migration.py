"""Tests for strategy migration detection and notification."""

from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.communication.enums import MessagePriority, MessageType
from synthorg.engine.workflow.ceremony_policy import CeremonyStrategyType
from synthorg.engine.workflow.strategy_migration import (
    StrategyMigrationInfo,
    detect_strategy_migration,
    format_migration_warning,
    format_reorder_prompt,
    notify_strategy_migration,
)

# ── StrategyMigrationInfo model ────────────────────────────────────


class TestStrategyMigrationInfo:
    """StrategyMigrationInfo construction and immutability."""

    @pytest.mark.unit
    def test_construction(self) -> None:
        info = StrategyMigrationInfo(
            sprint_id="sprint-42",
            previous_strategy=CeremonyStrategyType.TASK_DRIVEN,
            new_strategy=CeremonyStrategyType.CALENDAR,
            velocity_history_size=5,
        )
        assert info.sprint_id == "sprint-42"
        assert info.previous_strategy is CeremonyStrategyType.TASK_DRIVEN
        assert info.new_strategy is CeremonyStrategyType.CALENDAR
        assert info.velocity_history_size == 5

    @pytest.mark.unit
    def test_frozen(self) -> None:
        info = StrategyMigrationInfo(
            sprint_id="sprint-1",
            previous_strategy=CeremonyStrategyType.TASK_DRIVEN,
            new_strategy=CeremonyStrategyType.HYBRID,
            velocity_history_size=0,
        )
        with pytest.raises(Exception):  # noqa: B017, PT011
            info.sprint_id = "modified"  # type: ignore[misc]

    @pytest.mark.unit
    def test_same_strategy_rejected(self) -> None:
        """Model validator rejects same previous and new strategy."""
        with pytest.raises(ValueError, match="must differ"):
            StrategyMigrationInfo(
                sprint_id="sprint-1",
                previous_strategy=CeremonyStrategyType.HYBRID,
                new_strategy=CeremonyStrategyType.HYBRID,
                velocity_history_size=0,
            )

    @pytest.mark.unit
    def test_blank_sprint_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least 1 character"):
            StrategyMigrationInfo(
                sprint_id="",
                previous_strategy=CeremonyStrategyType.TASK_DRIVEN,
                new_strategy=CeremonyStrategyType.CALENDAR,
                velocity_history_size=0,
            )

    @pytest.mark.unit
    def test_negative_velocity_history_rejected(self) -> None:
        with pytest.raises(
            ValueError,
            match="greater than or equal",
        ):
            StrategyMigrationInfo(
                sprint_id="sprint-1",
                previous_strategy=CeremonyStrategyType.TASK_DRIVEN,
                new_strategy=CeremonyStrategyType.CALENDAR,
                velocity_history_size=-1,
            )


# ── detect_strategy_migration ──────────────────────────────────────


class TestDetectStrategyMigration:
    """detect_strategy_migration() tests."""

    @pytest.mark.unit
    def test_none_previous_returns_none(self) -> None:
        """First activation (no previous strategy) produces no migration."""
        result = detect_strategy_migration(
            previous_strategy_type=None,
            new_strategy_type=CeremonyStrategyType.TASK_DRIVEN,
            sprint_id="sprint-1",
            velocity_history_size=0,
        )
        assert result is None

    @pytest.mark.unit
    def test_same_strategy_returns_none(self) -> None:
        """Same strategy type re-used produces no migration."""
        result = detect_strategy_migration(
            previous_strategy_type=CeremonyStrategyType.HYBRID,
            new_strategy_type=CeremonyStrategyType.HYBRID,
            sprint_id="sprint-2",
            velocity_history_size=3,
        )
        assert result is None

    @pytest.mark.unit
    def test_different_strategy_returns_migration_info(self) -> None:
        result = detect_strategy_migration(
            previous_strategy_type=CeremonyStrategyType.TASK_DRIVEN,
            new_strategy_type=CeremonyStrategyType.CALENDAR,
            sprint_id="sprint-3",
            velocity_history_size=5,
        )
        assert result is not None
        assert result.sprint_id == "sprint-3"
        assert result.previous_strategy is CeremonyStrategyType.TASK_DRIVEN
        assert result.new_strategy is CeremonyStrategyType.CALENDAR

        assert result.velocity_history_size == 5

    _ALL_NON_TASK_DRIVEN: ClassVar[list[CeremonyStrategyType]] = [
        s for s in CeremonyStrategyType if s is not CeremonyStrategyType.TASK_DRIVEN
    ]

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "new_strategy",
        _ALL_NON_TASK_DRIVEN,
        ids=[s.value for s in _ALL_NON_TASK_DRIVEN],
    )
    def test_all_strategy_changes_from_task_driven(
        self,
        new_strategy: CeremonyStrategyType,
    ) -> None:
        """Changing from task_driven to any other strategy produces migration info."""
        result = detect_strategy_migration(
            previous_strategy_type=CeremonyStrategyType.TASK_DRIVEN,
            new_strategy_type=new_strategy,
            sprint_id="sprint-param",
            velocity_history_size=2,
        )
        assert result is not None
        assert result.new_strategy is new_strategy
        assert result.previous_strategy is CeremonyStrategyType.TASK_DRIVEN


# ── format helpers ─────────────────────────────────────────────────


def _sample_info() -> StrategyMigrationInfo:
    return StrategyMigrationInfo(
        sprint_id="sprint-10",
        previous_strategy=CeremonyStrategyType.TASK_DRIVEN,
        new_strategy=CeremonyStrategyType.HYBRID,
        velocity_window_reset=True,
        velocity_history_size=4,
    )


class TestFormatMigrationWarning:
    """format_migration_warning() tests."""

    @pytest.mark.unit
    def test_contains_strategy_names(self) -> None:
        text = format_migration_warning(_sample_info())
        assert "task_driven" in text
        assert "hybrid" in text

    @pytest.mark.unit
    def test_contains_sprint_id(self) -> None:
        text = format_migration_warning(_sample_info())
        assert "sprint-10" in text

    @pytest.mark.unit
    def test_mentions_velocity_reset(self) -> None:
        text = format_migration_warning(_sample_info())
        assert "velocity" in text.lower()


class TestFormatReorderPrompt:
    """format_reorder_prompt() tests."""

    @pytest.mark.unit
    def test_contains_new_strategy(self) -> None:
        text = format_reorder_prompt(_sample_info())
        assert "hybrid" in text

    @pytest.mark.unit
    def test_contains_history_size(self) -> None:
        text = format_reorder_prompt(_sample_info())
        assert "4" in text


# ── notify_strategy_migration ──────────────────────────────────────


def _make_mock_messenger() -> MagicMock:
    mock = MagicMock()
    mock.broadcast = AsyncMock(return_value=MagicMock())
    mock.send_message = AsyncMock(return_value=MagicMock())
    return mock


class TestNotifyStrategyMigration:
    """notify_strategy_migration() tests."""

    @pytest.mark.unit
    async def test_broadcasts_announcement(self) -> None:
        messenger = _make_mock_messenger()
        await notify_strategy_migration(_sample_info(), messenger)
        messenger.broadcast.assert_called_once()
        _, kwargs = messenger.broadcast.call_args
        assert kwargs["message_type"] is MessageType.ANNOUNCEMENT
        assert kwargs["priority"] is MessagePriority.HIGH

    @pytest.mark.unit
    async def test_sends_reorder_task_update(self) -> None:
        messenger = _make_mock_messenger()
        await notify_strategy_migration(_sample_info(), messenger)
        messenger.send_message.assert_called_once()
        _, kwargs = messenger.send_message.call_args
        assert kwargs["message_type"] is MessageType.TASK_UPDATE
        assert kwargs["priority"] is MessagePriority.HIGH

    @pytest.mark.unit
    async def test_broadcast_failure_still_sends_reorder(self) -> None:
        """Broadcast failure does not prevent reorder prompt."""
        messenger = _make_mock_messenger()
        messenger.broadcast = AsyncMock(side_effect=RuntimeError("bus down"))
        await notify_strategy_migration(_sample_info(), messenger)
        messenger.send_message.assert_called_once()

    @pytest.mark.unit
    async def test_send_message_failure_swallowed(self) -> None:
        """send_message failure is swallowed (broadcast succeeds)."""
        messenger = _make_mock_messenger()
        messenger.send_message = AsyncMock(
            side_effect=RuntimeError("channel not found"),
        )
        await notify_strategy_migration(_sample_info(), messenger)
        messenger.broadcast.assert_called_once()

    @pytest.mark.unit
    async def test_memory_error_from_broadcast_propagates(self) -> None:
        messenger = _make_mock_messenger()
        messenger.broadcast = AsyncMock(side_effect=MemoryError)
        with pytest.raises(MemoryError):
            await notify_strategy_migration(_sample_info(), messenger)

    @pytest.mark.unit
    async def test_memory_error_from_send_message_propagates(self) -> None:
        messenger = _make_mock_messenger()
        messenger.send_message = AsyncMock(side_effect=MemoryError)
        with pytest.raises(MemoryError):
            await notify_strategy_migration(_sample_info(), messenger)

    @pytest.mark.unit
    async def test_recursion_error_from_broadcast_propagates(self) -> None:
        messenger = _make_mock_messenger()
        messenger.broadcast = AsyncMock(side_effect=RecursionError)
        with pytest.raises(RecursionError):
            await notify_strategy_migration(_sample_info(), messenger)

    @pytest.mark.unit
    async def test_recursion_error_from_send_message_propagates(
        self,
    ) -> None:
        messenger = _make_mock_messenger()
        messenger.send_message = AsyncMock(side_effect=RecursionError)
        with pytest.raises(RecursionError):
            await notify_strategy_migration(_sample_info(), messenger)

    @pytest.mark.unit
    async def test_custom_channel_and_role(self) -> None:
        messenger = _make_mock_messenger()
        await notify_strategy_migration(
            _sample_info(),
            messenger,
            responsible_role="department_head",
            channel="#planning",
        )
        _, kwargs = messenger.send_message.call_args
        assert kwargs["channel"] == "#planning"
        assert kwargs["to"] == "department_head"
