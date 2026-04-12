"""Tests for middleware registries."""

from collections.abc import Generator

import pytest

from synthorg.engine.middleware.coordination_protocol import (
    BaseCoordinationMiddleware,
)
from synthorg.engine.middleware.errors import MiddlewareRegistryError
from synthorg.engine.middleware.protocol import BaseAgentMiddleware
from synthorg.engine.middleware.registry import (
    clear_agent_registry,
    clear_coordination_registry,
    get_agent_middleware_factory,
    get_coordination_middleware_factory,
    register_agent_middleware,
    register_coordination_middleware,
    registered_agent_middleware_names,
    registered_coordination_middleware_names,
)


@pytest.fixture(autouse=True)
def _clean_registries() -> Generator[None]:
    """Clear registries before and after each test."""
    clear_agent_registry()
    clear_coordination_registry()
    yield
    clear_agent_registry()
    clear_coordination_registry()


def _make_agent_mw(**_kwargs: object) -> BaseAgentMiddleware:
    return BaseAgentMiddleware(name="test")


def _make_agent_mw_other(**_kwargs: object) -> BaseAgentMiddleware:
    return BaseAgentMiddleware(name="test_other")


def _make_coord_mw(**_kwargs: object) -> BaseCoordinationMiddleware:
    return BaseCoordinationMiddleware(name="test")


# ── Agent registry ────────────────────────────────────────────────


@pytest.mark.unit
class TestAgentRegistry:
    """Agent middleware registry operations."""

    def test_register_and_lookup(self) -> None:
        register_agent_middleware("test", _make_agent_mw)
        factory = get_agent_middleware_factory("test")
        assert factory is _make_agent_mw

    def test_idempotent_registration(self) -> None:
        register_agent_middleware("test", _make_agent_mw)
        register_agent_middleware("test", _make_agent_mw)
        assert registered_agent_middleware_names() == ("test",)

    def test_conflicting_registration_raises(self) -> None:
        register_agent_middleware("test", _make_agent_mw)
        with pytest.raises(MiddlewareRegistryError, match="agent"):
            register_agent_middleware("test", _make_agent_mw_other)

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(
            MiddlewareRegistryError,
            match="Unknown",
        ):
            get_agent_middleware_factory("nonexistent")

    def test_registered_names(self) -> None:
        register_agent_middleware("a", _make_agent_mw)
        register_agent_middleware("b", _make_agent_mw_other)
        names = registered_agent_middleware_names()
        assert "a" in names
        assert "b" in names

    def test_clear(self) -> None:
        register_agent_middleware("test", _make_agent_mw)
        clear_agent_registry()
        assert registered_agent_middleware_names() == ()


# ── Coordination registry ─────────────────────────────────────────


@pytest.mark.unit
class TestCoordinationRegistry:
    """Coordination middleware registry operations."""

    def test_register_and_lookup(self) -> None:
        register_coordination_middleware("test", _make_coord_mw)
        factory = get_coordination_middleware_factory("test")
        assert factory is _make_coord_mw

    def test_idempotent_registration(self) -> None:
        register_coordination_middleware("test", _make_coord_mw)
        register_coordination_middleware("test", _make_coord_mw)
        names = registered_coordination_middleware_names()
        assert names == ("test",)

    def test_conflicting_raises(self) -> None:
        def _other(**_kw: object) -> BaseCoordinationMiddleware:
            return BaseCoordinationMiddleware(name="other")

        register_coordination_middleware("test", _make_coord_mw)
        with pytest.raises(
            MiddlewareRegistryError,
            match="coordination",
        ):
            register_coordination_middleware("test", _other)

    def test_unknown_raises(self) -> None:
        with pytest.raises(MiddlewareRegistryError):
            get_coordination_middleware_factory("nonexistent")

    def test_clear(self) -> None:
        register_coordination_middleware("test", _make_coord_mw)
        clear_coordination_registry()
        assert registered_coordination_middleware_names() == ()
