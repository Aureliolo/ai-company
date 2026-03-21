"""Tests for sandbox allowed_hosts network enforcement in container config."""

from pathlib import Path
from typing import Any, Literal

import pytest

from synthorg.tools.sandbox.docker_config import DockerSandboxConfig
from synthorg.tools.sandbox.docker_sandbox import DockerSandbox

pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]


def _build_config(
    tmp_path: Path,
    *,
    network: Literal["none", "bridge", "host"] = "bridge",
    allowed_hosts: tuple[str, ...] = ("example.com:443",),
    dns_allowed: bool = True,
    loopback_allowed: bool = True,
) -> dict[str, Any]:
    """Build container config for the given sandbox settings."""
    config = DockerSandboxConfig(
        network=network,
        allowed_hosts=allowed_hosts,
        dns_allowed=dns_allowed,
        loopback_allowed=loopback_allowed,
    )
    sandbox = DockerSandbox(config=config, workspace=tmp_path)
    return sandbox._build_container_config(
        command="echo",
        args=("hello",),
        container_cwd="/workspace",
        env_overrides=None,
    )


# -- Enforcement activated -------------------------------------------


class TestAllowedHostsEnforcementActive:
    """When allowed_hosts is set and network is bridge, enforcement activates."""

    def test_sandbox_allowed_hosts_env_set(self, tmp_path: Path) -> None:
        result = _build_config(tmp_path)
        env = result["Env"]
        matches = [e for e in env if e.startswith("SANDBOX_ALLOWED_HOSTS=")]
        assert len(matches) == 1
        assert matches[0] == "SANDBOX_ALLOWED_HOSTS=example.com:443"

    def test_multiple_hosts_comma_separated(self, tmp_path: Path) -> None:
        result = _build_config(
            tmp_path,
            allowed_hosts=("api.example.com:443", "db.local:5432"),
        )
        env = result["Env"]
        hosts_env = next(e for e in env if e.startswith("SANDBOX_ALLOWED_HOSTS="))
        assert hosts_env == ("SANDBOX_ALLOWED_HOSTS=api.example.com:443,db.local:5432")

    def test_cap_add_includes_net_admin(self, tmp_path: Path) -> None:
        result = _build_config(tmp_path)
        cap_add = result["HostConfig"]["CapAdd"]
        assert cap_add == ["NET_ADMIN"]

    def test_user_set_to_root(self, tmp_path: Path) -> None:
        result = _build_config(tmp_path)
        assert result["User"] == "root"

    def test_entrypoint_set_to_sandbox_init(self, tmp_path: Path) -> None:
        result = _build_config(tmp_path)
        assert result["Entrypoint"] == ["/usr/local/bin/sandbox-init"]

    def test_cap_drop_all_still_present(self, tmp_path: Path) -> None:
        result = _build_config(tmp_path)
        assert result["HostConfig"]["CapDrop"] == ["ALL"]

    def test_run_tmpfs_mounted_for_xtables_lock(self, tmp_path: Path) -> None:
        result = _build_config(tmp_path)
        tmpfs = result["HostConfig"]["Tmpfs"]
        assert "/run" in tmpfs


# -- DNS and loopback settings ---------------------------------------


class TestAllowedHostsDnsLoopbackSettings:
    """DNS and loopback settings are passed as environment variables."""

    @pytest.mark.parametrize(
        ("dns", "loopback", "expected", "not_expected"),
        [
            (True, True, "SANDBOX_DNS_ALLOWED=1", "SANDBOX_DNS_ALLOWED=0"),
            (False, True, "SANDBOX_DNS_ALLOWED=0", "SANDBOX_DNS_ALLOWED=1"),
            (True, True, "SANDBOX_LOOPBACK_ALLOWED=1", "SANDBOX_LOOPBACK_ALLOWED=0"),
            (True, False, "SANDBOX_LOOPBACK_ALLOWED=0", "SANDBOX_LOOPBACK_ALLOWED=1"),
        ],
    )
    def test_env_flag_set(
        self,
        tmp_path: Path,
        dns: bool,
        loopback: bool,
        expected: str,
        not_expected: str,
    ) -> None:
        result = _build_config(
            tmp_path,
            dns_allowed=dns,
            loopback_allowed=loopback,
        )
        env = result["Env"]
        assert expected in env
        assert not_expected not in env
        assert env.count(expected) == 1


