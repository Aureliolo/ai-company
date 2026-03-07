"""Subprocess-based sandbox backend.

Executes commands via ``asyncio.create_subprocess_exec`` with
environment filtering, workspace boundary enforcement, timeout
management, and PATH restriction.
"""

import asyncio
import contextlib
import fnmatch
import os
from pathlib import Path
from typing import TYPE_CHECKING

from ai_company.observability import get_logger
from ai_company.observability.events.sandbox import (
    SANDBOX_CLEANUP,
    SANDBOX_ENV_FILTERED,
    SANDBOX_EXECUTE_FAILED,
    SANDBOX_EXECUTE_START,
    SANDBOX_EXECUTE_SUCCESS,
    SANDBOX_EXECUTE_TIMEOUT,
    SANDBOX_HEALTH_CHECK,
    SANDBOX_SPAWN_FAILED,
    SANDBOX_WORKSPACE_VIOLATION,
)
from ai_company.tools.sandbox.config import SubprocessSandboxConfig
from ai_company.tools.sandbox.errors import (
    SandboxError,
    SandboxStartError,
)
from ai_company.tools.sandbox.result import SandboxResult

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = get_logger(__name__)

_PATH_SEP = ";" if os.name == "nt" else ":"

_DEFAULT_CONFIG = SubprocessSandboxConfig()


