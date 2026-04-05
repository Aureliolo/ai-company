"""Unit tests for AgentEngine personality-trim WebSocket notifier."""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.agent import AgentIdentity
from synthorg.core.task import Task
from synthorg.engine.agent_engine import AgentEngine

from .conftest import make_completion_response as _make_completion_response

if TYPE_CHECKING:
    from .conftest import MockCompletionProvider


def _make_resolver(
    *,
    trimming_enabled: bool = True,
    max_tokens_override: int = 10,
    notify_enabled: bool = True,
) -> MagicMock:
    """Build a ConfigResolver mock that returns the given ENGINE settings."""
    resolver = MagicMock()

    async def get_bool(namespace: str, key: str) -> bool:
        if key == "personality_trimming_enabled":
            return trimming_enabled
        if key == "personality_trimming_notify":
            return notify_enabled
        msg = f"unexpected get_bool({namespace}, {key})"
        raise AssertionError(msg)

    async def get_int(namespace: str, key: str) -> int:
        if key == "personality_max_tokens_override":
            return max_tokens_override
        msg = f"unexpected get_int({namespace}, {key})"
        raise AssertionError(msg)

    resolver.get_bool = AsyncMock(side_effect=get_bool)
    resolver.get_int = AsyncMock(side_effect=get_int)
    return resolver


@pytest.mark.unit
class TestPersonalityTrimNotifier:
    """Tests for the personality_trim_notifier callback in AgentEngine.run()."""

    async def test_notifier_fires_when_trimming_and_setting_enabled(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Notifier is awaited with the trim payload when trimming fires."""
        notifier = AsyncMock()
        resolver = _make_resolver(
            trimming_enabled=True,
            max_tokens_override=10,
            notify_enabled=True,
        )
        provider = mock_provider_factory([_make_completion_response()])
        engine = AgentEngine(
            provider=provider,
            config_resolver=resolver,
            personality_trim_notifier=notifier,
        )

        await engine.run(
            identity=sample_agent_with_personality,
            task=sample_task_with_criteria,
        )

        assert notifier.await_count == 1
        assert notifier.await_args is not None
        payload = notifier.await_args.args[0]
        assert set(payload.keys()) == {
            "agent_id",
            "agent_name",
            "task_id",
            "before_tokens",
            "after_tokens",
            "max_tokens",
            "trim_tier",
            "budget_met",
        }
        assert payload["agent_name"] == sample_agent_with_personality.name
        assert payload["max_tokens"] == 10
        assert isinstance(payload["before_tokens"], int)
        assert isinstance(payload["after_tokens"], int)

    async def test_notifier_suppressed_when_notify_setting_disabled(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """When personality_trimming_notify=False, the callback is not invoked."""
        notifier = AsyncMock()
        resolver = _make_resolver(
            trimming_enabled=True,
            max_tokens_override=10,
            notify_enabled=False,
        )
        provider = mock_provider_factory([_make_completion_response()])
        engine = AgentEngine(
            provider=provider,
            config_resolver=resolver,
            personality_trim_notifier=notifier,
        )

        await engine.run(
            identity=sample_agent_with_personality,
            task=sample_task_with_criteria,
        )

        notifier.assert_not_awaited()

    async def test_notifier_not_called_when_no_trimming_happens(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """No trim info => notifier is never called even when setting is true."""
        notifier = AsyncMock()
        # override=0 => profile default (500 for large tier), normal personality
        # does not trigger trimming.
        resolver = _make_resolver(
            trimming_enabled=True,
            max_tokens_override=0,
            notify_enabled=True,
        )
        provider = mock_provider_factory([_make_completion_response()])
        engine = AgentEngine(
            provider=provider,
            config_resolver=resolver,
            personality_trim_notifier=notifier,
        )

        await engine.run(
            identity=sample_agent_with_personality,
            task=sample_task_with_criteria,
        )

        notifier.assert_not_awaited()

    async def test_notifier_failure_is_swallowed(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """Exceptions raised inside the notifier never break task execution."""
        notifier = AsyncMock(side_effect=RuntimeError("pub broken"))
        resolver = _make_resolver(
            trimming_enabled=True,
            max_tokens_override=10,
            notify_enabled=True,
        )
        provider = mock_provider_factory([_make_completion_response()])
        engine = AgentEngine(
            provider=provider,
            config_resolver=resolver,
            personality_trim_notifier=notifier,
        )

        # Should complete without raising even though notifier blows up.
        result = await engine.run(
            identity=sample_agent_with_personality,
            task=sample_task_with_criteria,
        )

        assert notifier.await_count == 1
        assert result.is_success is True

    async def test_no_notifier_wired_is_noop(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """When no notifier callback is provided, trimming still proceeds normally."""
        resolver = _make_resolver(
            trimming_enabled=True,
            max_tokens_override=10,
            notify_enabled=True,
        )
        provider = mock_provider_factory([_make_completion_response()])
        engine = AgentEngine(
            provider=provider,
            config_resolver=resolver,
            # personality_trim_notifier intentionally omitted
        )

        result = await engine.run(
            identity=sample_agent_with_personality,
            task=sample_task_with_criteria,
        )

        assert result.is_success is True

    async def test_notifier_fires_without_config_resolver(
        self,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """When config_resolver is None, the notify setting defaults to enabled.

        Covers the ``self._config_resolver is None`` branch in
        ``_maybe_notify_personality_trim`` -- without a resolver the default
        behavior is to fire the notifier (opt-out only via explicit setting).
        """
        notifier = AsyncMock()
        provider = mock_provider_factory([_make_completion_response()])
        engine = AgentEngine(
            provider=provider,
            personality_trim_notifier=notifier,
            # config_resolver intentionally omitted
        )

        payload: dict[str, object] = {
            "agent_id": "agent-1",
            "agent_name": "Test Agent",
            "task_id": "task-1",
            "before_tokens": 600,
            "after_tokens": 200,
            "max_tokens": 300,
            "trim_tier": 2,
            "budget_met": True,
        }
        await engine._maybe_notify_personality_trim(payload)

        assert notifier.await_count == 1
        assert notifier.await_args is not None
        assert notifier.await_args.args[0] == payload

    async def test_cancelled_error_propagates(
        self,
        mock_provider_factory: type[MockCompletionProvider],
    ) -> None:
        """asyncio.CancelledError raised inside the notifier must propagate.

        BaseException subclasses (CancelledError, MemoryError, RecursionError)
        must never be swallowed by the best-effort try/except, so that task
        cancellation propagates correctly through the engine.
        """
        notifier = AsyncMock(side_effect=asyncio.CancelledError())
        provider = mock_provider_factory([_make_completion_response()])
        engine = AgentEngine(
            provider=provider,
            personality_trim_notifier=notifier,
        )

        payload: dict[str, object] = {
            "agent_id": "agent-1",
            "agent_name": "Test Agent",
            "task_id": "task-1",
            "before_tokens": 600,
            "after_tokens": 200,
            "max_tokens": 300,
            "trim_tier": 2,
            "budget_met": True,
        }

        with pytest.raises(asyncio.CancelledError):
            await engine._maybe_notify_personality_trim(payload)
