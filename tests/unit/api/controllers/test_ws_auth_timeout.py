"""Tests for the ``ws_auth_timeout_seconds`` kill-switch wiring.

The WebSocket first-message auth handler reads the timeout from
``app_state.ws_auth_timeout_seconds``, which is baked in at startup
by ``_apply_bridge_config`` from the ``api.ws_auth_timeout_seconds``
setting.  Flipping the value on ``app_state`` must change the
effective timeout the handler enforces.
"""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from synthorg.api.controllers.ws import _WS_CLOSE_AUTH_FAILED, _read_auth_message


class _NeverResolvingSocket:
    """Minimal ``WebSocket`` stand-in whose ``receive_text`` never returns.

    Enough surface for ``_read_auth_message`` to exercise the timeout
    path: it pulls ``app.state["app_state"]`` for the timeout, awaits
    ``receive_text()``, and on ``TimeoutError`` calls ``close(code, reason)``.
    """

    def __init__(self, *, ws_auth_timeout_seconds: float) -> None:
        self.closed_with: tuple[int, str] | None = None
        # Build a Litestar-shaped ``app.state`` dict accessor: the WS
        # handler reads ``socket.app.state["app_state"]``, so ``state``
        # must be subscriptable.
        state: dict[str, Any] = {
            "app_state": SimpleNamespace(
                ws_auth_timeout_seconds=ws_auth_timeout_seconds,
            ),
        }
        self.app = SimpleNamespace(state=state)

    async def receive_text(self) -> str:
        """Block until cancelled -- exercises the ``asyncio.wait_for`` path."""
        await asyncio.Event().wait()
        return ""  # pragma: no cover -- unreachable

    async def close(self, *, code: int, reason: str) -> None:
        self.closed_with = (code, reason)


@pytest.mark.unit
class TestWsAuthTimeoutKillSwitch:
    """The configured timeout gates first-message auth behavior."""

    async def test_short_timeout_closes_socket_with_4001(self) -> None:
        """A 10ms timeout closes the socket with the auth-timeout code."""
        socket = _NeverResolvingSocket(ws_auth_timeout_seconds=0.01)

        result = await _read_auth_message(socket)  # type: ignore[arg-type]

        assert result is None
        assert socket.closed_with is not None
        code, _reason = socket.closed_with
        assert code == _WS_CLOSE_AUTH_FAILED

    async def test_timeout_read_from_app_state(self) -> None:
        """Handler reads the timeout from ``app_state`` (not a module constant).

        A 100ms timeout must not expire within a ~10ms wait window;
        the ``wait_for`` is therefore driven by ``app_state`` rather
        than any hardcoded value.
        """
        socket = _NeverResolvingSocket(ws_auth_timeout_seconds=100.0)

        # Race the handler against a tight explicit timeout. If the
        # handler honors ``app_state.ws_auth_timeout_seconds=100``,
        # the outer ``wait_for`` fires first.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                _read_auth_message(socket),  # type: ignore[arg-type]
                timeout=0.05,
            )
        # The inner timeout (100s) hasn't fired, so the socket was
        # never closed by the handler itself.
        assert socket.closed_with is None