# -- Enforcement NOT activated ---------------------------------------


class TestAllowedHostsEnforcementInactive:
    """No enforcement when conditions are not met."""

    def test_no_enforcement_when_hosts_empty(self, tmp_path: Path) -> None:
        config = DockerSandboxConfig(network="bridge")
        sandbox = DockerSandbox(config=config, workspace=tmp_path)
        result = sandbox._build_container_config(
            command="echo",
            args=(),
            container_cwd="/workspace",
            env_overrides=None,
        )
        env = result["Env"]
        assert not any(e.startswith("SANDBOX_ALLOWED_HOSTS=") for e in env)
        assert "CapAdd" not in result["HostConfig"]
        assert "User" not in result
        assert "Entrypoint" not in result

    def test_no_enforcement_when_network_none(self, tmp_path: Path) -> None:
        config = DockerSandboxConfig(
            network="none",
            allowed_hosts=("example.com:443",),
        )
        sandbox = DockerSandbox(config=config, workspace=tmp_path)
        result = sandbox._build_container_config(
            command="echo",
            args=(),
            container_cwd="/workspace",
            env_overrides=None,
        )
        env = result["Env"]
        assert not any(e.startswith("SANDBOX_ALLOWED_HOSTS=") for e in env)
        assert "CapAdd" not in result["HostConfig"]
        assert "User" not in result
        assert "Entrypoint" not in result

    def test_default_config_no_enforcement(self, tmp_path: Path) -> None:
        """Default config (network=none, no hosts) has no enforcement."""
        sandbox = DockerSandbox(workspace=tmp_path)
        result = sandbox._build_container_config(
            command="echo",
            args=(),
            container_cwd="/workspace",
            env_overrides=None,
        )
        assert "CapAdd" not in result["HostConfig"]
        assert "User" not in result
        assert "Entrypoint" not in result


# -- env_overrides coexistence --------------------------------------


class TestAllowedHostsWithEnvOverrides:
    """User-provided env_overrides coexist with enforcement vars."""

    def test_user_env_preserved_alongside_enforcement(
        self,
        tmp_path: Path,
    ) -> None:
        config = DockerSandboxConfig(
            network="bridge",
            allowed_hosts=("example.com:443",),
        )
        sandbox = DockerSandbox(config=config, workspace=tmp_path)
        result = sandbox._build_container_config(
            command="echo",
            args=(),
            container_cwd="/workspace",
            env_overrides={"MY_VAR": "hello"},
        )
        env = result["Env"]
        assert "MY_VAR=hello" in env
        assert any(e.startswith("SANDBOX_ALLOWED_HOSTS=") for e in env)

    @pytest.mark.parametrize(
        "env_key",
        [
            "SANDBOX_ALLOWED_HOSTS",
            "SANDBOX_DNS_ALLOWED",
            "SANDBOX_LOOPBACK_ALLOWED",
        ],
    )
    def test_reserved_env_key_rejected(
        self,
        tmp_path: Path,
        env_key: str,
    ) -> None:
        from synthorg.tools.sandbox.errors import SandboxError

        config = DockerSandboxConfig(
            network="bridge",
            allowed_hosts=("example.com:443",),
        )
        sandbox = DockerSandbox(config=config, workspace=tmp_path)
        with pytest.raises(SandboxError, match="reserved"):
            sandbox._build_container_config(
                command="echo",
                args=(),
                container_cwd="/workspace",
                env_overrides={env_key: "evil"},
            )
