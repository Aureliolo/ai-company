"""Tests for SandboxPolicy 4-domain model."""

import pytest
from pydantic import ValidationError

from synthorg.tools.sandbox.policy import (
    FilesystemPolicy,
    InferencePolicy,
    NetworkPolicy,
    ProcessPolicy,
    SandboxPolicy,
)

pytestmark = pytest.mark.unit


class TestFilesystemPolicy:
    """Tests for FilesystemPolicy model."""

    def test_defaults(self) -> None:
        policy = FilesystemPolicy()
        assert policy.read_paths == ("/workspace",)
        assert policy.write_paths == ()
        assert policy.deny_paths == ("/etc/shadow", "/root")

    def test_custom_paths(self) -> None:
        policy = FilesystemPolicy(
            read_paths=("/data", "/config"),
            write_paths=("/output",),
            deny_paths=("/secrets",),
        )
        assert policy.read_paths == ("/data", "/config")
        assert policy.write_paths == ("/output",)
        assert policy.deny_paths == ("/secrets",)

    def test_frozen(self) -> None:
        policy = FilesystemPolicy()
        with pytest.raises(ValidationError):
            policy.read_paths = ("/other",)  # type: ignore[misc]


class TestNetworkPolicy:
    """Tests for NetworkPolicy model."""

    def test_defaults(self) -> None:
        policy = NetworkPolicy()
        assert policy.mode == "none"
        assert policy.allowed_hosts == ()
        assert policy.dns_allowed is True
        assert policy.loopback_allowed is True

    @pytest.mark.parametrize("mode", ["none", "bridge", "host"])
    def test_valid_modes(self, mode: str) -> None:
        policy = NetworkPolicy(mode=mode)  # type: ignore[arg-type]
        assert policy.mode == mode

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NetworkPolicy(mode="overlay")  # type: ignore[arg-type]

    def test_custom_hosts(self) -> None:
        policy = NetworkPolicy(
            mode="bridge",
            allowed_hosts=("api.example.com:443",),
        )
        assert policy.allowed_hosts == ("api.example.com:443",)


class TestProcessPolicy:
    """Tests for ProcessPolicy model."""

    def test_defaults(self) -> None:
        policy = ProcessPolicy()
        assert policy.max_processes == 64
        assert policy.allowed_executables == ()
        assert policy.deny_executables == ()

    def test_custom_limits(self) -> None:
        policy = ProcessPolicy(
            max_processes=128,
            allowed_executables=("/usr/bin/python3",),
            deny_executables=("/bin/sh",),
        )
        assert policy.max_processes == 128
        assert policy.allowed_executables == ("/usr/bin/python3",)
        assert policy.deny_executables == ("/bin/sh",)

    def test_max_processes_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_processes"):
            ProcessPolicy(max_processes=0)

    def test_max_processes_exceeds_limit_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_processes"):
            ProcessPolicy(max_processes=4097)

    def test_max_processes_at_limit(self) -> None:
        policy = ProcessPolicy(max_processes=4096)
        assert policy.max_processes == 4096


class TestInferencePolicy:
    """Tests for InferencePolicy model."""

    def test_defaults(self) -> None:
        policy = InferencePolicy()
        assert policy.route_through_proxy is True
        assert policy.allowed_providers == ()

    def test_custom_providers(self) -> None:
        policy = InferencePolicy(
            route_through_proxy=False,
            allowed_providers=("test-provider",),
        )
        assert policy.route_through_proxy is False
        assert policy.allowed_providers == ("test-provider",)


class TestSandboxPolicy:
    """Tests for the consolidated SandboxPolicy model."""

    def test_defaults(self) -> None:
        policy = SandboxPolicy()
        assert isinstance(policy.filesystem, FilesystemPolicy)
        assert isinstance(policy.network, NetworkPolicy)
        assert isinstance(policy.process, ProcessPolicy)
        assert isinstance(policy.inference, InferencePolicy)

    def test_custom_domains(self) -> None:
        policy = SandboxPolicy(
            filesystem=FilesystemPolicy(read_paths=("/data",)),
            network=NetworkPolicy(mode="bridge"),
            process=ProcessPolicy(max_processes=32),
            inference=InferencePolicy(route_through_proxy=False),
        )
        assert policy.filesystem.read_paths == ("/data",)
        assert policy.network.mode == "bridge"
        assert policy.process.max_processes == 32
        assert policy.inference.route_through_proxy is False

    def test_frozen(self) -> None:
        policy = SandboxPolicy()
        with pytest.raises(ValidationError):
            policy.filesystem = FilesystemPolicy()  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        policy = SandboxPolicy(
            network=NetworkPolicy(
                mode="bridge",
                allowed_hosts=("api.example.com:443",),
            ),
        )
        data = policy.model_dump()
        restored = SandboxPolicy.model_validate(data)
        assert restored == policy
