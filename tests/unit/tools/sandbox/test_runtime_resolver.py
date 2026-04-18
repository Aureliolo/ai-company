"""Tests for SandboxRuntimeResolver."""

import pytest

from synthorg.tools.sandbox.docker_config import DockerSandboxConfig
from synthorg.tools.sandbox.factory import merge_gvisor_defaults
from synthorg.tools.sandbox.runtime_resolver import SandboxRuntimeResolver
from synthorg.tools.sandbox.sandboxing_config import SandboxingConfig

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

    def test_returns_none_when_override_unavailable_and_no_global(self) -> None:
        config = DockerSandboxConfig(
            runtime_overrides={"code_execution": "runsc"},
        )
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc"}),
        )
        assert resolver.resolve_runtime("code_execution") is None

    def test_falls_through_to_global_when_override_unavailable(self) -> None:
        """When per-category override is unavailable, fall through to global."""
        config = DockerSandboxConfig(
            runtime="runc",
            runtime_overrides={"code_execution": "runsc"},
        )
        resolver = SandboxRuntimeResolver(
            config=config,
            available_runtimes=frozenset({"runc"}),
        )
        assert resolver.resolve_runtime("code_execution") == "runc"

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


class TestSandboxRuntimeResolverWithMergedDefaults:
    """Tests for factory-default gVisor overrides via merge_gvisor_defaults."""

    def test_default_gvisor_overrides_for_high_risk_categories(self) -> None:
        """merge_gvisor_defaults injects runsc for code_execution/terminal."""
        base = SandboxingConfig(default_backend="docker")
        merged = merge_gvisor_defaults(base)
        resolver = SandboxRuntimeResolver(
            config=merged.docker,
            available_runtimes=frozenset({"runc", "runsc"}),
        )
        assert resolver.resolve_runtime("code_execution") == "runsc"
        assert resolver.resolve_runtime("terminal") == "runsc"

    def test_user_override_takes_precedence_over_factory_default(
        self,
    ) -> None:
        """User-supplied runtime_overrides beat the factory defaults."""
        base = SandboxingConfig(
            default_backend="docker",
            docker=DockerSandboxConfig(
                runtime_overrides={
                    "code_execution": "runc",
                    "terminal": "runc",
                },
            ),
        )
        merged = merge_gvisor_defaults(base)
        resolver = SandboxRuntimeResolver(
            config=merged.docker,
            available_runtimes=frozenset({"runc", "runsc"}),
        )
        assert resolver.resolve_runtime("code_execution") == "runc"
        assert resolver.resolve_runtime("terminal") == "runc"


class TestSandboxRuntimeResolverProbe:
    """Tests for probe_available_runtimes() with mocked aiodocker."""

    async def test_probe_returns_discovered_runtimes(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Probe parses Runtimes from Docker info."""

        class _MockSystem:
            @staticmethod
            async def info() -> dict[str, object]:
                return {"Runtimes": {"runc": {}, "runsc": {}}}

        class _MockDocker:
            system = _MockSystem()

            async def __aenter__(self) -> _MockDocker:
                return self

            async def __aexit__(self, *_: object) -> None:
                return None

        monkeypatch.setattr("aiodocker.Docker", _MockDocker)
        result = await SandboxRuntimeResolver.probe_available_runtimes()
        assert result == frozenset({"runc", "runsc"})

    async def test_probe_falls_back_on_missing_runtimes_key(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing Runtimes key falls back to runc."""

        class _MockSystem:
            @staticmethod
            async def info() -> dict[str, object]:
                return {}

        class _MockDocker:
            system = _MockSystem()

            async def __aenter__(self) -> _MockDocker:
                return self

            async def __aexit__(self, *_: object) -> None:
                return None

        monkeypatch.setattr("aiodocker.Docker", _MockDocker)
        result = await SandboxRuntimeResolver.probe_available_runtimes()
        assert result == frozenset({"runc"})

    async def test_probe_falls_back_on_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Probe returns runc fallback when Docker is unavailable."""

        def _raise_error() -> None:
            msg = "daemon unavailable"
            raise ConnectionError(msg)

        monkeypatch.setattr("aiodocker.Docker", _raise_error)
        result = await SandboxRuntimeResolver.probe_available_runtimes()
        assert result == frozenset({"runc"})

    async def test_probe_falls_back_on_timeout(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Wedged-but-reachable daemon trips the startup timeout cap.

        ``aiodocker`` inherits aiohttp's 300 s ``sock_read`` default;
        the :func:`asyncio.timeout` wrapper must short-circuit to the
        ``runc`` fallback so startup doesn't stall for five minutes.
        """
        import asyncio

        class _MockSystem:
            @staticmethod
            async def info() -> dict[str, object]:
                # Simulate a wedged daemon: never returns until cancelled.
                await asyncio.Event().wait()
                return {}

        class _MockDocker:
            system = _MockSystem()

            async def __aenter__(self) -> _MockDocker:
                return self

            async def __aexit__(self, *_: object) -> None:
                return None

        monkeypatch.setattr("aiodocker.Docker", _MockDocker)
        monkeypatch.setattr(
            "synthorg.tools.sandbox.runtime_resolver._RUNTIME_PROBE_TIMEOUT_SECONDS",
            0.01,
        )
        result = await SandboxRuntimeResolver.probe_available_runtimes()
        assert result == frozenset({"runc"})
