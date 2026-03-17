"""Tool factory — instantiate built-in workspace tools with config-driven parameters.

Provides ``build_default_tools`` (core factory) and
``build_default_tools_from_config`` (convenience wrapper that
extracts parameters from a ``RootConfig``).  Both return
``tuple[BaseTool, ...]`` so callers can extend before wrapping
in a ``ToolRegistry``.
"""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.tool import TOOL_FACTORY_BUILT
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

if TYPE_CHECKING:
    from pathlib import Path

    from synthorg.config.schema import RootConfig
    from synthorg.tools.base import BaseTool
    from synthorg.tools.git_url_validator import GitCloneNetworkPolicy
    from synthorg.tools.sandbox.protocol import SandboxBackend

logger = get_logger(__name__)


def build_default_tools(
    *,
    workspace: Path,
    git_clone_policy: GitCloneNetworkPolicy | None = None,
    sandbox: SandboxBackend | None = None,
) -> tuple[BaseTool, ...]:
    """Instantiate all built-in workspace tools.

    Returns a sorted tuple of tool instances ready for use or
    extension before wrapping in a ``ToolRegistry``.

    Args:
        workspace: Absolute path to the agent workspace root.
        git_clone_policy: Network policy for git clone SSRF
            prevention.  ``None`` uses the default (block all
            private IPs, empty hostname allowlist).
        sandbox: Optional sandbox backend for git subprocess
            isolation.

    Returns:
        Tuple of ``BaseTool`` instances sorted by name.
    """
    fs_tools: list[BaseTool] = [
        ReadFileTool(workspace_root=workspace),
        WriteFileTool(workspace_root=workspace),
        EditFileTool(workspace_root=workspace),
        ListDirectoryTool(workspace_root=workspace),
        DeleteFileTool(workspace_root=workspace),
    ]

    git_tools: list[BaseTool] = [
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
    ]

    result = tuple(sorted(fs_tools + git_tools, key=lambda t: t.name))

    logger.info(
        TOOL_FACTORY_BUILT,
        tool_count=len(result),
        tools=tuple(t.name for t in result),
    )

    return result


def build_default_tools_from_config(
    *,
    workspace: Path,
    config: RootConfig,
    sandbox: SandboxBackend | None = None,
) -> tuple[BaseTool, ...]:
    """Build default tools using parameters from a ``RootConfig``.

    Convenience wrapper that extracts ``config.git_clone`` and
    delegates to :func:`build_default_tools`.

    Args:
        workspace: Absolute path to the agent workspace root.
        config: Validated root configuration.
        sandbox: Optional sandbox backend for git subprocess
            isolation.

    Returns:
        Tuple of ``BaseTool`` instances sorted by name.
    """
    return build_default_tools(
        workspace=workspace,
        git_clone_policy=config.git_clone,
        sandbox=sandbox,
    )
