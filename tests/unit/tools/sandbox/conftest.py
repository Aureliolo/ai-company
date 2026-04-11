"""Fixtures for sandbox tests."""

from pathlib import Path

import pytest

from synthorg.tools.sandbox.config import SubprocessSandboxConfig
from synthorg.tools.sandbox.subprocess_sandbox import SubprocessSandbox


@pytest.fixture(autouse=True)
def _isolate_sandbox_image_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear SYNTHORG_SANDBOX_IMAGE so host env never leaks into defaults.

    DockerSandboxConfig.image resolves from this env var via a Pydantic
    default_factory, so any CI or developer shell that exports it would
    make the default-value tests non-deterministic without this isolation.
    """
    monkeypatch.delenv("SYNTHORG_SANDBOX_IMAGE", raising=False)


@pytest.fixture
def sandbox_workspace(tmp_path: Path) -> Path:
    """Temporary workspace directory for sandbox tests."""
    return tmp_path


@pytest.fixture
def sandbox_config() -> SubprocessSandboxConfig:
    """Default sandbox configuration."""
    return SubprocessSandboxConfig()


@pytest.fixture
def subprocess_sandbox(
    sandbox_workspace: Path,
    sandbox_config: SubprocessSandboxConfig,
) -> SubprocessSandbox:
    """SubprocessSandbox instance with default config."""
    return SubprocessSandbox(
        config=sandbox_config,
        workspace=sandbox_workspace,
    )
