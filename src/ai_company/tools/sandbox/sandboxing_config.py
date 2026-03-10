"""Top-level sandboxing configuration model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_company.tools.sandbox.config import SubprocessSandboxConfig
from ai_company.tools.sandbox.docker_config import DockerSandboxConfig


class SandboxingConfig(BaseModel):
    """Top-level sandboxing configuration choosing backend per category.

    Attributes:
        default_backend: Default sandbox backend for all tool categories.
        overrides: Per-category backend overrides (category name to backend).
        subprocess: Subprocess sandbox backend configuration.
        docker: Docker sandbox backend configuration.
    """

    model_config = ConfigDict(frozen=True)

    default_backend: Literal["subprocess", "docker"] = "subprocess"
    overrides: dict[str, str] = Field(default_factory=dict)
    subprocess: SubprocessSandboxConfig = Field(
        default_factory=SubprocessSandboxConfig,
    )
    docker: DockerSandboxConfig = Field(
        default_factory=DockerSandboxConfig,
    )

    def backend_for_category(self, category: str) -> str:
        """Return the backend name for a given tool category.

        Args:
            category: Tool category name.

        Returns:
            The backend name (``"subprocess"`` or ``"docker"``).
        """
        return self.overrides.get(category, self.default_backend)
