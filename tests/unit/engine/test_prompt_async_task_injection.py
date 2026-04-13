"""Tests for async task state injection into system prompts."""

from datetime import UTC, datetime

import pytest

from synthorg.communication.async_tasks.models import (
    AsyncTaskRecord,
    AsyncTaskStateChannel,
    AsyncTaskStatus,
)
from synthorg.core.agent import AgentIdentity
from synthorg.engine.prompt import build_system_prompt


def _make_record(**overrides: object) -> AsyncTaskRecord:
    defaults: dict[str, object] = {
        "task_id": "task-1",
        "agent_name": "worker-1",
        "status": AsyncTaskStatus.RUNNING,
        "created_at": datetime(2026, 4, 14, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 14, tzinfo=UTC),
    }
    defaults.update(overrides)
    return AsyncTaskRecord(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestAsyncTaskPromptInjection:
    def test_section_present_when_records_exist(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        channel = AsyncTaskStateChannel().with_record(_make_record())
        prompt = build_system_prompt(
            agent=sample_agent_with_personality,
            async_task_state=channel,
        )
        assert "Active Async Tasks" in prompt.content
        assert "task-1" in prompt.content
        assert "worker-1" in prompt.content
        assert "running" in prompt.content
        assert "async_tasks" in prompt.sections

    def test_section_absent_when_empty(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        channel = AsyncTaskStateChannel()
        prompt = build_system_prompt(
            agent=sample_agent_with_personality,
            async_task_state=channel,
        )
        assert "Active Async Tasks" not in prompt.content

    def test_section_absent_when_none(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        prompt = build_system_prompt(
            agent=sample_agent_with_personality,
            async_task_state=None,
        )
        assert "Active Async Tasks" not in prompt.content

    def test_multiple_tasks_listed(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        channel = (
            AsyncTaskStateChannel()
            .with_record(_make_record(task_id="t-1", agent_name="a-1"))
            .with_record(_make_record(task_id="t-2", agent_name="a-2"))
        )
        prompt = build_system_prompt(
            agent=sample_agent_with_personality,
            async_task_state=channel,
        )
        assert "t-1" in prompt.content
        assert "t-2" in prompt.content
        assert "a-1" in prompt.content
        assert "a-2" in prompt.content
