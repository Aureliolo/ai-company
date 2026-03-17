"""Unit tests for the tool factory module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from synthorg.config.schema import RootConfig
from synthorg.tools._git_base import _BaseGitTool
from synthorg.tools.base import BaseTool
from synthorg.tools.factory import (
    build_default_tools,
    build_default_tools_from_config,
)
from synthorg.tools.file_system import BaseFileSystemTool
from synthorg.tools.git_tools import GitCloneTool
from synthorg.tools.git_url_validator import GitCloneNetworkPolicy

_EXPECTED_TOOL_NAMES: tuple[str, ...] = (
    "delete_file",
    "edit_file",
    "git_branch",
    "git_clone",
    "git_commit",
    "git_diff",
    "git_log",
    "git_status",
    "list_directory",
    "read_file",
    "write_file",
)


@pytest.mark.unit
class TestBuildDefaultTools:
    """Tests for build_default_tools()."""

    def test_returns_all_expected_tools(
        self,
        tmp_path: Path,
    ) -> None:
        """Factory returns all 11 built-in tools sorted by name."""
        tools = build_default_tools(workspace=tmp_path)
        names = tuple(t.name for t in tools)
        assert names == _EXPECTED_TOOL_NAMES

    def test_git_clone_receives_custom_policy(
        self,
        tmp_path: Path,
    ) -> None:
        """Custom GitCloneNetworkPolicy is wired to clone tool."""
        policy = GitCloneNetworkPolicy(
            hostname_allowlist=("internal.example.com",),
        )
        tools = build_default_tools(
            workspace=tmp_path,
            git_clone_policy=policy,
        )
        clone = next(t for t in tools if t.name == "git_clone")
        assert isinstance(clone, GitCloneTool)
        assert clone._network_policy.hostname_allowlist == ("internal.example.com",)

    def test_git_clone_default_policy_when_none(
        self,
        tmp_path: Path,
    ) -> None:
        """Without explicit policy, clone tool uses defaults."""
        tools = build_default_tools(workspace=tmp_path)
        clone = next(t for t in tools if t.name == "git_clone")
        assert isinstance(clone, GitCloneTool)
        assert clone._network_policy.hostname_allowlist == ()
        assert clone._network_policy.block_private_ips is True

    def test_git_clone_permissive_policy(
        self,
        tmp_path: Path,
    ) -> None:
        """Policy with block_private_ips=False is wired correctly."""
        policy = GitCloneNetworkPolicy(block_private_ips=False)
        tools = build_default_tools(
            workspace=tmp_path,
            git_clone_policy=policy,
        )
        clone = next(t for t in tools if t.name == "git_clone")
        assert isinstance(clone, GitCloneTool)
        assert clone._network_policy.block_private_ips is False

    def test_file_system_tools_receive_workspace(
        self,
        tmp_path: Path,
    ) -> None:
        """All file system tools have correct workspace_root."""
        tools = build_default_tools(workspace=tmp_path)
        fs_names = {
            "read_file",
            "write_file",
            "edit_file",
            "list_directory",
            "delete_file",
        }
        for tool in tools:
            if tool.name in fs_names:
                assert isinstance(tool, BaseFileSystemTool)
                assert tool.workspace_root == tmp_path.resolve()

    def test_git_tools_receive_workspace(
        self,
        tmp_path: Path,
    ) -> None:
        """All git tools have correct workspace path."""
        tools = build_default_tools(workspace=tmp_path)
        git_names = {
            "git_status",
            "git_log",
            "git_diff",
            "git_branch",
            "git_commit",
            "git_clone",
        }
        for tool in tools:
            if tool.name in git_names:
                assert isinstance(tool, _BaseGitTool)
                assert tool.workspace == tmp_path.resolve()

    def test_sandbox_passed_to_git_tools(
        self,
        tmp_path: Path,
    ) -> None:
        """Sandbox backend is forwarded to all git tools."""
        mock_sandbox = MagicMock()
        tools = build_default_tools(
            workspace=tmp_path,
            sandbox=mock_sandbox,
        )
        git_names = {
            "git_status",
            "git_log",
            "git_diff",
            "git_branch",
            "git_commit",
            "git_clone",
        }
        for tool in tools:
            if tool.name in git_names:
                assert isinstance(tool, _BaseGitTool)
                assert tool._sandbox is mock_sandbox

    def test_returns_tuple(self, tmp_path: Path) -> None:
        """Factory returns a tuple, not a list or other sequence."""
        tools = build_default_tools(workspace=tmp_path)
        assert isinstance(tools, tuple)

    def test_all_tools_are_base_tool_instances(
        self,
        tmp_path: Path,
    ) -> None:
        """Every returned tool is a BaseTool subclass instance."""
        tools = build_default_tools(workspace=tmp_path)
        for tool in tools:
            assert isinstance(tool, BaseTool)


@pytest.mark.unit
class TestBuildDefaultToolsFromConfig:
    """Tests for build_default_tools_from_config()."""

    def test_extracts_policy_from_config(
        self,
        tmp_path: Path,
    ) -> None:
        """Policy from RootConfig.git_clone flows to clone tool."""
        policy = GitCloneNetworkPolicy(
            hostname_allowlist=("git.corp.example.com",),
        )
        config = RootConfig(
            company_name="test-corp",
            git_clone=policy,
        )
        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
        )
        clone = next(t for t in tools if t.name == "git_clone")
        assert isinstance(clone, GitCloneTool)
        assert clone._network_policy.hostname_allowlist == ("git.corp.example.com",)

    def test_default_config_uses_default_policy(
        self,
        tmp_path: Path,
    ) -> None:
        """Default RootConfig yields default network policy."""
        config = RootConfig(company_name="test-corp")
        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
        )
        clone = next(t for t in tools if t.name == "git_clone")
        assert isinstance(clone, GitCloneTool)
        assert clone._network_policy.hostname_allowlist == ()
        assert clone._network_policy.block_private_ips is True

    def test_sandbox_passed_through_config_wrapper(
        self,
        tmp_path: Path,
    ) -> None:
        """Sandbox arg is forwarded by build_default_tools_from_config."""
        mock_sandbox = MagicMock()
        config = RootConfig(company_name="test-corp")
        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
            sandbox=mock_sandbox,
        )
        clone = next(t for t in tools if t.name == "git_clone")
        assert isinstance(clone, _BaseGitTool)
        assert clone._sandbox is mock_sandbox
