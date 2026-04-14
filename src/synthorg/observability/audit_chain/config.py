"""AuditChainConfig -- opt-in configuration for the audit chain sink."""

from pathlib import Path  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class AuditChainConfig(BaseModel):
    """Configuration for the quantum-safe audit chain.

    Attributes:
        enabled: Whether the audit chain sink is active.
        backend: Signing backend (``"asqav"`` only for now).
        tsa_url: RFC 3161 TSA endpoint for timestamping.
            ``None`` uses local clock only.
        signing_key_path: Path to signing key file.
        chain_storage_path: Path for chain persistence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    enabled: bool = Field(
        default=False,
        description="Whether the audit chain sink is active",
    )
    backend: Literal["asqav"] = Field(
        default="asqav",
        description="Signing backend",
    )
    tsa_url: NotBlankStr | None = Field(
        default=None,
        description="RFC 3161 TSA endpoint (None = local clock only)",
    )
    signing_key_path: Path | None = Field(
        default=None,
        description="Path to signing key file",
    )
    chain_storage_path: Path | None = Field(
        default=None,
        description="Path for chain persistence",
    )
