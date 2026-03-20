"""Tests for the compaction summarizer callback factory."""

import pytest

from synthorg.core.agent import AgentIdentity
from synthorg.engine.compaction.models import CompactionConfig
from synthorg.engine.compaction.summarizer import make_compaction_callback
from synthorg.engine.context import AgentContext
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage

pytestmark = pytest.mark.timeout(30)


def _msg(role: MessageRole, content: str) -> ChatMessage:
    """Create a chat message."""
    return ChatMessage(role=role, content=content)


def _build_context(
    identity: AgentIdentity,
    messages: tuple[ChatMessage, ...],
    *,
    capacity: int = 1000,
    fill: int = 900,
    turn_count: int = 5,
) -> AgentContext:
    """Build an AgentContext with given messages and fill level."""
    return AgentContext.from_identity(
        identity,
        context_capacity_tokens=capacity,
    ).model_copy(
        update={
            "conversation": messages,
            "context_fill_tokens": fill,
            "turn_count": turn_count,
        },
    )


@pytest.mark.unit
class TestMakeCompactionCallback:
    """make_compaction_callback factory and compaction logic."""

    async def test_below_threshold_returns_none(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        config = CompactionConfig(fill_threshold_percent=80.0)
        callback = make_compaction_callback(config=config)

        ctx = _build_context(
            sample_agent_with_personality,
            messages=(
                _msg(MessageRole.SYSTEM, "sys prompt"),
                _msg(MessageRole.USER, "q1"),
                _msg(MessageRole.ASSISTANT, "a1"),
                _msg(MessageRole.USER, "q2"),
                _msg(MessageRole.ASSISTANT, "a2"),
            ),
            capacity=1000,
            fill=700,  # 70% < 80%
        )
        result = await callback(ctx)
        assert result is None

    async def test_above_threshold_compresses(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        config = CompactionConfig(
            fill_threshold_percent=80.0,
            min_messages_to_compact=4,
            preserve_recent_turns=1,
        )
        callback = make_compaction_callback(config=config)

        # 10 messages: sys + 4 user/assistant pairs + 1 user
        messages = (
            _msg(MessageRole.SYSTEM, "system prompt"),
            _msg(MessageRole.USER, "question 1"),
            _msg(MessageRole.ASSISTANT, "answer 1"),
            _msg(MessageRole.USER, "question 2"),
            _msg(MessageRole.ASSISTANT, "answer 2"),
            _msg(MessageRole.USER, "question 3"),
            _msg(MessageRole.ASSISTANT, "answer 3"),
            _msg(MessageRole.USER, "question 4"),
            _msg(MessageRole.ASSISTANT, "answer 4"),
            _msg(MessageRole.USER, "question 5"),
        )
        ctx = _build_context(
            sample_agent_with_personality,
            messages=messages,
            capacity=1000,
            fill=850,  # 85% > 80%
        )
        result = await callback(ctx)
        assert result is not None
        # Should have: sys_msg + summary_msg + last 2 messages
        assert len(result.conversation) < len(messages)
        # System message preserved
        assert result.conversation[0].role == MessageRole.SYSTEM
        assert result.conversation[0].content == "system prompt"
        # Summary is second message
        assert result.conversation[1].role == MessageRole.SYSTEM
        assert "Archived" in (result.conversation[1].content or "")
        # Compression metadata set
        assert result.compression_metadata is not None
        assert result.compression_metadata.compactions_performed == 1
        assert result.compression_metadata.archived_turns > 0

    async def test_too_few_messages_returns_none(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        config = CompactionConfig(min_messages_to_compact=4)
        callback = make_compaction_callback(config=config)

        ctx = _build_context(
            sample_agent_with_personality,
            messages=(
                _msg(MessageRole.SYSTEM, "sys"),
                _msg(MessageRole.USER, "q"),
                _msg(MessageRole.ASSISTANT, "a"),
            ),
            capacity=100,
            fill=95,  # 95% but only 3 messages
        )
        result = await callback(ctx)
        assert result is None

    async def test_nothing_to_archive_returns_none(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        config = CompactionConfig(
            preserve_recent_turns=3,
            min_messages_to_compact=2,
        )
        callback = make_compaction_callback(config=config)

        # 7 messages: sys + 3 pairs = all preserved
        messages = (
            _msg(MessageRole.SYSTEM, "sys"),
            _msg(MessageRole.USER, "q1"),
            _msg(MessageRole.ASSISTANT, "a1"),
            _msg(MessageRole.USER, "q2"),
            _msg(MessageRole.ASSISTANT, "a2"),
            _msg(MessageRole.USER, "q3"),
            _msg(MessageRole.ASSISTANT, "a3"),
        )
        ctx = _build_context(
            sample_agent_with_personality,
            messages=messages,
            capacity=100,
            fill=95,
        )
        result = await callback(ctx)
        assert result is None

    async def test_unknown_capacity_returns_none(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        config = CompactionConfig()
        callback = make_compaction_callback(config=config)

        ctx = AgentContext.from_identity(
            sample_agent_with_personality,
        ).model_copy(
            update={
                "conversation": (
                    _msg(MessageRole.SYSTEM, "sys"),
                    _msg(MessageRole.USER, "q"),
                    _msg(MessageRole.ASSISTANT, "a"),
                    _msg(MessageRole.USER, "q"),
                    _msg(MessageRole.ASSISTANT, "a"),
                ),
                "context_fill_tokens": 9999,
            },
        )
        # No capacity set, so fill_percent is None
        result = await callback(ctx)
        assert result is None

    async def test_multiple_compactions_increment(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        config = CompactionConfig(
            fill_threshold_percent=80.0,
            min_messages_to_compact=4,
            preserve_recent_turns=1,
        )
        callback = make_compaction_callback(config=config)

        messages = tuple(
            _msg(
                MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                f"msg {i}" * 20,
            )
            for i in range(12)
        )
        messages = (_msg(MessageRole.SYSTEM, "sys"), *messages)

        ctx = _build_context(
            sample_agent_with_personality,
            messages=messages,
            capacity=1000,
            fill=850,
        )
        result1 = await callback(ctx)
        assert result1 is not None
        assert result1.compression_metadata is not None
        assert result1.compression_metadata.compactions_performed == 1

        # Simulate more messages added after first compaction
        new_msgs = result1.conversation + tuple(
            _msg(
                MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                f"new msg {i}" * 20,
            )
            for i in range(8)
        )
        ctx2 = result1.model_copy(
            update={
                "conversation": new_msgs,
                "context_fill_tokens": 900,
            },
        )
        result2 = await callback(ctx2)
        assert result2 is not None
        assert result2.compression_metadata is not None
        assert result2.compression_metadata.compactions_performed == 2


@pytest.mark.unit
class TestCompactionSanitization:
    """Assistant content snippets are sanitized in compaction summaries."""

    @pytest.mark.parametrize(
        ("user_prompt", "assistant_text", "forbidden_substr", "expected_token"),
        [
            pytest.param(
                "read the config",
                r"I read C:\Users\dev\project\secrets.yaml and found credentials",
                "C:\\Users",
                "[REDACTED_PATH]",
                id="path",
            ),
            pytest.param(
                "call the API",
                "Called https://api.internal.io/v1/secret?key=abc123 successfully",
                "https://",
                "[REDACTED_URL]",
                id="url",
            ),
        ],
    )
    async def test_assistant_snippet_sanitized(
        self,
        sample_agent_with_personality: AgentIdentity,
        user_prompt: str,
        assistant_text: str,
        forbidden_substr: str,
        expected_token: str,
    ) -> None:
        config = CompactionConfig(
            fill_threshold_percent=80.0,
            min_messages_to_compact=4,
            preserve_recent_turns=1,
        )
        callback = make_compaction_callback(config=config)

        messages = (
            _msg(MessageRole.SYSTEM, "system prompt"),
            _msg(MessageRole.USER, user_prompt),
            _msg(MessageRole.ASSISTANT, assistant_text),
            _msg(MessageRole.USER, "what next"),
            _msg(MessageRole.ASSISTANT, "processing data now"),
            _msg(MessageRole.USER, "continue"),
            _msg(MessageRole.ASSISTANT, "done with the task"),
            _msg(MessageRole.USER, "thanks"),
        )
        ctx = _build_context(
            sample_agent_with_personality,
            messages=messages,
            capacity=1000,
            fill=850,
        )
        result = await callback(ctx)
        assert result is not None
        summary_msg = result.conversation[1]
        assert summary_msg.content is not None
        assert forbidden_substr not in summary_msg.content
        assert expected_token in summary_msg.content

    async def test_assistant_long_path_crossing_boundary_is_sanitized(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """A path crossing the 100-char snippet boundary is still redacted."""
        config = CompactionConfig(
            fill_threshold_percent=80.0,
            min_messages_to_compact=4,
            preserve_recent_turns=1,
        )
        callback = make_compaction_callback(config=config)

        long_path = "C:\\Users\\dev\\" + ("nested\\" * 20) + "secrets.yaml"
        messages = (
            _msg(MessageRole.SYSTEM, "system prompt"),
            _msg(MessageRole.USER, "analyze logs"),
            _msg(
                MessageRole.ASSISTANT,
                f"I inspected {long_path} and extracted values",
            ),
            _msg(MessageRole.USER, "continue"),
            _msg(MessageRole.ASSISTANT, "working"),
            _msg(MessageRole.USER, "continue"),
            _msg(MessageRole.ASSISTANT, "done"),
            _msg(MessageRole.USER, "thanks"),
        )
        ctx = _build_context(
            sample_agent_with_personality,
            messages=messages,
            capacity=1000,
            fill=850,
        )
        result = await callback(ctx)
        assert result is not None
        summary_msg = result.conversation[1]
        assert summary_msg.content is not None
        assert "C:\\Users\\dev" not in summary_msg.content
        assert "[REDACTED_PATH]" in summary_msg.content
