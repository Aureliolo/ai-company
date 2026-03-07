"""Sandbox backend protocol definition."""

from pathlib import Path  # noqa: TC003 — used at runtime in Protocol
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ai_company.tools.sandbox.result import SandboxResult


@runtime_checkable
class SandboxBackend(Protocol):
    """Protocol for pluggable sandbox backends.

    Implementations execute commands in an isolated environment with
    environment filtering, workspace enforcement, and timeout support.
    Subprocess is the M3 backend; Docker/K8s are future work.
    """

    async def execute(
        self,
        *,
        command: str,
        args: tuple[str, ...],
        cwd: Path | None = None,
        env_overrides: Mapping[str, str] | None = None,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> SandboxResult:
        """Execute a command in the sandbox.

        Args:
            command: Executable name or path.
            args: Command arguments.
            cwd: Working directory (defaults to sandbox workspace root).
            env_overrides: Extra env vars applied on top of filtered env.
            timeout: Seconds before the process is killed. Falls back
                to the backend's default timeout if ``None``.

        Returns:
            A ``SandboxResult`` with captured output and exit status.
        """
        ...

    async def cleanup(self) -> None:
        """Release any resources held by the backend."""
        ...

    async def health_check(self) -> bool:
        """Return ``True`` if the backend is operational."""
        ...

    def get_backend_type(self) -> str:
        """Return a short identifier for this backend type."""
        ...
