"""Integration tests for Docker sandbox with real Docker daemon.

These tests require a running Docker daemon and the sandbox image.
They are skipped automatically if Docker is unavailable.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from ai_company.tools.sandbox.docker_config import DockerSandboxConfig
from ai_company.tools.sandbox.docker_sandbox import DockerSandbox

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.timeout(60)]


def _docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    try:
        import aiodocker

        async def _check() -> bool:
            try:
                client = aiodocker.Docker()
                await client.version()
            except Exception:
                return False
            else:
                await client.close()
                return True

        return asyncio.get_event_loop().run_until_complete(_check())
    except Exception:
        return False


skip_no_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker daemon not available",
)


@skip_no_docker
class TestDockerSandboxRealExecution:
    """Real Docker execution tests."""

    async def test_run_python_code(self, tmp_path: Path) -> None:
        """Execute Python code in a real Docker container."""
        config = DockerSandboxConfig(
            image="python:3.14-slim",
            timeout_seconds=30,
        )
        sandbox = DockerSandbox(
            config=config,
            workspace=tmp_path,
        )
        try:
            result = await sandbox.execute(
                command="python3",
                args=("-c", "print('hello from docker')"),
            )
            assert result.success
            assert "hello from docker" in result.stdout
        finally:
            await sandbox.cleanup()

    async def test_run_with_timeout(self, tmp_path: Path) -> None:
        """Timeout kills the container."""
        config = DockerSandboxConfig(
            image="python:3.14-slim",
            timeout_seconds=120,
        )
        sandbox = DockerSandbox(
            config=config,
            workspace=tmp_path,
        )
        try:
            result = await sandbox.execute(
                command="sleep",
                args=("60",),
                timeout=2.0,
            )
            assert result.timed_out
            assert not result.success
        finally:
            await sandbox.cleanup()

    async def test_health_check(self, tmp_path: Path) -> None:
        """Health check returns True with running daemon."""
        sandbox = DockerSandbox(workspace=tmp_path)
        try:
            assert await sandbox.health_check() is True
        finally:
            await sandbox.cleanup()
