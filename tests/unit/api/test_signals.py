"""Unit tests for the POSIX shutdown signal handler."""

import asyncio
import signal
import sys
from unittest.mock import patch

import pytest

from synthorg.api.signals import (
    _make_handler,
    _on_signal,
    install_shutdown_handlers,
)

pytestmark = pytest.mark.unit


class _FakeAppState:
    """Minimal AppState shim for handler tests."""

    def __init__(self) -> None:
        self.shutdown_requested = asyncio.Event()


class TestInstallShutdownHandlers:
    """``install_shutdown_handlers`` idempotency + platform detection."""

    async def test_resets_shutdown_event_on_reinstall(self) -> None:
        """A second install must clear a previously-set shutdown event."""
        app_state = _FakeAppState()
        app_state.shutdown_requested.set()
        assert app_state.shutdown_requested.is_set()
        install_shutdown_handlers(app_state)  # type: ignore[arg-type]
        assert not app_state.shutdown_requested.is_set()

    async def test_idempotent_registration(self) -> None:
        """Calling twice on the same AppState must not raise."""
        app_state = _FakeAppState()
        install_shutdown_handlers(app_state)  # type: ignore[arg-type]
        install_shutdown_handlers(app_state)  # type: ignore[arg-type]

    async def test_skips_on_windows(self) -> None:
        """On Windows we fall back to uvicorn's handler and skip."""
        app_state = _FakeAppState()
        with patch("synthorg.api.signals.sys") as mock_sys:
            mock_sys.platform = "win32"
            install_shutdown_handlers(app_state)  # type: ignore[arg-type]
            # Event is still reset before the platform check.
            assert not app_state.shutdown_requested.is_set()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX-only code path",
    )
    async def test_survives_add_signal_handler_not_implemented(self) -> None:
        """Proactor loops raising NotImplementedError are logged + ignored."""
        app_state = _FakeAppState()
        loop = asyncio.get_running_loop()
        with patch.object(loop, "add_signal_handler", side_effect=NotImplementedError):
            # Must not raise; the skip is logged at DEBUG instead.
            install_shutdown_handlers(app_state)  # type: ignore[arg-type]


class TestOnSignal:
    """Handler behaviour when a signal arrives."""

    def test_sets_shutdown_flag(self) -> None:
        app_state = _FakeAppState()
        assert not app_state.shutdown_requested.is_set()
        _on_signal(signal.SIGTERM, app_state)  # type: ignore[arg-type]
        assert app_state.shutdown_requested.is_set()

    def test_idempotent_set(self) -> None:
        """Double-signal is a no-op for already-set events."""
        app_state = _FakeAppState()
        _on_signal(signal.SIGTERM, app_state)  # type: ignore[arg-type]
        _on_signal(signal.SIGTERM, app_state)  # type: ignore[arg-type]
        assert app_state.shutdown_requested.is_set()


class TestMakeHandler:
    """The closure factory captures sig + state correctly."""

    def test_closure_binds_signal_and_state(self) -> None:
        app_state = _FakeAppState()
        handler = _make_handler(signal.SIGINT, app_state)  # type: ignore[arg-type]
        assert callable(handler)
        handler()
        assert app_state.shutdown_requested.is_set()

    def test_handler_invocation_survives_event_loop_mismatch(self) -> None:
        """Handler must work even when called outside an event loop."""
        app_state = _FakeAppState()
        handler = _make_handler(signal.SIGTERM, app_state)  # type: ignore[arg-type]
        # Calls with no running loop should not explode.
        handler()
        assert app_state.shutdown_requested.is_set()
