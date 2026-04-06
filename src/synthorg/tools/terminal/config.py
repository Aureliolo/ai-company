"""Configuration model for terminal/shell tools."""

from pydantic import BaseModel, ConfigDict, Field


class TerminalConfig(BaseModel):
    """Configuration for terminal/shell tools.

    Attributes:
        command_allowlist: When non-empty, only these command prefixes
            are allowed.  Empty means all non-blocked commands are
            allowed.
        command_blocklist: Command patterns that are always blocked
            regardless of allowlist.
        max_output_bytes: Maximum output size to capture.
        default_timeout: Default command execution timeout in seconds.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    command_allowlist: tuple[str, ...] = Field(
        default=(),
        description="Allowed command prefixes (empty = all non-blocked)",
    )
    command_blocklist: tuple[str, ...] = Field(
        default=(
            "rm -rf /",
            "mkfs",
            "dd if=",
            ":(){ :|:& };:",
            "shutdown",
            "reboot",
            "halt",
            "poweroff",
            "format c:",
        ),
        description="Command patterns that are always blocked",
    )
    max_output_bytes: int = Field(
        default=1_048_576,
        gt=0,
        description="Maximum output size (bytes)",
    )
    default_timeout: float = Field(
        default=30.0,
        gt=0,
        le=600.0,
        description="Default command timeout (seconds)",
    )
