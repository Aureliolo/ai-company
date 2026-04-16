"""Docker-based sandbox backend.

Executes commands inside ephemeral Docker containers with workspace
mount, resource limits, network isolation, and timeout management.
Uses ``aiodocker`` for asynchronous Docker daemon communication.
"""

import asyncio
import platform
import secrets
import time
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final

import aiodocker
import aiodocker.containers

from synthorg.core.types import NotBlankStr
from synthorg.observability import get_logger
from synthorg.observability.events.docker import (
    DOCKER_CLEANUP,
    DOCKER_CONTAINER_CREATED,
    DOCKER_CONTAINER_REMOVE_FAILED,
    DOCKER_CONTAINER_REMOVED,
    DOCKER_CONTAINER_STOP_FAILED,
    DOCKER_CONTAINER_STOPPED,
    DOCKER_DAEMON_UNAVAILABLE,
    DOCKER_EXECUTE_FAILED,
    DOCKER_EXECUTE_START,
    DOCKER_EXECUTE_SUCCESS,
    DOCKER_EXECUTE_TIMEOUT,
    DOCKER_HEALTH_CHECK,
)
from synthorg.observability.events.sandbox import (
    SANDBOX_CONTAINER_LOGS_COLLECTED,
    SANDBOX_NETWORK_ENFORCEMENT,
    SANDBOX_RUNTIME_RESOLVER_ATTACHED,
    SANDBOX_SIDECAR_CREATED,
    SANDBOX_SIDECAR_HEALTH_FAILED,
    SANDBOX_SIDECAR_HEALTHY,
    SANDBOX_SIDECAR_REMOVE_FAILED,
    SANDBOX_SIDECAR_REMOVED,
    SANDBOX_SIDECAR_STARTED,
)
from synthorg.tools.sandbox.container_log_shipper import (
    build_correlation_env,
    collect_sidecar_logs,
    ship_container_logs,
)
from synthorg.tools.sandbox.credential_manager import SandboxCredentialManager
from synthorg.tools.sandbox.docker_config import DockerSandboxConfig
from synthorg.tools.sandbox.errors import SandboxError, SandboxStartError
from synthorg.tools.sandbox.result import SandboxResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.observability.config import ContainerLogShippingConfig
    from synthorg.tools.sandbox.runtime_resolver import SandboxRuntimeResolver

_RESERVED_ENV_KEYS: Final[frozenset[str]] = frozenset(
    {
        "SIDECAR_ALLOWED_HOSTS",
        "SIDECAR_DNS_ALLOWED",
        "SIDECAR_LOOPBACK_ALLOWED",
        "SIDECAR_ALLOW_ALL",
        "SIDECAR_ADMIN_TOKEN",
        "SANDBOX_ALLOWED_HOSTS",
        "SANDBOX_DNS_ALLOWED",
        "SANDBOX_LOOPBACK_ALLOWED",
    }
)

_SIDECAR_HEALTH_POLL_INTERVAL: Final[float] = 0.2
_SIDECAR_HEALTH_TIMEOUT: Final[float] = 15.0
_SIDECAR_MEMORY: Final[str] = "64m"
_SIDECAR_CPU: Final[float] = 0.5
_SIDECAR_PIDS: Final[int] = 32

logger = get_logger(__name__)

