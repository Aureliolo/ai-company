"""Tests for PolicyGateMiddleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.engine.middleware.models import ToolCallResult
from synthorg.engine.middleware.policy_gate import PolicyGateMiddleware
from synthorg.security.policy_engine.models import PolicyDecision


def _make_ctx(agent_id: str = "agent-001") -> MagicMock:
    """Create a mock AgentMiddlewareContext."""
    ctx = MagicMock()
    ctx.agent_id = agent_id
    ctx.task_id = "task-001"
    ctx.metadata = {}
    return ctx


def _make_allow_engine() -> AsyncMock:
    """Create a mock PolicyEngine that always allows."""
    engine = AsyncMock()
    engine.name = "test-engine"
    engine.evaluate = AsyncMock(
        return_value=PolicyDecision(
            allow=True,
            reason="Policy permits",
            latency_ms=0.1,
        ),
    )
    return engine


def _make_deny_engine(reason: str = "Policy denies") -> AsyncMock:
    """Create a mock PolicyEngine that always denies."""
    engine = AsyncMock()
    engine.name = "test-engine"
    engine.evaluate = AsyncMock(
        return_value=PolicyDecision(
            allow=False,
            reason=reason,
            latency_ms=0.2,
        ),
    )
    return engine


@pytest.mark.unit
class TestPolicyGateMiddleware:
    """Tests for PolicyGateMiddleware wrap_tool_call."""

    async def test_allow_passes_through(self) -> None:
        engine = _make_allow_engine()
        mw = PolicyGateMiddleware(
            policy_engine=engine,
            evaluation_mode="enforce",
        )
        ctx = _make_ctx()
        expected = ToolCallResult(
            tool_name="read_file",
            output="file content",
        )
        call = AsyncMock(return_value=expected)

        result = await mw.wrap_tool_call(ctx, call)
        assert result == expected
        call.assert_awaited_once_with(ctx)

    async def test_deny_enforce_blocks(self) -> None:
        engine = _make_deny_engine("Not allowed by policy")
        mw = PolicyGateMiddleware(
            policy_engine=engine,
            evaluation_mode="enforce",
        )
        ctx = _make_ctx()
        call = AsyncMock()

        result = await mw.wrap_tool_call(ctx, call)
        assert result.success is False
        assert "Not allowed by policy" in (result.error or "")
        call.assert_not_awaited()

    async def test_deny_log_only_passes_through(self) -> None:
        engine = _make_deny_engine()
        mw = PolicyGateMiddleware(
            policy_engine=engine,
            evaluation_mode="log_only",
        )
        ctx = _make_ctx()
        expected = ToolCallResult(
            tool_name="read_file",
            output="file content",
        )
        call = AsyncMock(return_value=expected)

        result = await mw.wrap_tool_call(ctx, call)
        assert result == expected
        call.assert_awaited_once_with(ctx)

    async def test_name_property(self) -> None:
        engine = _make_allow_engine()
        mw = PolicyGateMiddleware(
            policy_engine=engine,
            evaluation_mode="enforce",
        )
        assert mw.name == "policy_gate"

    async def test_none_engine_passes_through(self) -> None:
        """When no engine is configured, middleware passes through."""
        mw = PolicyGateMiddleware(
            policy_engine=None,
            evaluation_mode="enforce",
        )
        ctx = _make_ctx()
        expected = ToolCallResult(
            tool_name="read_file",
            output="ok",
        )
        call = AsyncMock(return_value=expected)

        result = await mw.wrap_tool_call(ctx, call)
        assert result == expected
        call.assert_awaited_once_with(ctx)
