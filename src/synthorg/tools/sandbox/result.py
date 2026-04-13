"""Sandbox execution result model."""

from collections.abc import Mapping  # noqa: TC003 -- needed at runtime for Pydantic
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field


class SandboxResult(BaseModel):
    """Immutable result of a sandboxed command execution.

    Attributes:
        stdout: Captured standard output.
        stderr: Captured standard error.
        returncode: Process exit code.
        timed_out: Whether the process was killed due to timeout.
        success: Computed -- ``True`` when returncode is 0 and not timed out.
        container_id: Docker container ID (Docker backend only).
        sidecar_id: Sidecar container ID (Docker backend only).
        sidecar_logs: Parsed JSON log entries from the sidecar container.
        agent_id: Agent that triggered this execution.
        execution_time_ms: Wall-clock execution time in milliseconds.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False

    # Docker-specific fields (optional, backward compat with SubprocessSandbox)
    container_id: str | None = None
    sidecar_id: str | None = None
    sidecar_logs: tuple[Mapping[str, Any], ...] = ()
    agent_id: str | None = None
    execution_time_ms: int | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        """Whether the execution succeeded."""
        return self.returncode == 0 and not self.timed_out
