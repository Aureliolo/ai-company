"""Docker-based sandbox backend.

Executes commands inside ephemeral Docker containers with workspace
mount, resource limits, network isolation, and timeout management.
Uses ``aiodocker`` for asynchronous Docker daemon communication.
"""

import asyncio
import platform
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final

import aiodocker

from ai_company.core.types import NotBlankStr
from ai_company.observability import get_logger
from ai_company.observability.events.docker import (
    DOCKER_CLEANUP,
    DOCKER_CONTAINER_CREATED,
    DOCKER_CONTAINER_REMOVED,
    DOCKER_CONTAINER_STOPPED,
    DOCKER_DAEMON_UNAVAILABLE,
    DOCKER_EXECUTE_FAILED,
    DOCKER_EXECUTE_START,
    DOCKER_EXECUTE_SUCCESS,
    DOCKER_EXECUTE_TIMEOUT,
    DOCKER_HEALTH_CHECK,
)
from ai_company.tools.sandbox.docker_config import DockerSandboxConfig
from ai_company.tools.sandbox.errors import SandboxError, SandboxStartError
from ai_company.tools.sandbox.result import SandboxResult

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = get_logger(__name__)

_DEFAULT_CONFIG = DockerSandboxConfig()
_NANO_CPUS_MULTIPLIER: Final[int] = 1_000_000_000
_CONTAINER_WORKSPACE: Final[str] = "/workspace"
_STOP_TIMEOUT_SECONDS: Final[int] = 5
_DRIVE_SEPARATOR_PARTS: Final[int] = 2


def _to_posix_bind_path(path: Path) -> str:
    r"""Convert a host path to POSIX format for Docker bind mounts.

    On Windows, converts ``C:\Users\foo`` to ``/c/Users/foo``
    for Docker Desktop compatibility.

    Args:
        path: Host filesystem path to convert.

    Returns:
        POSIX-formatted path string suitable for Docker bind mounts.
    """
    if platform.system() == "Windows":
        posix = PurePosixPath(path.as_posix())
        parts = str(posix).split(":", 1)
        if len(parts) == _DRIVE_SEPARATOR_PARTS:
            drive = parts[0].lstrip("/").lower()
            rest = parts[1]
            return f"/{drive}{rest}"
    return str(path)


