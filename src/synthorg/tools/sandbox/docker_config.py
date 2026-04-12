"""Docker sandbox configuration model."""

import os
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.config import (
    CONFIG_ENV_VAR_FALLBACK,
    CONFIG_ENV_VAR_RESOLVED,
    CONFIG_VALIDATION_FAILED,
)
from synthorg.tools.sandbox.policy import SandboxPolicy  # noqa: TC001

logger = get_logger(__name__)

_VALID_NETWORK_MODES = frozenset({"none", "bridge", "host"})
_MIN_PORT = 1
_MAX_PORT = 65535
_HOST_PORT_PARTS = 2
_SANDBOX_IMAGE_ENV_VAR = "SYNTHORG_SANDBOX_IMAGE"
_FALLBACK_SANDBOX_IMAGE = "ghcr.io/aureliolo/synthorg-sandbox:latest"


def _default_sandbox_image() -> str:
    """Resolve the default sandbox image from ``SYNTHORG_SANDBOX_IMAGE``.

    The CLI injects the digest-pinned sandbox image reference into the
    backend container via this env var.  When it is unset, empty, or
    whitespace-only, fall back to the ghcr.io tag-based reference so an
    operator running the backend outside the CLI still gets a pullable
    default.  Logs both branches so operators debugging image-resolution
    issues see which source won.
    """
    raw = os.environ.get(_SANDBOX_IMAGE_ENV_VAR, "")
    value = raw.strip()
    if value:
        logger.debug(
            CONFIG_ENV_VAR_RESOLVED,
            var=_SANDBOX_IMAGE_ENV_VAR,
            resolved=value,
        )
        return value
    logger.debug(
        CONFIG_ENV_VAR_FALLBACK,
        var=_SANDBOX_IMAGE_ENV_VAR,
        fallback=_FALLBACK_SANDBOX_IMAGE,
        reason="env var unset or whitespace-only",
    )
    return _FALLBACK_SANDBOX_IMAGE


