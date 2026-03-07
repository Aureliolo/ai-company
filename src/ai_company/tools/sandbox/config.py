"""Subprocess sandbox configuration model."""

from pydantic import BaseModel, ConfigDict, Field


class SubprocessSandboxConfig(BaseModel):
    """Configuration for the subprocess sandbox backend.

    Attributes:
        timeout_seconds: Default command timeout in seconds.
        workspace_only: Enforce cwd within the workspace boundary.
        restricted_path: Filter PATH entries to safe directories.
        env_allowlist: Environment variable names allowed to pass through.
            Supports ``LC_*`` as a glob for all locale variables.
        env_denylist_patterns: fnmatch patterns to strip even if in
            the allowlist (e.g. ``*KEY*`` catches ``API_KEY``).
    """

    model_config = ConfigDict(frozen=True)

    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=600,
    )
    workspace_only: bool = True
    restricted_path: bool = True
    env_allowlist: tuple[str, ...] = (
        "HOME",
        "PATH",
        "USER",
        "LANG",
        "LC_*",
        "TERM",
        "TZ",
        "TMPDIR",
        "TEMP",
        "TMP",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
    )
    env_denylist_patterns: tuple[str, ...] = (
        "*KEY*",
        "*SECRET*",
        "*TOKEN*",
        "*PASSWORD*",
        "*CREDENTIAL*",
        "*PRIVATE*",
    )
