"""Tests for SandboxRuntimeResolver."""

import pytest

from synthorg.tools.sandbox.docker_config import DockerSandboxConfig
from synthorg.tools.sandbox.runtime_resolver import SandboxRuntimeResolver

pytestmark = pytest.mark.unit


class TestSandboxRuntimeResolverResolve:
    """Tests for resolve_runtime()."""

    def test_returns_override_when_available(self) -> None:
        config = DockerSandboxConfig(
            runtime_overrides={"code_execution": "runsc"},
        )
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc", "runsc"}),
        )
        assert resolver.resolve_runtime("code_execution") == "runsc"

    def test_falls_back_to_runc_when_override_unavailable(self) -> None:
        config = DockerSandboxConfig(
            runtime_overrides={"code_execution": "runsc"},
        )
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc"}),
        )
        assert resolver.resolve_runtime("code_execution") is None

    def test_returns_global_runtime_when_no_override(self) -> None:
        config = DockerSandboxConfig(runtime="runsc")
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc", "runsc"}),
        )
        assert resolver.resolve_runtime("file_system") == "runsc"

    def test_global_runtime_falls_back_when_unavailable(self) -> None:
        config = DockerSandboxConfig(runtime="runsc")
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc"}),
        )
        assert resolver.resolve_runtime("file_system") is None

    def test_returns_none_when_no_override_no_global(self) -> None:
        config = DockerSandboxConfig()
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc"}),
        )
        assert resolver.resolve_runtime("file_system") is None

    def test_override_takes_precedence_over_global(self) -> None:
        config = DockerSandboxConfig(
            runtime="runc",
            runtime_overrides={"code_execution": "runsc"},
        )
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc", "runsc"}),
        )
        assert resolver.resolve_runtime("code_execution") == "runsc"

    def test_category_without_override_uses_global(self) -> None:
        config = DockerSandboxConfig(
            runtime="runsc",
            runtime_overrides={"code_execution": "kata"},
        )
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc", "runsc", "kata"}),
        )
        assert resolver.resolve_runtime("terminal") == "runsc"


class TestSandboxRuntimeResolverWithDefaults:
    """Tests for factory default gVisor overrides."""

    def test_default_gvisor_overrides_for_high_risk_categories(self) -> None:
        config = DockerSandboxConfig(
            runtime_overrides={
                "code_execution": "runsc",
                "terminal": "runsc",
            },
        )
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc", "runsc"}),
        )
        assert resolver.resolve_runtime("code_execution") == "runsc"
        assert resolver.resolve_runtime("terminal") == "runsc"

    def test_user_override_takes_precedence_over_factory_default(
        self,
    ) -> None:
        config = DockerSandboxConfig(
            runtime_overrides={
                "code_execution": "runc",
                "terminal": "runc",
            },
        )
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc", "runsc"}),
        )
        assert resolver.resolve_runtime("code_execution") == "runc"
        assert resolver.resolve_runtime("terminal") == "runc"


class TestSandboxRuntimeResolverProbe:
    """Tests for probe_available_runtimes()."""

    async def test_probe_returns_frozenset(self) -> None:
        result = await SandboxRuntimeResolver.probe_available_runtimes()
        assert isinstance(result, frozenset)

    async def test_probe_returns_runc_fallback_on_failure(self) -> None:
        """When Docker is unavailable, return runc as minimum fallback."""
        result = await SandboxRuntimeResolver.probe_available_runtimes()
        # In CI/test environment, Docker may not be available.
        # The probe should always return at least runc as a fallback.
        assert "runc" in result
