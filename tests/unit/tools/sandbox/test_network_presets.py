"""Tests for network rule presets and DockerSandboxConfig preset integration."""

import pytest

from synthorg.tools.sandbox.docker_config import DockerSandboxConfig
from synthorg.tools.sandbox.network_presets import PRESETS

pytestmark = pytest.mark.unit


class TestPresetData:
    """Validate preset data is well-formed."""

    @pytest.mark.parametrize("name", sorted(PRESETS))
    def test_preset_entries_are_valid_host_port(self, name: str) -> None:
        for entry in PRESETS[name]:
            parts = entry.split(":")
            assert len(parts) == 2, f"{entry!r} must be host:port"
            host, port_str = parts
            assert host, f"host part of {entry!r} must not be empty"
            port = int(port_str)
            assert 1 <= port <= 65535, f"port {port} out of range"

    def test_presets_registry_not_empty(self) -> None:
        assert len(PRESETS) >= 3


class TestPresetsIntegration:
    """DockerSandboxConfig merges presets into allowed_hosts."""

    def test_single_preset_merged(self) -> None:
        config = DockerSandboxConfig(
            network="bridge",
            network_presets=("git",),
        )
        for entry in PRESETS["git"]:
            assert entry in config.allowed_hosts

    def test_multiple_presets_merged(self) -> None:
        config = DockerSandboxConfig(
            network="bridge",
            network_presets=("python-dev", "git"),
        )
        for entry in PRESETS["python-dev"]:
            assert entry in config.allowed_hosts
        for entry in PRESETS["git"]:
            assert entry in config.allowed_hosts

    def test_preset_merged_with_explicit_hosts(self) -> None:
        config = DockerSandboxConfig(
            network="bridge",
            allowed_hosts=("custom.api.com:443",),
            network_presets=("git",),
        )
        assert "custom.api.com:443" in config.allowed_hosts
        for entry in PRESETS["git"]:
            assert entry in config.allowed_hosts

    def test_no_duplicates_after_merge(self) -> None:
        config = DockerSandboxConfig(
            network="bridge",
            allowed_hosts=("github.com:443",),
            network_presets=("git",),
        )
        count = config.allowed_hosts.count("github.com:443")
        assert count == 1, f"github.com:443 appears {count} times"

    def test_unknown_preset_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown network preset"):
            DockerSandboxConfig(
                network="bridge",
                network_presets=("nonexistent-preset",),
            )


class TestAllowAllMutualExclusion:
    """network_allow_all and allowed_hosts are mutually exclusive."""

    def test_allow_all_with_hosts_raises(self) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            DockerSandboxConfig(
                network="bridge",
                network_allow_all=True,
                allowed_hosts=("example.com:443",),
            )

    def test_allow_all_with_presets_raises(self) -> None:
        """Presets merge into allowed_hosts before allow_all check."""
        with pytest.raises(ValueError, match="mutually exclusive"):
            DockerSandboxConfig(
                network="bridge",
                network_allow_all=True,
                network_presets=("git",),
            )

    def test_allow_all_without_hosts_ok(self) -> None:
        config = DockerSandboxConfig(
            network="bridge",
            network_allow_all=True,
        )
        assert config.network_allow_all

    def test_hosts_without_allow_all_ok(self) -> None:
        config = DockerSandboxConfig(
            network="bridge",
            allowed_hosts=("example.com:443",),
        )
        assert not config.network_allow_all
