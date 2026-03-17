"""Integration tests for tool factory + config loading pipeline."""

from pathlib import Path

import pytest

from synthorg.config.loader import load_config_from_string
from synthorg.tools.factory import (
    build_default_tools,
    build_default_tools_from_config,
)
from synthorg.tools.git_tools import GitCloneTool
from synthorg.tools.registry import ToolRegistry

_EXPECTED_TOOL_COUNT: int = 11


@pytest.mark.integration
class TestToolFactoryConfigIntegration:
    """Integration: YAML config -> RootConfig -> factory -> tool instances."""

    def test_yaml_with_allowlist_wires_to_clone_tool(
        self,
        tmp_path: Path,
    ) -> None:
        """YAML hostname_allowlist propagates to GitCloneTool."""
        yaml_str = """\
company_name: test-corp
git_clone:
  hostname_allowlist:
    - internal.example.com
"""
        config = load_config_from_string(yaml_str)
        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
        )
        clone = next(t for t in tools if t.name == "git_clone")
        assert isinstance(clone, GitCloneTool)
        assert clone._network_policy.hostname_allowlist == ("internal.example.com",)

    def test_yaml_empty_git_clone_uses_defaults(
        self,
        tmp_path: Path,
    ) -> None:
        """Empty git_clone section yields default policy."""
        yaml_str = """\
company_name: test-corp
git_clone: {}
"""
        config = load_config_from_string(yaml_str)
        tools = build_default_tools_from_config(
            workspace=tmp_path,
            config=config,
        )
        clone = next(t for t in tools if t.name == "git_clone")
        assert isinstance(clone, GitCloneTool)
        assert clone._network_policy.hostname_allowlist == ()
        assert clone._network_policy.block_private_ips is True

    def test_factory_tools_form_valid_registry(
        self,
        tmp_path: Path,
    ) -> None:
        """Factory output can be wrapped in ToolRegistry without errors."""
        tools = build_default_tools(workspace=tmp_path)
        registry = ToolRegistry(tools)
        assert len(list(registry.all_tools())) == _EXPECTED_TOOL_COUNT
