"""Tests for middleware chain factories."""

from collections.abc import Generator

import pytest

from synthorg.core.middleware_config import (
    AgentMiddlewareConfig,
    CoordinationMiddlewareConfig,
)
from synthorg.engine.middleware.coordination_protocol import (
    BaseCoordinationMiddleware,
)
from synthorg.engine.middleware.factory import (
    build_agent_middleware_chain,
    build_coordination_middleware_chain,
)
from synthorg.engine.middleware.protocol import (
    BaseAgentMiddleware,
)
from synthorg.engine.middleware.registry import (
    clear_agent_registry,
    clear_coordination_registry,
    register_agent_middleware,
    register_coordination_middleware,
)


@pytest.fixture(autouse=True)
def _clean_registries() -> Generator[None]:
    """Clear registries before and after each test."""
    clear_agent_registry()
    clear_coordination_registry()
    yield
    clear_agent_registry()
    clear_coordination_registry()


# ── Agent chain factory ───────────────────────────────────────────


@pytest.mark.unit
class TestBuildAgentMiddlewareChain:
    """Agent middleware chain building from config."""

    def test_empty_chain_when_nothing_registered(self) -> None:
        config = AgentMiddlewareConfig(chain=("foo", "bar"))
        chain = build_agent_middleware_chain(config)
        assert len(chain) == 0

    def test_builds_chain_from_registered(self) -> None:
        def _factory_a(**_kw: object) -> BaseAgentMiddleware:
            return BaseAgentMiddleware(name="a")

        def _factory_b(**_kw: object) -> BaseAgentMiddleware:
            return BaseAgentMiddleware(name="b")

        register_agent_middleware("a", _factory_a)
        register_agent_middleware("b", _factory_b)

        config = AgentMiddlewareConfig(chain=("a", "b"))
        chain = build_agent_middleware_chain(config)
        assert chain.names == ("a", "b")

    def test_skips_unregistered(self) -> None:
        def _factory(**_kw: object) -> BaseAgentMiddleware:
            return BaseAgentMiddleware(name="a")

        register_agent_middleware("a", _factory)

        config = AgentMiddlewareConfig(chain=("a", "missing"))
        chain = build_agent_middleware_chain(config)
        assert chain.names == ("a",)

    def test_skips_on_missing_dependency(self) -> None:
        def _factory(*, required_dep: str) -> BaseAgentMiddleware:
            return BaseAgentMiddleware(name="needs_dep")

        register_agent_middleware("needs_dep", _factory)

        config = AgentMiddlewareConfig(chain=("needs_dep",))
        # No deps provided -> TypeError -> skipped
        chain = build_agent_middleware_chain(config)
        assert len(chain) == 0

    def test_passes_deps_to_factory(self) -> None:
        received: dict[str, object] = {}

        def _factory(**kw: object) -> BaseAgentMiddleware:
            received.update(kw)
            return BaseAgentMiddleware(name="dep_aware")

        register_agent_middleware("dep_aware", _factory)

        config = AgentMiddlewareConfig(chain=("dep_aware",))
        build_agent_middleware_chain(
            config,
            deps={"tracker": "mock_tracker"},
        )
        assert received["tracker"] == "mock_tracker"

    def test_preserves_chain_order(self) -> None:
        for name in ("c", "b", "a"):

            def _factory(n: str = name, **_kw: object) -> BaseAgentMiddleware:
                return BaseAgentMiddleware(name=n)

            register_agent_middleware(name, _factory)

        config = AgentMiddlewareConfig(chain=("a", "b", "c"))
        chain = build_agent_middleware_chain(config)
        assert chain.names == ("a", "b", "c")


# ── Coordination chain factory ────────────────────────────────────


@pytest.mark.unit
class TestBuildCoordinationMiddlewareChain:
    """Coordination middleware chain building from config."""

    def test_empty_chain_when_nothing_registered(self) -> None:
        config = CoordinationMiddlewareConfig(chain=("foo",))
        chain = build_coordination_middleware_chain(config)
        assert len(chain) == 0

    def test_builds_chain_from_registered(self) -> None:
        def _factory(**_kw: object) -> BaseCoordinationMiddleware:
            return BaseCoordinationMiddleware(name="gate")

        register_coordination_middleware("gate", _factory)

        config = CoordinationMiddlewareConfig(chain=("gate",))
        chain = build_coordination_middleware_chain(config)
        assert chain.names == ("gate",)

    def test_skips_unregistered(self) -> None:
        config = CoordinationMiddlewareConfig(
            chain=("missing",),
        )
        chain = build_coordination_middleware_chain(config)
        assert len(chain) == 0

    def test_skips_on_missing_dependency(self) -> None:
        def _factory(*, required: str) -> BaseCoordinationMiddleware:
            return BaseCoordinationMiddleware(name="x")

        register_coordination_middleware("x", _factory)

        config = CoordinationMiddlewareConfig(chain=("x",))
        chain = build_coordination_middleware_chain(config)
        assert len(chain) == 0
