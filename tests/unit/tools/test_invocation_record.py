"""Tests for ToolInvocationRecord model validation."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.tools.invocation_record import ToolInvocationRecord

_NOW = datetime(2026, 3, 24, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
class TestToolInvocationRecordValidation:
    def test_success_with_no_error_message(self) -> None:
        record = ToolInvocationRecord(
            agent_id="agent-001",
            tool_name="read_file",
            is_success=True,
            timestamp=_NOW,
        )
        assert record.is_success is True
        assert record.error_message is None

    def test_success_with_error_message_rejected(self) -> None:
        with pytest.raises(
            ValidationError,
            match=r"error_message must be None when is_success is True",
        ):
            ToolInvocationRecord(
                agent_id="agent-001",
                tool_name="read_file",
                is_success=True,
                timestamp=_NOW,
                error_message="oops",
            )

    def test_failure_with_error_message(self) -> None:
        record = ToolInvocationRecord(
            agent_id="agent-001",
            tool_name="write_file",
            is_success=False,
            timestamp=_NOW,
            error_message="Permission denied",
        )
        assert record.is_success is False
        assert record.error_message == "Permission denied"

    def test_failure_without_error_message_allowed(self) -> None:
        record = ToolInvocationRecord(
            agent_id="agent-001",
            tool_name="exec_cmd",
            is_success=False,
            timestamp=_NOW,
            error_message=None,
        )
        assert record.is_success is False
        assert record.error_message is None

    def test_frozen_model(self) -> None:
        record = ToolInvocationRecord(
            agent_id="agent-001",
            tool_name="read_file",
            is_success=True,
            timestamp=_NOW,
        )
        with pytest.raises(ValidationError):
            record.agent_id = "other"  # type: ignore[misc]

    def test_auto_generated_id(self) -> None:
        r1 = ToolInvocationRecord(
            agent_id="agent-001",
            tool_name="read_file",
            is_success=True,
            timestamp=_NOW,
        )
        r2 = ToolInvocationRecord(
            agent_id="agent-001",
            tool_name="read_file",
            is_success=True,
            timestamp=_NOW,
        )
        assert r1.id != r2.id