_DEFAULT_CONFIG = DockerSandboxConfig()
_NANO_CPUS_MULTIPLIER: Final[int] = 1_000_000_000
_CONTAINER_WORKSPACE: Final[str] = "/workspace"
_STOP_TIMEOUT_SECONDS: Final[int] = 5
_DRIVE_SEPARATOR_PARTS: Final[int] = 2
# Cap structured-log stderr captures so a stream of binary output from
# inside a container cannot blow up our logging pipeline.
_MAX_STDERR_LOG_CHARS: Final[int] = 200


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
        log_shipping_config: ContainerLogShippingConfig | None = None,
    ) -> None:
        """Initialize the Docker sandbox.

        Args:
            config: Docker sandbox configuration (defaults to standard).
            workspace: Absolute path to the workspace root. Must exist.
            log_shipping_config: Container log shipping configuration.
                Default-constructed if not provided.

        Raises:
            ValueError: If *workspace* is not absolute or does not exist.
        """
        if not workspace.is_absolute():
            msg = f"workspace must be an absolute path, got: {workspace}"
            logger.warning(DOCKER_EXECUTE_FAILED, error=msg)
            raise ValueError(msg)
        resolved = workspace.resolve()
        if not resolved.is_dir():
            msg = f"workspace directory does not exist: {resolved}"
            logger.warning(DOCKER_EXECUTE_FAILED, error=msg)
            raise ValueError(msg)
        self._config = config or _DEFAULT_CONFIG
        self._workspace = resolved
        self._docker: aiodocker.Docker | None = None
        self._tracked_containers: dict[str, str | None] = {}
        self._lock = asyncio.Lock()
        self._credential_manager = SandboxCredentialManager()
        self._runtime_resolver: SandboxRuntimeResolver | None = None
        if log_shipping_config is None:
            from synthorg.observability.config import (  # noqa: PLC0415
                ContainerLogShippingConfig as _Cfg,
            )

            log_shipping_config = _Cfg()
        self._log_shipping_config = log_shipping_config

    @property
    def config(self) -> DockerSandboxConfig:
        """Docker sandbox configuration."""
        return self._config

    @property
    def workspace(self) -> Path:
        """Workspace root directory."""
        return self._workspace

    def set_runtime_resolver(
        self,
        resolver: SandboxRuntimeResolver,
    ) -> None:
        """Attach a runtime resolver for per-category runtime selection.

        Args:
            resolver: The resolver with probed runtime availability.
        """
        self._runtime_resolver = resolver
        logger.info(
            SANDBOX_RUNTIME_RESOLVER_ATTACHED,
            resolver_type=type(resolver).__name__,
        )

    async def _ensure_docker(self) -> aiodocker.Docker:
        """Lazily connect to the Docker daemon.

        Serialized with ``_lock`` to prevent duplicate client creation
        from concurrent calls.

        Returns:
            An ``aiodocker.Docker`` client instance.

        Raises:
            SandboxStartError: If the Docker daemon is unavailable.
        """
        async with self._lock:
            if self._docker is not None:
                return self._docker
            client = aiodocker.Docker()
            try:
                await client.version()
            except Exception as exc:
                await client.close()
                logger.exception(
                    DOCKER_DAEMON_UNAVAILABLE,
                    error=str(exc),
                )
                msg = f"Docker daemon unavailable: {exc}"
                raise SandboxStartError(msg) from exc
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
            logger.warning(
                DOCKER_EXECUTE_FAILED,
                error=msg,
                cwd=str(cwd),
                workspace=str(self._workspace),
            )
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

    def _build_container_config(  # noqa: PLR0913
        self,
        *,
        command: str,
        args: tuple[str, ...],
        container_cwd: str,
        env_overrides: Mapping[str, str] | None,
        category: str = "",
        network_mode: str | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        """Build the Docker container creation config.

        Args:
            command: Executable name or path.
            args: Command arguments.
            container_cwd: Working directory inside the container.
            env_overrides: Environment variables for the container.
            category: Tool category for runtime resolution.
            network_mode: Override the default network mode. Used to
                set ``container:<sidecar_id>`` when sidecar
            owner_id: Lifecycle owner for container labeling.
                enforcement is active.

        Returns:
            A dict suitable for ``aiodocker`` container creation.
        """
        sanitized = (
            self._credential_manager.sanitize_env(env_overrides)
            if env_overrides
            else None
        )
        env_list = self._validate_env(sanitized)
        correlation_env = build_correlation_env()
        # Merge: correlation IDs override user-supplied duplicates.
        merged: dict[str, str] = {}
        for entry in env_list:
            key, _, value = entry.partition("=")
            merged[key] = value
        for entry in correlation_env:
            key, _, value = entry.partition("=")
            merged[key] = value
        env_list = [f"{k}={v}" for k, v in merged.items()]
        host_config = self._build_host_config(category=category)
        if network_mode is not None:
            host_config["NetworkMode"] = network_mode
        labels: dict[str, str] = {"synthorg.sandbox": "true"}
        if owner_id is not None:
            labels["synthorg.sandbox.owner_id"] = owner_id
        container_config: dict[str, Any] = {
            "Image": self._config.image,
            "Cmd": [command, *args],
            "WorkingDir": container_cwd,
            "Env": env_list,
            "Labels": labels,
            "HostConfig": host_config,
            "AttachStdout": True,
            "AttachStderr": True,
        }
        return container_config

    def _validate_env(
        self,
        env_overrides: Mapping[str, str] | None,
    ) -> list[str]:
        """Validate env_overrides and return the env list."""
        if env_overrides:
            conflicting = sorted(
                set(env_overrides) & _RESERVED_ENV_KEYS,
            )
            if conflicting:
                msg = (
                    "env_overrides cannot set reserved sandbox "
                    f"control variables: {conflicting}"
                )
                logger.warning(
                    DOCKER_EXECUTE_FAILED,
                    error=msg,
                    conflicting_keys=conflicting,
                )
                raise SandboxError(msg)
        return [f"{k}={v}" for k, v in (env_overrides or {}).items()]

    def _build_host_config(
        self,
        *,
        category: str = "",
    ) -> dict[str, Any]:
        """Build the Docker host config dict."""
        bind_path = _to_posix_bind_path(self._workspace)
        mount_mode = self._config.mount_mode
        bind_str = f"{bind_path}:{_CONTAINER_WORKSPACE}:{mount_mode}"
        memory_bytes = self._parse_memory_limit(
            self._config.memory_limit,
        )
        nano_cpus = int(self._config.cpu_limit * _NANO_CPUS_MULTIPLIER)
        host_config: dict[str, Any] = {
            "Binds": [bind_str],
            "Tmpfs": {"/tmp": "size=64m,noexec,nosuid"},  # noqa: S108
            "Memory": memory_bytes,
            "NanoCpus": nano_cpus,
            "NetworkMode": self._config.network,
            "AutoRemove": False,
            "PidsLimit": 64,
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
        }
        runtime = self._resolve_runtime(category)
        if runtime is not None:
            host_config["Runtime"] = runtime
        return host_config

    def _resolve_runtime(self, category: str) -> str | None:
        """Resolve the effective container runtime for a category.

        Delegates to the ``SandboxRuntimeResolver`` when available,
        otherwise falls back to ``config.runtime``.
        """
        if self._runtime_resolver is not None:
            return self._runtime_resolver.resolve_runtime(category)
        return self._config.runtime

    def _needs_sidecar(self) -> bool:
        """Return ``True`` if sidecar-based network enforcement is needed.

        Enforcement activates when ``allowed_hosts`` is non-empty (or
        ``network_allow_all`` is set) and the default network is not
        ``"none"``.
        """
        has_rules = bool(
            self._config.allowed_hosts or self._config.network_allow_all,
        )
        return has_rules and self._config.network != "none"

    async def _create_sidecar(
        self,
        docker: aiodocker.Docker,
    ) -> str:
        """Create a sidecar proxy container.

        The sidecar enforces ``allowed_hosts`` via dual-layer DNS +
        DNAT transparent proxy.  It runs on bridge network with
        ``NET_ADMIN`` capability (for iptables DNAT rules).

        Args:
            docker: Docker client.

        Returns:
            The sidecar container ID.

        Raises:
            SandboxStartError: If container creation fails.
        """
        admin_token = secrets.token_urlsafe(32)
        env_list: list[str] = [f"SIDECAR_ADMIN_TOKEN={admin_token}"]

        if self._config.network_allow_all:
            env_list.append("SIDECAR_ALLOW_ALL=1")
        else:
            hosts_csv = ",".join(self._config.allowed_hosts)
            env_list.append(f"SIDECAR_ALLOWED_HOSTS={hosts_csv}")

        dns_flag = "1" if self._config.dns_allowed else "0"
        lo_flag = "1" if self._config.loopback_allowed else "0"
        env_list.append(f"SIDECAR_DNS_ALLOWED={dns_flag}")
        env_list.append(f"SIDECAR_LOOPBACK_ALLOWED={lo_flag}")

        # Inject correlation env vars so sidecar logs can self-correlate.
        env_list.extend(build_correlation_env())

        memory_bytes = self._parse_memory_limit(_SIDECAR_MEMORY)
        nano_cpus = int(_SIDECAR_CPU * _NANO_CPUS_MULTIPLIER)

        config: dict[str, Any] = {
            "Image": self._config.sidecar_image,
            "Env": env_list,
            "HostConfig": {
                "NetworkMode": "bridge",
                "CapDrop": ["ALL"],
                "CapAdd": ["NET_ADMIN"],
                "ReadonlyRootfs": True,
                "Tmpfs": {
                    "/tmp": "size=8m,noexec,nosuid",  # noqa: S108
                    "/run": "size=1m,nosuid",  # iptables needs /run/xtables.lock
                },
                "Memory": memory_bytes,
                "NanoCpus": nano_cpus,
                "PidsLimit": _SIDECAR_PIDS,
                "AutoRemove": False,
                "SecurityOpt": ["no-new-privileges"],
            },
        }

        try:
            container = await docker.containers.create(config)  # pyright: ignore[reportAttributeAccessIssue]
        except Exception as exc:
            msg = f"Failed to create sidecar container: {exc}"
            logger.exception(
                DOCKER_EXECUTE_FAILED,
                command="sidecar",
                error=msg,
            )
            raise SandboxStartError(msg) from exc

        sidecar_id = container.id
        logger.debug(
            SANDBOX_SIDECAR_CREATED,
            sidecar_id=sidecar_id[:12],
            image=self._config.sidecar_image,
        )

        allowed = (
            "allow_all"
            if self._config.network_allow_all
            else ",".join(self._config.allowed_hosts)
        )
        logger.debug(
            SANDBOX_NETWORK_ENFORCEMENT,
            allowed_hosts=allowed,
            dns_allowed=self._config.dns_allowed,
            loopback_allowed=self._config.loopback_allowed,
        )
        return sidecar_id

    async def _wait_sidecar_healthy(
        self,
        docker: aiodocker.Docker,
        sidecar_id: str,
    ) -> None:
        """Wait for the sidecar container to report healthy.

        Polls Docker's built-in health check status every 200ms
        until ``healthy`` or timeout.

        Args:
            docker: Docker client.
            sidecar_id: Sidecar container ID.

        Raises:
            SandboxStartError: On timeout or unhealthy status.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _SIDECAR_HEALTH_TIMEOUT
        container_obj = docker.containers.container(sidecar_id)  # pyright: ignore[reportAttributeAccessIssue]

        while loop.time() < deadline:
            try:
                info = await container_obj.show()
            except TimeoutError, ConnectionError, OSError:
                await asyncio.sleep(_SIDECAR_HEALTH_POLL_INTERVAL)
                continue

            state = info.get("State", {})

            # Fail fast if sidecar exited before becoming healthy.
            container_status = state.get("Status", "")
            if container_status in ("exited", "dead"):
                msg = (
                    f"Sidecar exited before becoming healthy"
                    f" (status={container_status})"
                )
                logger.warning(
                    SANDBOX_SIDECAR_HEALTH_FAILED,
                    sidecar_id=sidecar_id[:12],
                    status=container_status,
                )
                raise SandboxStartError(msg)

            health_status = state.get("Health", {}).get("Status")
            if health_status == "healthy":
                logger.debug(
                    SANDBOX_SIDECAR_HEALTHY,
                    sidecar_id=sidecar_id[:12],
                )
                return
            if health_status == "unhealthy":
                msg = "Sidecar health check reported unhealthy"
                logger.warning(
                    SANDBOX_SIDECAR_HEALTH_FAILED,
                    sidecar_id=sidecar_id[:12],
                    status=health_status,
                )
                raise SandboxStartError(msg)

            await asyncio.sleep(_SIDECAR_HEALTH_POLL_INTERVAL)

        msg = "Sidecar health check timed out"
        logger.warning(
            SANDBOX_SIDECAR_HEALTH_FAILED,
            sidecar_id=sidecar_id[:12],
            timeout=_SIDECAR_HEALTH_TIMEOUT,
        )
        raise SandboxStartError(msg)

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
        if not limit_lower:
            msg = "Memory limit must not be empty"
            raise ValueError(msg)
        multipliers = {"k": 1024, "m": 1024**2, "g": 1024**3}
        if limit_lower[-1] in multipliers:
            result = int(limit_lower[:-1]) * multipliers[limit_lower[-1]]
        else:
            result = int(limit_lower)
        if result <= 0:
            msg = f"Memory limit must be positive, got: {limit!r}"
            raise ValueError(msg)
        return result

    async def execute(  # noqa: PLR0913
        self,
        *,
        command: str,
        args: tuple[str, ...],
        cwd: Path | None = None,
        env_overrides: Mapping[str, str] | None = None,
        timeout: float | None = None,  # noqa: ASYNC109
        category: str = "",
        owner_id: str | None = None,
    ) -> SandboxResult:
        """Execute a command inside a Docker container.

        Args:
            command: Executable name or path.
            args: Command arguments.
            cwd: Working directory (defaults to workspace root).
            env_overrides: Extra env vars (only these -- no host leakage).
            timeout: Seconds before the container is killed. Clamped
                to ``config.timeout_seconds`` if larger.
            category: Tool category for per-category runtime selection.
            owner_id: Lifecycle owner (agent ID, task ID, or ``None``).

        Returns:
            A ``SandboxResult`` with captured output and exit status.

        Raises:
            SandboxStartError: If the Docker daemon or image is unavailable.
            SandboxError: If cwd is outside the workspace boundary.
        """
        work_dir = cwd if cwd is not None else self._workspace
        self._validate_cwd(work_dir)

        effective_timeout = min(
            timeout if timeout is not None else self._config.timeout_seconds,
            self._config.timeout_seconds,
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
            category=category,
            owner_id=owner_id,
        )

    async def _run_container(  # noqa: C901, PLR0912, PLR0913, PLR0915
        self,
        *,
        docker: aiodocker.Docker,
        command: str,
        args: tuple[str, ...],
        container_cwd: str,
        env_overrides: Mapping[str, str] | None,
        timeout: float,  # noqa: ASYNC109
        category: str = "",
        owner_id: str | None = None,
    ) -> SandboxResult:
        """Create, start, and wait for a container.

        Args:
            docker: Docker client.
            command: Executable name or path.
            args: Command arguments.
            container_cwd: Container working directory.
            env_overrides: Environment variables.
            timeout: Timeout in seconds.
            category: Tool category for runtime resolution.
            owner_id: Lifecycle owner for container labeling and
                lifecycle strategy dispatch.

        Returns:
            A ``SandboxResult`` with captured output and exit status.
        """
        # Create sidecar if network enforcement is needed.
        sidecar_id: str | None = None
        network_mode: str | None = None

        if self._needs_sidecar():
            sidecar_id = await self._create_sidecar(docker)
            # Track sidecar immediately so cleanup() can find it
            # even if start/health-check fails or is cancelled.
            self._tracked_containers[f"_sidecar:{sidecar_id}"] = None
            try:
                sidecar_obj = docker.containers.container(sidecar_id)  # pyright: ignore[reportAttributeAccessIssue]
                await sidecar_obj.start()
                logger.debug(
                    SANDBOX_SIDECAR_STARTED,
                    sidecar_id=sidecar_id[:12],
                )
                await self._wait_sidecar_healthy(docker, sidecar_id)
            except BaseException as exc:
                # Catch BaseException to handle CancelledError too --
                # sidecar must be cleaned up even on task cancellation.
                removed = await self._remove_container(
                    docker,
                    sidecar_id,
                )
                if removed:
                    self._tracked_containers.pop(
                        f"_sidecar:{sidecar_id}",
                        None,
                    )
                msg = f"Sidecar startup failed: {exc}"
                raise SandboxStartError(msg) from exc
            # Don't pop the _sidecar: temp key yet -- keep it tracked
            # until the sandbox container is created and takes over.
            network_mode = f"container:{sidecar_id}"

        config = self._build_container_config(
            command=command,
            args=args,
            container_cwd=container_cwd,
            env_overrides=env_overrides,
            category=category,
            network_mode=network_mode,
            owner_id=owner_id,
        )

        try:
            container = await docker.containers.create(config)  # pyright: ignore[reportAttributeAccessIssue]
        except Exception as exc:
            if sidecar_id:
                removed = await self._remove_container(
                    docker,
                    sidecar_id,
                )
                if removed:
                    self._tracked_containers.pop(
                        f"_sidecar:{sidecar_id}",
                        None,
                    )
            msg = f"Failed to create container: {exc}"
            logger.exception(
                DOCKER_EXECUTE_FAILED,
                command=command,
                error=msg,
            )
            raise SandboxStartError(msg) from exc

        container_id = container.id
        self._tracked_containers[container_id] = sidecar_id
        # Sandbox now tracks the sidecar -- remove the temp key.
        if sidecar_id:
            self._tracked_containers.pop(
                f"_sidecar:{sidecar_id}",
                None,
            )
        logger.debug(
            DOCKER_CONTAINER_CREATED,
            container_id=container_id[:12],
            image=self._config.image,
        )

        cfg = self._log_shipping_config
        sidecar_logs: tuple[dict[str, Any], ...] = ()
        result: SandboxResult | None = None
        try:
            result = await self._start_and_wait(
                docker=docker,
                container_id=container_id,
                command=command,
                args=args,
                timeout=timeout,
            )
        finally:
            # Collect sidecar logs BEFORE container removal
            # (best-effort -- never blocks cleanup).
            if sidecar_id and cfg.enabled:
                try:
                    sidecar_logs = await collect_sidecar_logs(
                        docker,
                        sidecar_id,
                        config=cfg,
                    )
                except MemoryError, RecursionError:
                    raise
                except Exception:
                    logger.debug(
                        SANDBOX_CONTAINER_LOGS_COLLECTED,
                        sidecar_id=sidecar_id[:12],
                        status="collection_error_in_cleanup",
                        exc_info=True,
                    )

            # Ship collected logs even on execution failure so
            # sidecar network decisions are always observable.
            _stdout = result.stdout if result is not None else ""
            _stderr = result.stderr if result is not None else ""
            _ms = (result.execution_time_ms or 0) if result is not None else 0
            await ship_container_logs(
                config=cfg,
                container_id=container_id,
                sidecar_id=sidecar_id,
                stdout=_stdout,
                stderr=_stderr,
                sidecar_logs=sidecar_logs,
                execution_time_ms=_ms,
            )

            sandbox_removed = await self._remove_container(
                docker,
                container_id,
            )
            if sandbox_removed:
                self._tracked_containers.pop(container_id, None)
            if sidecar_id:
                sidecar_removed = await self._remove_container(
                    docker,
                    sidecar_id,
                )
                if sidecar_removed:
                    logger.debug(
                        SANDBOX_SIDECAR_REMOVED,
                        sidecar_id=sidecar_id[:12],
                    )
                else:
                    logger.warning(
                        SANDBOX_SIDECAR_REMOVE_FAILED,
                        sidecar_id=sidecar_id[:12],
                        error="removal failed, sidecar remains tracked",
                    )

        # Enrich result with sidecar data and agent context.
        # (Unreachable when _start_and_wait raises -- exception
        # propagates through finally.)
        assert result is not None  # noqa: S101
        import structlog.contextvars  # noqa: PLC0415

        ctx = structlog.contextvars.get_contextvars()
        return result.model_copy(
            update={
                "sidecar_id": sidecar_id,
                "sidecar_logs": sidecar_logs,
                "agent_id": ctx.get("agent_id"),
            },
        )

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
        container_obj = docker.containers.container(container_id)  # pyright: ignore[reportAttributeAccessIssue]
        try:
            await container_obj.start()
        except Exception as exc:
            msg = f"Failed to start container {container_id[:12]}: {exc}"
            logger.exception(
                DOCKER_EXECUTE_FAILED,
                container_id=container_id[:12],
                error=msg,
            )
            raise SandboxStartError(msg) from exc

        start_mono = time.monotonic()
        timed_out, returncode = await self._wait_for_exit(
            docker=docker,
            container_obj=container_obj,
            container_id=container_id,
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - start_mono) * 1000)

        stdout, stderr = await self._safe_collect_logs(
            container_obj,
            container_id,
        )
        self._log_execution_outcome(
            command,
            args,
            container_id,
            returncode,
            stderr,
        )
        if timed_out:
            return SandboxResult(
                stdout=stdout,
                stderr=stderr or f"Container timed out after {timeout}s",
                returncode=returncode,
                timed_out=True,
                container_id=container_id,
                execution_time_ms=elapsed_ms,
            )
        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            container_id=container_id,
            execution_time_ms=elapsed_ms,
        )

    async def _wait_for_exit(
        self,
        *,
        docker: aiodocker.Docker,
        container_obj: aiodocker.containers.DockerContainer,
        container_id: str,
        timeout: float,  # noqa: ASYNC109
    ) -> tuple[bool, int]:
        """Wait for the container to exit or timeout.

        Returns:
            Tuple of (timed_out, returncode).
        """
        try:
            response = await asyncio.wait_for(
                container_obj.wait(),
                timeout=timeout,
            )
            return (False, response.get("StatusCode", -1))
        except TimeoutError:
            logger.warning(
                DOCKER_EXECUTE_TIMEOUT,
                container_id=container_id[:12],
                timeout=timeout,
            )
            await self._stop_container(docker, container_id)
            return (True, -1)

    async def _safe_collect_logs(
        self,
        container_obj: aiodocker.containers.DockerContainer,
        container_id: str,
    ) -> tuple[str, str]:
        """Collect logs, returning empty strings on failure."""
        try:
            return await self._collect_logs(container_obj)
        except Exception as exc:
            logger.warning(
                DOCKER_EXECUTE_FAILED,
                container_id=container_id[:12],
                error=f"Log collection failed: {exc}",
            )
            return ("", "")

    @staticmethod
    def _log_execution_outcome(
        command: str,
        args: tuple[str, ...],
        container_id: str,
        returncode: int,
        stderr: str,
    ) -> None:
        """Log the execution outcome at the appropriate level."""
        if returncode != 0:
            logger.warning(
                DOCKER_EXECUTE_FAILED,
                command=command,
                args=args,
                returncode=returncode,
                stderr_length=len(stderr),
                stderr_head=stderr[:_MAX_STDERR_LOG_CHARS],
            )
        else:
            logger.debug(
                DOCKER_EXECUTE_SUCCESS,
                command=command,
                args=args,
                container_id=container_id[:12],
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
        stdout = "".join(stdout_logs)
        stderr = "".join(stderr_logs)
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
            container_obj = docker.containers.container(container_id)  # pyright: ignore[reportAttributeAccessIssue]
            await container_obj.stop(
                t=_STOP_TIMEOUT_SECONDS,
            )
            logger.debug(
                DOCKER_CONTAINER_STOPPED,
                container_id=container_id[:12],
            )
        except Exception as exc:
            logger.warning(
                DOCKER_CONTAINER_STOP_FAILED,
                container_id=container_id[:12],
                error=str(exc),
            )

    @staticmethod
    async def _remove_container(
        docker: aiodocker.Docker,
        container_id: str,
    ) -> bool:
        """Remove a container, forcing removal if necessary.

        Args:
            docker: Docker client.
            container_id: Container ID to remove.

        Returns:
            ``True`` if removal succeeded, ``False`` on failure.
        """
        try:
            container_obj = docker.containers.container(container_id)  # pyright: ignore[reportAttributeAccessIssue]
            await container_obj.delete(force=True)
            logger.debug(
                DOCKER_CONTAINER_REMOVED,
                container_id=container_id[:12],
            )
        except Exception as exc:
            logger.warning(
                DOCKER_CONTAINER_REMOVE_FAILED,
                container_id=container_id[:12],
                error=str(exc),
            )
            return False
        return True

    async def cleanup(self) -> None:
        """Stop and remove tracked containers, then close the Docker session.

        Removes sandbox containers first, then their paired sidecars,
        to allow graceful network shutdown.
        """
        logger.debug(
            DOCKER_CLEANUP,
            tracked_count=len(self._tracked_containers),
        )
        if self._docker is not None:
            for sandbox_id, sidecar_id in list(
                self._tracked_containers.items(),
            ):
                await self._stop_container(self._docker, sandbox_id)
                await self._remove_container(self._docker, sandbox_id)
                if sidecar_id:
                    await self._stop_container(self._docker, sidecar_id)
                    await self._remove_container(self._docker, sidecar_id)
            try:
                await self._docker.close()
            except Exception as exc:
                logger.warning(
                    DOCKER_CLEANUP,
                    error=f"Docker client close failed: {exc}",
                )
            finally:
                self._docker = None
        self._tracked_containers = {}

    async def health_check(self) -> bool:
        """Return ``True`` if the Docker daemon is reachable.

        Returns:
            ``True`` if healthy, ``False`` otherwise.
        """
        try:
            docker = await self._ensure_docker()
            await docker.version()
        except Exception as exc:
            logger.warning(
                DOCKER_HEALTH_CHECK,
                healthy=False,
                error=str(exc),
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