class SubprocessSandbox:
    """Subprocess sandbox backend.

    Runs commands in child processes with filtered environment variables,
    workspace boundary checks, and configurable timeouts.

    Attributes:
        config: Sandbox configuration.
        workspace: Absolute path to the workspace root directory.
    """

    def __init__(
        self,
        *,
        config: SubprocessSandboxConfig | None = None,
        workspace: Path,
    ) -> None:
        """Initialize the subprocess sandbox.

        Args:
            config: Sandbox configuration (defaults to standard config).
            workspace: Absolute path to the workspace root. Must exist.

        Raises:
            ValueError: If *workspace* is not absolute or does not exist.
        """
        if not workspace.is_absolute():
            msg = f"workspace must be an absolute path, got: {workspace}"
            raise ValueError(msg)
        resolved = workspace.resolve()
        if not resolved.is_dir():
            msg = f"workspace directory does not exist: {resolved}"
            raise ValueError(msg)
        self._config = config or _DEFAULT_CONFIG
        self._workspace = resolved

    @property
    def config(self) -> SubprocessSandboxConfig:
        """Sandbox configuration."""
        return self._config

    @property
    def workspace(self) -> Path:
        """Workspace root directory."""
        return self._workspace

    def _matches_allowlist(self, name: str) -> bool:
        """Check if an env var name matches any entry in the allowlist."""
        for pattern in self._config.env_allowlist:
            if pattern == name:
                return True
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    def _matches_denylist(self, name: str) -> bool:
        """Check if an env var name matches any denylist pattern."""
        upper = name.upper()
        return any(
            fnmatch.fnmatch(upper, pat) for pat in self._config.env_denylist_patterns
        )

    def _filter_path(self, path_value: str) -> str:
        """Filter PATH entries, keeping only safe system directories."""
        safe_prefixes = self._get_safe_path_prefixes()
        entries = path_value.split(_PATH_SEP)
        filtered = [
            e
            for e in entries
            if any(e.lower().startswith(prefix.lower()) for prefix in safe_prefixes)
        ]
        return _PATH_SEP.join(filtered) if filtered else path_value

    @staticmethod
    def _get_safe_path_prefixes() -> tuple[str, ...]:
        """Return safe PATH prefixes for the current platform."""
        if os.name == "nt":
            system_root = os.environ.get("SYSTEMROOT", r"C:\WINDOWS")
            return (
                system_root,
                str(Path(system_root) / "system32"),
                r"C:\Program Files\Git",
                r"C:\Program Files (x86)\Git",
            )
        return ("/usr/bin", "/usr/local/bin", "/bin", "/usr/sbin", "/sbin")

    def _build_filtered_env(
        self,
        env_overrides: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Build a filtered environment for the subprocess.

        Starts with an empty dict, copies allowed vars from the current
        process environment, strips denylist matches, optionally filters
        PATH, then applies overrides.

        Args:
            env_overrides: Extra vars applied on top (always win).

        Returns:
            The filtered environment mapping.
        """
        env: dict[str, str] = {}
        filtered_count = 0

        for name, value in os.environ.items():
            if self._matches_allowlist(name) and not self._matches_denylist(
                name,
            ):
                env[name] = value
            else:
                filtered_count += 1

        if self._config.restricted_path and "PATH" in env:
            env["PATH"] = self._filter_path(env["PATH"])

        if env_overrides:
            env.update(env_overrides)

        logger.debug(
            SANDBOX_ENV_FILTERED,
            filtered_count=filtered_count,
            kept_count=len(env),
        )
        return env

    def _validate_cwd(self, cwd: Path) -> None:
        """Validate that *cwd* is within the workspace boundary.

        Args:
            cwd: Working directory to validate.

        Raises:
            SandboxError: If *cwd* is outside the workspace and
                ``workspace_only`` is enabled.
        """
        if not self._config.workspace_only:
            return
        try:
            cwd.resolve().relative_to(self._workspace)
        except ValueError:
            logger.warning(
                SANDBOX_WORKSPACE_VIOLATION,
                cwd=str(cwd),
                workspace=str(self._workspace),
            )
            msg = f"Working directory '{cwd}' is outside workspace '{self._workspace}'"
            raise SandboxError(msg) from None

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
            cwd: Working directory (defaults to workspace root).
            env_overrides: Extra env vars applied on top of filtered env.
            timeout: Seconds before the process is killed.

        Returns:
            A ``SandboxResult`` with captured output and exit status.

        Raises:
            SandboxStartError: If the subprocess could not be started.
            SandboxError: If cwd is outside the workspace boundary.
        """
        work_dir = cwd or self._workspace
        self._validate_cwd(work_dir)

        effective_timeout = timeout or self._config.timeout_seconds
        env = self._build_filtered_env(env_overrides)

        logger.debug(
            SANDBOX_EXECUTE_START,
            command=command,
            args=args,
            cwd=str(work_dir),
            timeout=effective_timeout,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                command,
                *args,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except OSError as exc:
            logger.warning(
                SANDBOX_SPAWN_FAILED,
                command=command,
                error=str(exc),
                exc_info=True,
            )
            msg = f"Failed to start '{command}': {exc}"
            raise SandboxStartError(
                msg,
                context={"command": command},
            ) from exc

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=effective_timeout,
            )
        except TimeoutError:
            proc.kill()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(proc.communicate(), timeout=5.0)
            logger.warning(
                SANDBOX_EXECUTE_TIMEOUT,
                command=command,
                args=args,
                timeout=effective_timeout,
            )
            return SandboxResult(
                stdout="",
                stderr=f"Process timed out after {effective_timeout}s",
                returncode=-1,
                timed_out=True,
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        returncode = proc.returncode or 0

        if returncode != 0:
            logger.warning(
                SANDBOX_EXECUTE_FAILED,
                command=command,
                args=args,
                returncode=returncode,
                stderr=stderr,
            )
        else:
            logger.debug(
                SANDBOX_EXECUTE_SUCCESS,
                command=command,
                args=args,
            )

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )

    async def cleanup(self) -> None:
        """No-op — subprocesses are ephemeral."""
        logger.debug(SANDBOX_CLEANUP, backend="subprocess")

    async def health_check(self) -> bool:
        """Return ``True`` if the workspace directory exists."""
        healthy = self._workspace.is_dir()
        logger.debug(
            SANDBOX_HEALTH_CHECK,
            backend="subprocess",
            healthy=healthy,
            workspace=str(self._workspace),
        )
        return healthy

    def get_backend_type(self) -> str:
        """Return ``'subprocess'``."""
        return "subprocess"