class DockerSandbox:
    """Docker sandbox backend.

    Runs commands in ephemeral Docker containers with workspace mounts,
    resource limits (memory, CPU), network isolation, and timeout
    management.

    Attributes:
        config: Docker sandbox configuration.
        workspace: Absolute path to the workspace root directory.
    """

    def __init__(
        self,
        *,
        config: DockerSandboxConfig | None = None,
        workspace: Path,
    ) -> None:
        """Initialize the Docker sandbox.

        Args:
            config: Docker sandbox configuration (defaults to standard).
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
        self._docker: aiodocker.Docker | None = None
        self._tracked_containers: list[str] = []

    @property
    def config(self) -> DockerSandboxConfig:
        """Docker sandbox configuration."""
        return self._config

    @property
    def workspace(self) -> Path:
        """Workspace root directory."""
        return self._workspace

    async def _ensure_docker(self) -> aiodocker.Docker:
        """Lazily connect to the Docker daemon.

        Returns:
            An ``aiodocker.Docker`` client instance.

        Raises:
            SandboxStartError: If the Docker daemon is unavailable.
        """
        if self._docker is not None:
            return self._docker
        try:
            client = aiodocker.Docker()
            await client.version()
        except Exception as exc:
            logger.exception(
                DOCKER_DAEMON_UNAVAILABLE,
                error=str(exc),
            )
            msg = f"Docker daemon unavailable: {exc}"
            raise SandboxStartError(msg) from exc
        else:
            self._docker = client
            return client

    def _validate_cwd(self, cwd: Path) -> None:
        """Validate that *cwd* is within the workspace boundary.

        Args:
            cwd: Working directory to validate.

        Raises:
            SandboxError: If *cwd* is outside the workspace.
        """
        try:
            cwd.resolve().relative_to(self._workspace)
        except ValueError as exc:
            msg = f"Working directory '{cwd}' is outside workspace '{self._workspace}'"
            raise SandboxError(msg) from exc

    def _resolve_cwd_in_container(self, cwd: Path | None) -> str:
        """Map a host cwd to a container-internal path.

        Args:
            cwd: Host working directory, or ``None`` for workspace root.

        Returns:
            POSIX path inside the container.
        """
        if cwd is None:
            return _CONTAINER_WORKSPACE
        rel = cwd.resolve().relative_to(self._workspace)
        return str(PurePosixPath(_CONTAINER_WORKSPACE) / rel)

    def _build_container_config(
        self,
        *,
        command: str,
        args: tuple[str, ...],
        container_cwd: str,
        env_overrides: Mapping[str, str] | None,
        auto_remove: bool,
    ) -> dict[str, Any]:
        """Build the Docker container creation config.

        Args:
            command: Executable name or path.
            args: Command arguments.
            container_cwd: Working directory inside the container.
            env_overrides: Environment variables for the container.
            auto_remove: Whether Docker should auto-remove the container.

        Returns:
            A dict suitable for ``aiodocker`` container creation.
        """
        bind_path = _to_posix_bind_path(self._workspace)
        mount_mode = self._config.mount_mode
        bind_str = f"{bind_path}:{_CONTAINER_WORKSPACE}:{mount_mode}"

        env_list = [f"{k}={v}" for k, v in (env_overrides or {}).items()]

        memory_bytes = self._parse_memory_limit(
            self._config.memory_limit,
        )
        nano_cpus = int(self._config.cpu_limit * _NANO_CPUS_MULTIPLIER)

        host_config: dict[str, Any] = {
            "Binds": [bind_str],
            "Memory": memory_bytes,
            "NanoCpus": nano_cpus,
            "NetworkMode": self._config.network,
            "AutoRemove": auto_remove,
        }
        if self._config.runtime is not None:
            host_config["Runtime"] = self._config.runtime

        return {
            "Image": self._config.image,
            "Cmd": [command, *args],
            "WorkingDir": container_cwd,
            "Env": env_list,
            "HostConfig": host_config,
            "AttachStdout": True,
            "AttachStderr": True,
        }

    @staticmethod
    def _parse_memory_limit(limit: str) -> int:
        """Parse a Docker memory limit string to bytes.

        Supports suffixes ``k``, ``m``, ``g`` (case-insensitive).

        Args:
            limit: Memory limit string (e.g. ``"512m"``).

        Returns:
            Memory limit in bytes.

        Raises:
            ValueError: If the format is invalid.
        """
        limit_lower = limit.strip().lower()
        multipliers = {"k": 1024, "m": 1024**2, "g": 1024**3}
        if limit_lower[-1] in multipliers:
            return int(limit_lower[:-1]) * multipliers[limit_lower[-1]]
        return int(limit_lower)

    async def execute(
        self,
        *,
        command: str,
        args: tuple[str, ...],
        cwd: Path | None = None,
        env_overrides: Mapping[str, str] | None = None,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> SandboxResult:
        """Execute a command inside a Docker container.

        Args:
            command: Executable name or path.
            args: Command arguments.
            cwd: Working directory (defaults to workspace root).
            env_overrides: Extra env vars (only these — no host leakage).
            timeout: Seconds before the container is killed.

        Returns:
            A ``SandboxResult`` with captured output and exit status.

        Raises:
            SandboxStartError: If the Docker daemon or image is unavailable.
            SandboxError: If cwd is outside the workspace boundary.
        """
        work_dir = cwd if cwd is not None else self._workspace
        self._validate_cwd(work_dir)

        effective_timeout = (
            timeout if timeout is not None else self._config.timeout_seconds
        )
        container_cwd = self._resolve_cwd_in_container(cwd)

        logger.debug(
            DOCKER_EXECUTE_START,
            command=command,
            args=args,
            cwd=container_cwd,
            timeout=effective_timeout,
            image=self._config.image,
        )

        docker = await self._ensure_docker()
        return await self._run_container(
            docker=docker,
            command=command,
            args=args,
            container_cwd=container_cwd,
            env_overrides=env_overrides,
            timeout=effective_timeout,
        )

    async def _run_container(  # noqa: PLR0913
        self,
        *,
        docker: aiodocker.Docker,
        command: str,
        args: tuple[str, ...],
        container_cwd: str,
        env_overrides: Mapping[str, str] | None,
        timeout: float,  # noqa: ASYNC109
    ) -> SandboxResult:
        """Create, start, and wait for a container.

        Args:
            docker: Docker client.
            command: Executable name or path.
            args: Command arguments.
            container_cwd: Container working directory.
            env_overrides: Environment variables.
            timeout: Timeout in seconds.

        Returns:
            A ``SandboxResult`` with captured output and exit status.
        """
        # Disable auto_remove when we might need to stop on timeout
        config = self._build_container_config(
            command=command,
            args=args,
            container_cwd=container_cwd,
            env_overrides=env_overrides,
            auto_remove=False,
        )

        try:
            container = await docker.containers.create(
                config,
            )
        except Exception as exc:
            msg = f"Failed to create container: {exc}"
            logger.exception(
                DOCKER_EXECUTE_FAILED,
                command=command,
                error=msg,
            )
            raise SandboxStartError(msg) from exc

        container_id = container.id
        self._tracked_containers = [
            *self._tracked_containers,
            container_id,
        ]
        logger.debug(
            DOCKER_CONTAINER_CREATED,
            container_id=container_id[:12],
            image=self._config.image,
        )

        try:
            return await self._start_and_wait(
                docker=docker,
                container_id=container_id,
                command=command,
                args=args,
                timeout=timeout,
            )
        finally:
            await self._remove_container(docker, container_id)

    async def _start_and_wait(
        self,
        *,
        docker: aiodocker.Docker,
        container_id: str,
        command: str,
        args: tuple[str, ...],
        timeout: float,  # noqa: ASYNC109
    ) -> SandboxResult:
        """Start a container and wait for completion or timeout.

        Args:
            docker: Docker client.
            container_id: Container ID.
            command: Command (for logging).
            args: Args (for logging).
            timeout: Timeout in seconds.

        Returns:
            A ``SandboxResult``.
        """
        container_obj = docker.containers.container(container_id)
        await container_obj.start()

        timed_out = False
        try:
            response = await asyncio.wait_for(
                container_obj.wait(),
                timeout=timeout,
            )
            returncode = response.get("StatusCode", -1)
        except TimeoutError:
            timed_out = True
            logger.warning(
                DOCKER_EXECUTE_TIMEOUT,
                container_id=container_id[:12],
                command=command,
                args=args,
                timeout=timeout,
            )
            await self._stop_container(docker, container_id)
            returncode = -1

        stdout, stderr = await self._collect_logs(container_obj)

        if timed_out:
            return SandboxResult(
                stdout=stdout,
                stderr=stderr or f"Container timed out after {timeout}s",
                returncode=returncode,
                timed_out=True,
            )

        if returncode != 0:
            logger.warning(
                DOCKER_EXECUTE_FAILED,
                command=command,
                args=args,
                returncode=returncode,
                stderr=stderr,
            )
        else:
            logger.debug(
                DOCKER_EXECUTE_SUCCESS,
                command=command,
                args=args,
                container_id=container_id[:12],
            )

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )

    @staticmethod
    async def _collect_logs(
        container_obj: aiodocker.containers.DockerContainer,
    ) -> tuple[str, str]:
        """Collect stdout and stderr logs from a container.

        Args:
            container_obj: Docker container object.

        Returns:
            Tuple of (stdout, stderr) as strings.
        """
        stdout_logs = await container_obj.log(
            stdout=True,
            stderr=False,
        )
        stderr_logs = await container_obj.log(
            stdout=False,
            stderr=True,
        )
        stdout = "".join(stdout_logs).strip()
        stderr = "".join(stderr_logs).strip()
        return stdout, stderr

    @staticmethod
    async def _stop_container(
        docker: aiodocker.Docker,
        container_id: str,
    ) -> None:
        """Stop a running container.

        Args:
            docker: Docker client.
            container_id: Container ID to stop.
        """
        try:
            container_obj = docker.containers.container(container_id)
            await container_obj.stop(
                t=_STOP_TIMEOUT_SECONDS,
            )
            logger.debug(
                DOCKER_CONTAINER_STOPPED,
                container_id=container_id[:12],
            )
        except Exception as exc:
            logger.warning(
                DOCKER_CONTAINER_STOPPED,
                container_id=container_id[:12],
                error=str(exc),
            )

    @staticmethod
    async def _remove_container(
        docker: aiodocker.Docker,
        container_id: str,
    ) -> None:
        """Remove a container, forcing removal if necessary.

        Args:
            docker: Docker client.
            container_id: Container ID to remove.
        """
        try:
            container_obj = docker.containers.container(container_id)
            await container_obj.delete(force=True)
            logger.debug(
                DOCKER_CONTAINER_REMOVED,
                container_id=container_id[:12],
            )
        except Exception as exc:
            logger.warning(
                DOCKER_CONTAINER_REMOVED,
                container_id=container_id[:12],
                error=str(exc),
            )

    async def cleanup(self) -> None:
        """Stop tracked containers and close the Docker session."""
        logger.debug(
            DOCKER_CLEANUP,
            tracked_count=len(self._tracked_containers),
        )
        if self._docker is not None:
            for cid in self._tracked_containers:
                await self._stop_container(self._docker, cid)
            await self._docker.close()
            self._docker = None
        self._tracked_containers = []

    async def health_check(self) -> bool:
        """Return ``True`` if the Docker daemon is reachable.

        Returns:
            ``True`` if healthy, ``False`` otherwise.
        """
        try:
            docker = await self._ensure_docker()
            await docker.version()
        except Exception:
            logger.debug(
                DOCKER_HEALTH_CHECK,
                healthy=False,
            )
            return False
        else:
            logger.debug(
                DOCKER_HEALTH_CHECK,
                healthy=True,
            )
            return True

    def get_backend_type(self) -> NotBlankStr:
        """Return ``'docker'``."""
        return NotBlankStr("docker")
