"""Docker sandbox configuration model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_company.core.types import NotBlankStr  # noqa: TC001


class DockerSandboxConfig(BaseModel):
    """Configuration for the Docker sandbox backend.

    Attributes:
        image: Docker image to use for sandbox containers.
        network: Default Docker network mode.
        network_overrides: Per-category network mode overrides.
        allowed_hosts: Host:port allowlist for network filtering.
        memory_limit: Container memory limit (Docker format).
        cpu_limit: CPU core limit for the container.
        timeout_seconds: Default command timeout in seconds.
        mount_mode: Workspace mount mode (read-write or read-only).
        auto_remove: Whether to auto-remove containers on exit.
        runtime: Optional container runtime (e.g. ``"runsc"`` for gVisor).
    """

    model_config = ConfigDict(frozen=True)

    image: NotBlankStr = "ai-company-sandbox:latest"
    network: Literal["none", "bridge", "host"] = "none"
    network_overrides: dict[str, str] = Field(default_factory=dict)
    allowed_hosts: tuple[str, ...] = ()
    memory_limit: NotBlankStr = "512m"
    cpu_limit: float = Field(default=1.0, gt=0, le=16)
    timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    mount_mode: Literal["rw", "ro"] = "rw"
    auto_remove: bool = True
    runtime: NotBlankStr | None = None
