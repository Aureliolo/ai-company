"""Tests for AG-UI event types and StreamEvent model."""

from datetime import UTC, datetime

import pytest

from synthorg.communication.event_stream.types import AgUiEventType, StreamEvent


@pytest.mark.unit
class TestAgUiEventType:
    def test_run_started_value(self) -> None:
        assert AgUiEventType.RUN_STARTED.value == "run_started"

    def test_run_finished_value(self) -> None:
        assert AgUiEventType.RUN_FINISHED.value == "run_finished"

    def test_run_error_value(self) -> None:
        assert AgUiEventType.RUN_ERROR.value == "run_error"

    def test_step_started_value(self) -> None:
        assert AgUiEventType.STEP_STARTED.value == "step_started"

    def test_step_finished_value(self) -> None:
        assert AgUiEventType.STEP_FINISHED.value == "step_finished"

    def test_step_failed_value(self) -> None:
        assert AgUiEventType.STEP_FAILED.value == "step_failed"

    def test_text_message_start_value(self) -> None:
        assert AgUiEventType.TEXT_MESSAGE_START.value == "text_message_start"

    def test_text_message_content_value(self) -> None:
        assert AgUiEventType.TEXT_MESSAGE_CONTENT.value == "text_message_content"

    def test_text_message_end_value(self) -> None:
        assert AgUiEventType.TEXT_MESSAGE_END.value == "text_message_end"

    def test_tool_call_start_value(self) -> None:
        assert AgUiEventType.TOOL_CALL_START.value == "tool_call_start"

    def test_tool_call_args_value(self) -> None:
        assert AgUiEventType.TOOL_CALL_ARGS.value == "tool_call_args"

    def test_tool_call_end_value(self) -> None:
        assert AgUiEventType.TOOL_CALL_END.value == "tool_call_end"

    def test_approval_interrupt_value(self) -> None:
        assert AgUiEventType.APPROVAL_INTERRUPT.value == "approval_interrupt"

    def test_approval_resumed_value(self) -> None:
        assert AgUiEventType.APPROVAL_RESUMED.value == "approval_resumed"

    def test_info_request_interrupt_value(self) -> None:
        assert AgUiEventType.INFO_REQUEST_INTERRUPT.value == "info_request_interrupt"

    def test_info_request_resumed_value(self) -> None:
        assert AgUiEventType.INFO_REQUEST_RESUMED.value == "info_request_resumed"

    def test_dissent_value(self) -> None:
        assert AgUiEventType.DISSENT.value == "synthorg:dissent"

    def test_all_members_count(self) -> None:
        assert len(AgUiEventType) == 17


@pytest.mark.unit
class TestStreamEvent:
    def _make_event(self, **overrides: object) -> StreamEvent:
        defaults: dict[str, object] = {
            "id": "evt-001",
            "type": AgUiEventType.RUN_STARTED,
            "timestamp": datetime(2026, 4, 13, tzinfo=UTC),
            "session_id": "session-abc",
            "correlation_id": None,
            "agent_id": None,
            "payload": {},
        }
        defaults.update(overrides)
        return StreamEvent(**defaults)  # type: ignore[arg-type]

    def test_construction(self) -> None:
        event = self._make_event()
        assert event.id == "evt-001"
        assert event.type == AgUiEventType.RUN_STARTED
        assert event.session_id == "session-abc"

    def test_frozen(self) -> None:
        event = self._make_event()
        with pytest.raises(Exception, match="frozen"):
            event.id = "changed"  # type: ignore[misc]

    def test_payload_deep_copied(self) -> None:
        original: dict[str, object] = {"key": "value", "nested": {"a": 1}}
        event = self._make_event(payload=original)
        original["key"] = "mutated"
        assert event.payload["key"] == "value"

    def test_optional_fields(self) -> None:
        event = self._make_event(
            correlation_id="corr-123",
            agent_id="agent-xyz",
        )
        assert event.correlation_id == "corr-123"
        assert event.agent_id == "agent-xyz"

    def test_blank_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            self._make_event(id="")

    def test_blank_session_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            self._make_event(session_id="")

    def test_whitespace_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            self._make_event(id="   ")
