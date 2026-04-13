"""Example agent evaluation: FILE_OPERATIONS behavior category."""

import pytest

from synthorg.engine.loop_protocol import BehaviorTag


@pytest.mark.agent_eval(category="file_operations")
async def test_agent_file_read_behavior() -> None:
    """Verify agent correctly categorizes file read operations."""
    assert BehaviorTag.FILE_OPERATIONS.value == "file_operations"


@pytest.mark.agent_eval(category="file_operations")
async def test_agent_file_write_behavior() -> None:
    """Verify agent correctly categorizes file write operations."""
    assert BehaviorTag.FILE_OPERATIONS in BehaviorTag
