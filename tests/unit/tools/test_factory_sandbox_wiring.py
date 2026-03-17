"""Unit tests for per-category sandbox wiring in build_default_tools_from_config."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from synthorg.config.schema import RootConfig
from synthorg.tools._git_base import _BaseGitTool
from synthorg.tools.factory import build_default_tools_from_config
from synthorg.tools.file_system import BaseFileSystemTool
from synthorg.tools.sandbox.protocol import SandboxBackend
from synthorg.tools.sandbox.sandboxing_config import SandboxingConfig

_GIT_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "git_status",
        "git_log",
        "git_diff",
        "git_branch",
        "git_commit",
        "git_clone",
    }
)

_FS_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "read_file",
        "write_file",
        "edit_file",
        "list_directory",
        "delete_file",
    }
)


@pytest.mark.unit
class TestFactorySandboxWiring:
    """Tests for per-category sandbox resolution in build_default_tools_from_config."""

    @patch(
        "synthorg.tools.sandbox.factory.SubprocessSandbox",
    )
    def test_default_config_gives_git_tools_subprocess_sandbox(
        self,
        mock_subprocess_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Default SandboxingConfig gives all git tools a subprocess sandbox."""
        mock_instance = MagicMock(spec=SandboxBackend)
        mock_subprocess_cls.return_value = mock_instance

        config = RootConfig(company_name="test-corp")
        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
        )

        for tool in tools:
            if tool.name in _GIT_TOOL_NAMES:
                assert isinstance(tool, _BaseGitTool)
                assert tool._sandbox is mock_instance

    @patch(
        "synthorg.tools.sandbox.factory.DockerSandbox",
    )
    def test_docker_default_gives_git_tools_docker_sandbox(
        self,
        mock_docker_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Docker default SandboxingConfig gives all git tools a docker sandbox."""
        mock_instance = MagicMock(spec=SandboxBackend)
        mock_docker_cls.return_value = mock_instance

        sandboxing = SandboxingConfig(default_backend="docker")
        config = RootConfig(
            company_name="test-corp",
            sandboxing=sandboxing,
        )
        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
        )

        for tool in tools:
            if tool.name in _GIT_TOOL_NAMES:
                assert isinstance(tool, _BaseGitTool)
                assert tool._sandbox is mock_instance

    def test_explicit_sandbox_param_takes_precedence(
        self,
        tmp_path: Path,
    ) -> None:
        """Explicit sandbox= param overrides config-based resolution."""
        explicit_sandbox = MagicMock(spec=SandboxBackend)
        config = RootConfig(company_name="test-corp")

        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
            sandbox=explicit_sandbox,
        )

        for tool in tools:
            if tool.name in _GIT_TOOL_NAMES:
                assert isinstance(tool, _BaseGitTool)
                assert tool._sandbox is explicit_sandbox

    @patch(
        "synthorg.tools.sandbox.factory.SubprocessSandbox",
    )
    def test_explicit_sandbox_backends_map_used(
        self,
        mock_subprocess_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Explicit sandbox_backends= map is used for resolution."""
        mock_backend = MagicMock(spec=SandboxBackend)
        config = RootConfig(company_name="test-corp")

        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
            sandbox_backends={"subprocess": mock_backend},
        )

        for tool in tools:
            if tool.name in _GIT_TOOL_NAMES:
                assert isinstance(tool, _BaseGitTool)
                assert tool._sandbox is mock_backend
        # Should NOT auto-build backends when map is provided
        mock_subprocess_cls.assert_not_called()

    @patch(
        "synthorg.tools.sandbox.factory.SubprocessSandbox",
    )
    def test_auto_build_from_config_when_neither_provided(
        self,
        mock_subprocess_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Auto-builds backends from config when no sandbox args provided."""
        mock_instance = MagicMock(spec=SandboxBackend)
        mock_subprocess_cls.return_value = mock_instance

        config = RootConfig(company_name="test-corp")
        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
        )

        # Should have built subprocess backend from config
        mock_subprocess_cls.assert_called_once()

        for tool in tools:
            if tool.name in _GIT_TOOL_NAMES:
                assert isinstance(tool, _BaseGitTool)
                assert tool._sandbox is mock_instance

    def test_file_system_tools_unaffected(
        self,
        tmp_path: Path,
    ) -> None:
        """File system tools have no sandbox attribute regardless of config."""
        mock_sandbox = MagicMock(spec=SandboxBackend)
        config = RootConfig(company_name="test-corp")

        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
            sandbox=mock_sandbox,
        )

        for tool in tools:
            if tool.name in _FS_TOOL_NAMES:
                assert isinstance(tool, BaseFileSystemTool)
                assert not hasattr(tool, "_sandbox")

    def test_tool_count_unchanged(
        self,
        tmp_path: Path,
    ) -> None:
        """Sandbox wiring doesn't change the number of tools returned."""
        config = RootConfig(company_name="test-corp")

        tools_with_sandbox = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
            sandbox=MagicMock(spec=SandboxBackend),
        )

        tools_without = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
            sandbox=MagicMock(spec=SandboxBackend),
        )

        expected_count = 11
        assert len(tools_with_sandbox) == expected_count
        assert len(tools_without) == expected_count
