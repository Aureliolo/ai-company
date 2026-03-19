"""Tool factory -- instantiate built-in workspace tools with config-driven parameters.

Provides ``build_default_tools`` (core factory) and
``build_default_tools_from_config`` (convenience wrapper that
extracts parameters from a ``RootConfig``).  Both return
``tuple[BaseTool, ...]`` so callers can extend before wrapping
in a ``ToolRegistry``.
"""

from typing import TYPE_CHECKING

from synthorg.core.enums import ToolCategory
from synthorg.observability import get_logger
from synthorg.observability.events.tool import (
    TOOL_FACTORY_BUILT,
    TOOL_FACTORY_CONFIG_ENTRY,
    TOOL_FACTORY_ERROR,
)
from synthorg.tools.file_system import (
    DeleteFileTool,
    EditFileTool,
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
)
from synthorg.tools.git_tools import (
    GitBranchTool,
    GitCloneTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitStatusTool,
)
from synthorg.tools.sandbox.factory import (
    build_sandbox_backends,
    resolve_sandbox_for_category,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from synthorg.config.schema import RootConfig
    from synthorg.tools.base import BaseTool
    from synthorg.tools.git_url_validator import GitCloneNetworkPolicy
    from synthorg.tools.sandbox.protocol import SandboxBackend

logger = get_logger(__name__)


def _build_file_system_tools(
    *,
    workspace: Path,
) -> tuple[BaseTool, ...]:
    """Instantiate the five built-in file-system tools."""
    return (
        ReadFileTool(workspace_root=workspace),
        WriteFileTool(workspace_root=workspace),
        EditFileTool(workspace_root=workspace),
        ListDirectoryTool(workspace_root=workspace),
        DeleteFileTool(workspace_root=workspace),
    )


def _build_git_tools(
    *,
    workspace: Path,
    git_clone_policy: GitCloneNetworkPolicy | None,
    sandbox: SandboxBackend | None,
) -> tuple[BaseTool, ...]:
    """Instantiate the six built-in git tools."""
    return (
        GitStatusTool(workspace=workspace, sandbox=sandbox),
        GitLogTool(workspace=workspace, sandbox=sandbox),
        GitDiffTool(workspace=workspace, sandbox=sandbox),
        GitBranchTool(workspace=workspace, sandbox=sandbox),
        GitCommitTool(workspace=workspace, sandbox=sandbox),
        GitCloneTool(
            workspace=workspace,
            sandbox=sandbox,
            network_policy=git_clone_policy,
        ),
    )


def build_default_tools(
    *,
    workspace: Path,
    git_clone_policy: GitCloneNetworkPolicy | None = None,
    sandbox: SandboxBackend | None = None,
) -> tuple[BaseTool, ...]:
    """Instantiate all built-in workspace tools.

    Args:
        workspace: Absolute path to the agent workspace root.
        git_clone_policy: Network policy for git clone SSRF
            prevention.  ``None`` uses the default (block all
            private IPs, empty hostname allowlist).
        sandbox: Optional sandbox backend for subprocess
            isolation (passed to git tools).

    Returns:
        Sorted tuple of ``BaseTool`` instances.

    Raises:
        ValueError: If *workspace* is not an absolute path.
    """
    if not workspace.is_absolute():
        msg = f"workspace must be an absolute path, got: {workspace}"
        logger.warning(TOOL_FACTORY_ERROR, error=msg)
        raise ValueError(msg)

    all_tools = (
        *_build_file_system_tools(workspace=workspace),
        *_build_git_tools(
            workspace=workspace,
            git_clone_policy=git_clone_policy,
            sandbox=sandbox,
        ),
    )
    result = tuple(sorted(all_tools, key=lambda t: t.name))

    policy = git_clone_policy
    block_ips = policy.block_private_ips if policy is not None else True
    allowlist_len = len(policy.hostname_allowlist) if policy is not None else 0
    logger.info(
        TOOL_FACTORY_BUILT,
        tool_count=len(result),
        tools=tuple(t.name for t in result),
        git_clone_block_private_ips=block_ips,
        git_clone_allowlist_size=allowlist_len,
    )
    return result


def _resolve_vc_sandbox(
    *,
    config: RootConfig,
    sandbox_backends: Mapping[str, SandboxBackend] | None,
    workspace: Path,
) -> SandboxBackend:
    """Resolve the sandbox backend for the VERSION_CONTROL category.

    Builds backends from config when *sandbox_backends* is ``None``.
    """
    if sandbox_backends is None:
        sandbox_backends = build_sandbox_backends(
            config=config.sandboxing,
            workspace=workspace,
        )
    return resolve_sandbox_for_category(
        config=config.sandboxing,
        backends=sandbox_backends,
        category=ToolCategory.VERSION_CONTROL,
    )


def build_default_tools_from_config(
    *,
    workspace: Path,
    config: RootConfig,
    sandbox_backends: Mapping[str, SandboxBackend] | None = None,
) -> tuple[BaseTool, ...]:
    """Build default tools using parameters from a ``RootConfig``.

    Convenience wrapper that extracts ``config.git_clone`` and
    ``config.sandboxing`` to resolve per-category sandbox backends.

    Currently wires the ``VERSION_CONTROL`` category (git tools).
    Other categories (e.g. ``CODE_EXECUTION``) will be wired as
    their respective tool builders are added to the factory.

    Sandbox resolution priority:
        1. Explicit *sandbox_backends* -- per-category resolution
           via config.
        2. Auto-build backends from ``config.sandboxing``.

    Args:
        workspace: Absolute path to the agent workspace root.
        config: Validated root configuration.
        sandbox_backends: Pre-built mapping of backend name to instance.
            When provided, per-category resolution uses this map
            instead of auto-building backends.

    Returns:
        Sorted tuple of ``BaseTool`` instances.

    Raises:
        ValueError: If *workspace* is not an absolute path.
        KeyError: If per-category sandbox resolution finds a backend
            name not present in the built or provided backends mapping.
    """
    logger.debug(
        TOOL_FACTORY_CONFIG_ENTRY,
        source="config",
    )

    vc_sandbox = _resolve_vc_sandbox(
        config=config,
        sandbox_backends=sandbox_backends,
        workspace=workspace,
    )

    return build_default_tools(
        workspace=workspace,
        git_clone_policy=config.git_clone,
        sandbox=vc_sandbox,
    )