class DockerSandboxConfig(BaseModel):
    """Configuration for the Docker sandbox backend.

    Attributes:
        image: Docker image to use for sandbox containers.
        network: Default Docker network mode.
        network_overrides: Per-category network mode overrides.
        allowed_hosts: Host:port allowlist for network filtering.
        dns_allowed: Allow outbound DNS when ``allowed_hosts`` restricts
            network.  Default ``True`` (needed for hostname resolution).
            Set to ``False`` to require IP addresses in ``allowed_hosts``.
        loopback_allowed: Allow loopback traffic in restricted network
            mode.  Default ``True``.
        memory_limit: Container memory limit (Docker format).
        cpu_limit: CPU core limit for the container.
        timeout_seconds: Default command timeout in seconds.
        mount_mode: Workspace mount mode (read-write or read-only).
        runtime: Optional container runtime (e.g. ``"runsc"`` for gVisor).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    image: NotBlankStr = Field(
        default_factory=_default_sandbox_image,
        description=(
            "Docker image for sandbox containers. Precedence: explicit YAML, "
            "SYNTHORG_SANDBOX_IMAGE env var, "
            "ghcr.io/aureliolo/synthorg-sandbox:latest fallback."
        ),
    )
    network: Literal["none", "bridge", "host"] = Field(
        default="none",
        description="Default Docker network mode",
    )
    network_overrides: dict[NotBlankStr, NotBlankStr] = Field(
        default_factory=dict,
        description="Per-category network mode overrides",
    )
    runtime_overrides: dict[NotBlankStr, NotBlankStr] = Field(
        default_factory=dict,
        description="Per-category container runtime overrides",
    )
    allowed_hosts: tuple[NotBlankStr, ...] = Field(
        default=(),
        description="Host:port allowlist for network filtering",
    )
    dns_allowed: bool = Field(
        default=True,
        description=(
            "Allow outbound DNS (port 53) when allowed_hosts restricts "
            "network; set to False to require IP addresses"
        ),
    )
    loopback_allowed: bool = Field(
        default=True,
        description="Allow loopback traffic in restricted network mode",
    )
    memory_limit: NotBlankStr = Field(
        default="512m",
        description="Container memory limit (Docker format, e.g. '512m')",
    )
    cpu_limit: float = Field(default=1.0, gt=0, le=16)
    timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    mount_mode: Literal["rw", "ro"] = Field(
        default="ro",
        description="Workspace mount mode (read-only by default)",
    )
    runtime: NotBlankStr | None = Field(
        default=None,
        description="Optional container runtime (e.g. 'runsc' for gVisor)",
    )
    policy: SandboxPolicy | None = Field(
        default=None,
        description=(
            "Structured 4-domain policy overlay (filesystem, network, "
            "process, inference).  Consumed by the sandbox execution "
            "layer to apply domain-specific constraints at runtime."
        ),
    )

    @model_validator(mode="after")
    def _validate_memory_limit(self) -> Self:
        """Validate that memory_limit uses a supported format.

        Accepts an integer with an optional ``k``/``m``/``g`` suffix.
        """
        limit = self.memory_limit.strip().lower()
        if not limit:
            msg = "Memory limit must not be empty"
            logger.warning(CONFIG_VALIDATION_FAILED, field="memory_limit", reason=msg)
            raise ValueError(msg)
        multipliers = {"k", "m", "g"}
        numeric_part = limit[:-1] if limit[-1] in multipliers else limit
        try:
            value = int(numeric_part)
        except ValueError as exc:
            msg = f"Invalid memory_limit format: {self.memory_limit!r}"
            logger.warning(CONFIG_VALIDATION_FAILED, field="memory_limit", reason=msg)
            raise ValueError(msg) from exc
        if value <= 0:
            msg = f"Memory limit must be positive, got: {self.memory_limit!r}"
            logger.warning(CONFIG_VALIDATION_FAILED, field="memory_limit", reason=msg)
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_network_overrides(self) -> Self:
        """Ensure network override values are valid network modes."""
        for category, mode in self.network_overrides.items():
            if mode not in _VALID_NETWORK_MODES:
                msg = (
                    f"Invalid network mode {mode!r} for category "
                    f"{category!r}; must be one of {sorted(_VALID_NETWORK_MODES)}"
                )
                logger.warning(
                    CONFIG_VALIDATION_FAILED,
                    field="network_overrides",
                    category=category,
                    reason=msg,
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_allowed_hosts(self) -> Self:
        """Validate that allowed_hosts entries use ``host:port`` format.

        Only IPv4 addresses and hostnames are supported; IPv6
        addresses are not supported by the iptables enforcement
        script.
        """
        for entry in self.allowed_hosts:
            parts = entry.split(":")
            if len(parts) != _HOST_PORT_PARTS:
                msg = (
                    f"allowed_hosts entry {entry!r} must use "
                    "'host:port' format (exactly one ':'); "
                    "IPv6 addresses are not supported"
                )
                logger.warning(
                    CONFIG_VALIDATION_FAILED,
                    field="allowed_hosts",
                    reason=msg,
                )
                raise ValueError(msg)
            host, port_str = parts
            if not host or host == "*":
                msg = (
                    f"host part of {entry!r} must be a hostname "
                    "or IP (not empty or wildcard)"
                )
                logger.warning(
                    CONFIG_VALIDATION_FAILED,
                    field="allowed_hosts",
                    reason=msg,
                )
                raise ValueError(msg)
            try:
                port = int(port_str)
            except ValueError as exc:
                msg = f"port {port_str!r} in {entry!r} is not a valid integer"
                logger.warning(
                    CONFIG_VALIDATION_FAILED,
                    field="allowed_hosts",
                    reason=msg,
                )
                raise ValueError(msg) from exc
            if port < _MIN_PORT or port > _MAX_PORT:
                msg = (
                    f"port {port} in {entry!r} must be "
                    f"between {_MIN_PORT} and {_MAX_PORT}"
                )
                logger.warning(
                    CONFIG_VALIDATION_FAILED,
                    field="allowed_hosts",
                    reason=msg,
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_allowed_hosts_with_host_network(self) -> Self:
        """Reject allowed_hosts with network='host' (unsafe).

        Checks both the top-level ``network`` field and any
        ``network_overrides`` entries.
        """
        if not self.allowed_hosts:
            return self
        if self.network == "host":
            msg = (
                "allowed_hosts cannot be used with network='host' -- "
                "iptables rules would affect the host system"
            )
            logger.warning(
                CONFIG_VALIDATION_FAILED,
                field="allowed_hosts",
                reason=msg,
            )
            raise ValueError(msg)
        host_overrides = [
            cat for cat, mode in self.network_overrides.items() if mode == "host"
        ]
        if host_overrides:
            msg = (
                "allowed_hosts cannot be used with "
                "network_overrides containing 'host' "
                f"(categories: {sorted(host_overrides)}) -- "
                "iptables rules would affect the host system"
            )
            logger.warning(
                CONFIG_VALIDATION_FAILED,
                field="allowed_hosts",
                reason=msg,
            )
            raise ValueError(msg)
        return self
