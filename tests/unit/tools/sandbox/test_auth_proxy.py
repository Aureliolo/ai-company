"""Tests for SandboxAuthProxy."""

import pytest

from synthorg.tools.sandbox.auth_proxy import SandboxAuthProxy

pytestmark = pytest.mark.unit


class TestSandboxAuthProxy:
    """Tests for SandboxAuthProxy lifecycle."""

    def test_initial_state(self) -> None:
        proxy = SandboxAuthProxy()
        assert proxy.port == 0
        assert proxy.url == ""

    async def test_start_not_implemented(self) -> None:
        proxy = SandboxAuthProxy()
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            await proxy.start()

    async def test_stop_is_safe_when_not_started(self) -> None:
        proxy = SandboxAuthProxy()
        await proxy.stop()
        assert proxy.port == 0
        assert proxy.url == ""
