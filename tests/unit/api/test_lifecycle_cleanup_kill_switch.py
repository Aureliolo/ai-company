"""Tests for the ``lifecycle_cleanup_enabled`` live kill-switch.

When operators flip ``api.lifecycle_cleanup_enabled=false`` the WS
ticket / session / lockout cleanup loop must short-circuit every
tick without tearing down the task.  When ``True`` the loop must
call all three cleanup paths on every tick.
"""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.api import lifecycle_helpers


def _build_app_state(*, enabled: bool) -> SimpleNamespace:
    """Build a minimal ``AppState`` stand-in with counting stub stores."""
    ticket_store = SimpleNamespace(
        cleanup_expired=MagicMock(return_value=None),
    )
    session_store = SimpleNamespace(
        cleanup_expired=AsyncMock(return_value=None),
    )
    lockout_store = SimpleNamespace(
        cleanup_expired=AsyncMock(return_value=None),
    )
    config_resolver = SimpleNamespace(
        get_bool=AsyncMock(return_value=enabled),
        get_float=AsyncMock(return_value=0.001),
    )
    return SimpleNamespace(
        ticket_store=ticket_store,
        session_store=session_store,
        lockout_store=lockout_store,
        config_resolver=config_resolver,
        has_config_resolver=True,
        has_session_store=True,
        has_lockout_store=True,
    )


async def _run_loop_ticks(app_state: Any, ticks: int) -> None:
    """Drive the cleanup loop for *ticks* iterations, then cancel.

    Uses ``_resolve_ticket_cleanup_interval`` via the stubbed
    resolver (returning 1ms) so the loop advances predictably without
    any wall-clock assumptions.  Cancellation is the loop's terminal
    state; the test observes side-effects on the stub stores.
    """
    task = asyncio.create_task(lifecycle_helpers._ticket_cleanup_loop(app_state))
    # Yield control long enough for the stubbed ``asyncio.sleep(0.001)``
    # to advance through *ticks* iterations.
    for _ in range(ticks):
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.unit
class TestLifecycleCleanupKillSwitch:
    """Flipping the setting gates all three cleanup paths together."""

    async def test_enabled_calls_all_cleanup_paths(self) -> None:
        """When ``enabled=True`` every tick runs all three cleanups."""
        app_state = _build_app_state(enabled=True)

        await _run_loop_ticks(app_state, ticks=2)

        assert app_state.ticket_store.cleanup_expired.call_count >= 1
        assert app_state.session_store.cleanup_expired.await_count >= 1
        assert app_state.lockout_store.cleanup_expired.await_count >= 1

    async def test_disabled_short_circuits_every_tick(self) -> None:
        """When ``enabled=False`` no cleanup path runs, but the loop stays alive."""
        app_state = _build_app_state(enabled=False)

        await _run_loop_ticks(app_state, ticks=3)

        # The kill-switch must gate all three cleanup sites together.
        assert app_state.ticket_store.cleanup_expired.call_count == 0
        assert app_state.session_store.cleanup_expired.await_count == 0
        assert app_state.lockout_store.cleanup_expired.await_count == 0
        # But the resolver must have been consulted at least once per
        # tick -- proves the loop is running and the gate is live,
        # not frozen.
        assert app_state.config_resolver.get_bool.await_count >= 1


@pytest.mark.unit
class TestResolveLifecycleCleanupEnabled:
    """Fail-safe fallback policy for the resolver call itself."""

    async def test_no_resolver_returns_true(self) -> None:
        """Missing resolver keeps cleanup running (fail-safe)."""
        app_state = SimpleNamespace(has_config_resolver=False)

        assert (
            await lifecycle_helpers._resolve_lifecycle_cleanup_enabled(
                app_state,  # type: ignore[arg-type]
            )
            is True
        )

    async def test_resolver_exception_returns_true(self) -> None:
        """Resolver raising ``Exception`` keeps cleanup running (fail-safe)."""
        config_resolver = SimpleNamespace(
            get_bool=AsyncMock(side_effect=RuntimeError("settings backend down")),
        )
        app_state = SimpleNamespace(
            has_config_resolver=True,
            config_resolver=config_resolver,
        )

        assert (
            await lifecycle_helpers._resolve_lifecycle_cleanup_enabled(
                app_state,  # type: ignore[arg-type]
            )
            is True
        )


@pytest.mark.unit
class TestRunCleanupTickExceptionIsolation:
    """Each per-store cleanup failure is isolated from the others."""

    async def test_ticket_cleanup_failure_does_not_block_session_or_lockout(
        self,
    ) -> None:
        """``ticket_store.cleanup_expired`` raising still runs session + lockout."""
        ticket_store = SimpleNamespace(
            cleanup_expired=MagicMock(side_effect=RuntimeError("ticket exploded")),
        )
        session_store = SimpleNamespace(cleanup_expired=AsyncMock(return_value=None))
        lockout_store = SimpleNamespace(cleanup_expired=AsyncMock(return_value=None))
        app_state = SimpleNamespace(
            ticket_store=ticket_store,
            session_store=session_store,
            lockout_store=lockout_store,
            has_session_store=True,
            has_lockout_store=True,
        )

        await lifecycle_helpers._run_cleanup_tick(app_state)  # type: ignore[arg-type]

        # Ticket raised -- but session and lockout still ran to completion.
        ticket_store.cleanup_expired.assert_called_once()
        session_store.cleanup_expired.assert_awaited_once()
        lockout_store.cleanup_expired.assert_awaited_once()

    async def test_session_cleanup_failure_does_not_block_lockout(self) -> None:
        """``session_store.cleanup_expired`` raising still runs lockout cleanup."""
        ticket_store = SimpleNamespace(cleanup_expired=MagicMock(return_value=None))
        session_store = SimpleNamespace(
            cleanup_expired=AsyncMock(side_effect=RuntimeError("sessions gone")),
        )
        lockout_store = SimpleNamespace(cleanup_expired=AsyncMock(return_value=None))
        app_state = SimpleNamespace(
            ticket_store=ticket_store,
            session_store=session_store,
            lockout_store=lockout_store,
            has_session_store=True,
            has_lockout_store=True,
        )

        await lifecycle_helpers._run_cleanup_tick(app_state)  # type: ignore[arg-type]

        ticket_store.cleanup_expired.assert_called_once()
        session_store.cleanup_expired.assert_awaited_once()
        lockout_store.cleanup_expired.assert_awaited_once()

    async def test_memory_error_propagates_from_cleanup_tick(self) -> None:
        """``MemoryError`` escapes the cleanup tick -- OOM must not be swallowed."""
        ticket_store = SimpleNamespace(
            cleanup_expired=MagicMock(side_effect=MemoryError),
        )
        app_state = SimpleNamespace(
            ticket_store=ticket_store,
            has_session_store=False,
            has_lockout_store=False,
        )

        with pytest.raises(MemoryError):
            await lifecycle_helpers._run_cleanup_tick(app_state)  # type: ignore[arg-type]
