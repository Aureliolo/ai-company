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
from synthorg.tools.web.html_parser import HtmlParserTool
from synthorg.tools.web.http_request import HttpRequestTool

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from synthorg.config.schema import RootConfig
    from synthorg.tools.base import BaseTool
    from synthorg.tools.database.config import DatabaseConfig, DatabaseConnectionConfig
    from synthorg.tools.git_url_validator import GitCloneNetworkPolicy
    from synthorg.tools.network_validator import NetworkPolicy
    from synthorg.tools.sandbox.protocol import SandboxBackend
    from synthorg.tools.terminal.config import TerminalConfig
    from synthorg.tools.web.web_search import WebSearchProvider

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


def _build_web_tools(
    *,
    network_policy: NetworkPolicy | None = None,
    search_provider: WebSearchProvider | None = None,
    max_response_bytes: int = 1_048_576,
    request_timeout: float = 30.0,
) -> tuple[BaseTool, ...]:
    """Instantiate the built-in web tools."""
    from synthorg.tools.web.web_search import WebSearchTool  # noqa: PLC0415

    tools: list[BaseTool] = [
        HttpRequestTool(
            network_policy=network_policy,
            max_response_bytes=max_response_bytes,
            request_timeout=request_timeout,
        ),
        HtmlParserTool(),
    ]
    if search_provider is not None:
        tools.append(
            WebSearchTool(
                provider=search_provider,
                network_policy=network_policy,
            )
        )
    return tuple(tools)


def _build_database_tools(
    *,
    config: DatabaseConfig,
) -> tuple[BaseTool, ...]:
    """Instantiate the built-in database tools for each configured connection."""
    from synthorg.tools.database import SchemaInspectTool, SqlQueryTool  # noqa: PLC0415

    if not config.connections:
        return ()

    # Use the default connection, or first available
    conn_name = config.default_connection
    conn_config: DatabaseConnectionConfig | None = config.connections.get(conn_name)
    if conn_config is None and config.connections:
        conn_name = next(iter(config.connections))
        conn_config = config.connections[conn_name]
    if conn_config is None:
        return ()

    return (
        SqlQueryTool(config=conn_config),
        SchemaInspectTool(config=conn_config),
    )


def _build_terminal_tools(
    *,
    sandbox: SandboxBackend | None = None,
    config: TerminalConfig | None = None,
) -> tuple[BaseTool, ...]:
    """Instantiate the built-in terminal tools."""
    from synthorg.tools.terminal.shell_command import ShellCommandTool  # noqa: PLC0415

    return (ShellCommandTool(sandbox=sandbox, config=config),)


def build_default_tools(  # noqa: PLR0913
    *,
    workspace: Path,
    git_clone_policy: GitCloneNetworkPolicy | None = None,
    sandbox: SandboxBackend | None = None,
    web_network_policy: NetworkPolicy | None = None,
    web_search_provider: WebSearchProvider | None = None,
    database_config: DatabaseConfig | None = None,
    terminal_config: TerminalConfig | None = None,
    terminal_sandbox: SandboxBackend | None = None,
) -> tuple[BaseTool, ...]:
    """Instantiate all built-in workspace tools.

    Args:
        workspace: Absolute path to the agent workspace root.
        git_clone_policy: Network policy for git clone SSRF
            prevention.  ``None`` uses the default (block all
            private IPs, empty hostname allowlist).
        sandbox: Optional sandbox backend for subprocess
            isolation (passed to git tools).
        web_network_policy: Network policy for web tools.
        web_search_provider: Optional search provider for web search.
        database_config: Database configuration.  ``None`` skips
            database tool creation.
        terminal_config: Terminal tool configuration.
        terminal_sandbox: Sandbox backend for terminal tools.

    Returns:
        Sorted tuple of ``BaseTool`` instances.

    Raises:
        ValueError: If *workspace* is not an absolute path.
    """
    if not workspace.is_absolute():
        msg = f"workspace must be an absolute path, got: {workspace}"
        logger.warning(TOOL_FACTORY_ERROR, error=msg)
        raise ValueError(msg)

    all_tools: list[BaseTool] = [
        *_build_file_system_tools(workspace=workspace),
        *_build_git_tools(
            workspace=workspace,
            git_clone_policy=git_clone_policy,
            sandbox=sandbox,
        ),
        *_build_web_tools(
            network_policy=web_network_policy,
            search_provider=web_search_provider,
        ),
        *_build_terminal_tools(
            sandbox=terminal_sandbox,
            config=terminal_config,
        ),
    ]

    if database_config is not None:
        all_tools.extend(
            _build_database_tools(config=database_config),
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


def build_default_tools_from_config(
    *,
    workspace: Path,
    config: RootConfig,
    sandbox_backends: Mapping[str, SandboxBackend] | None = None,
    web_search_provider: WebSearchProvider | None = None,
) -> tuple[BaseTool, ...]:
    """Build default tools using parameters from a ``RootConfig``.

    Convenience wrapper that extracts tool configurations and
    resolves per-category sandbox backends from ``config.sandboxing``.

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
        web_search_provider: Optional web search provider to inject
            into the web search tool.

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

    # Build sandbox backends once for all categories.
    resolved_backends = sandbox_backends or build_sandbox_backends(
        config=config.sandboxing,
        workspace=workspace,
    )

    vc_sandbox = resolve_sandbox_for_category(
        config=config.sandboxing,
        backends=resolved_backends,
        category=ToolCategory.VERSION_CONTROL,
    )

    # Resolve terminal sandbox if configured
    terminal_sandbox: SandboxBackend | None = None
    if config.terminal is not None:
        try:
            terminal_sandbox = resolve_sandbox_for_category(
                config=config.sandboxing,
                backends=resolved_backends,
                category=ToolCategory.TERMINAL,
            )
        except KeyError:
            logger.warning(
                TOOL_FACTORY_ERROR,
                error=(
                    "No sandbox backend for TERMINAL category; "
                    "terminal tools will operate without sandbox"
                ),
            )

    # Extract web config
    web_policy: NetworkPolicy | None = None
    if config.web is not None:
        web_policy = config.web.network_policy

    return build_default_tools(
        workspace=workspace,
        git_clone_policy=config.git_clone,
        sandbox=vc_sandbox,
        web_network_policy=web_policy,
        web_search_provider=web_search_provider,
        database_config=config.database,
        terminal_config=config.terminal,
        terminal_sandbox=terminal_sandbox,
    )
