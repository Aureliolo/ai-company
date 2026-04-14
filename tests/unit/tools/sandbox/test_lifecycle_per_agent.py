"""Tests for per-agent lifecycle strategy."""

import asyncio

import pytest

from synthorg.tools.sandbox.lifecycle.config import SandboxLifecycleConfig
from synthorg.tools.sandbox.lifecycle.per_agent import PerAgentStrategy
from synthorg.tools.sandbox.lifecycle.protocol import ContainerHandle

pytestmark = pytest.mark.unit


def _make_handle(cid: str = "c1") -> ContainerHandle:
    return ContainerHandle(container_id=cid)


def _make_strategy(
    grace: float = 0.1,
    max_idle: float = 300.0,
) -> PerAgentStrategy:
    config = SandboxLifecycleConfig(
        grace_period_seconds=grace,
        max_idle_seconds=max_idle,
    )
    return PerAgentStrategy(config)


class TestPerAgentAcquire:
    """acquire() reuses within same owner, creates for new owners."""

    async def test_creates_new_container(self) -> None:
        strategy = _make_strategy()
        created = _make_handle("agent-c1")

        async def create_fn() -> ContainerHandle:
            return created

        handle = await strategy.acquire(
            owner_id="agent-1",
            create_fn=create_fn,
        )
        assert handle is created

    async def test_reuses_existing_container(self) -> None:
        strategy = _make_strategy()
        calls: list[int] = []

        async def create_fn() -> ContainerHandle:
            calls.append(1)
            return _make_handle(f"c-{len(calls)}")

        h1 = await strategy.acquire(
            owner_id="agent-1",
            create_fn=create_fn,
        )
        h2 = await strategy.acquire(
            owner_id="agent-1",
            create_fn=create_fn,
        )
        assert h1 is h2
        assert len(calls) == 1

    async def test_different_owners_get_different_containers(self) -> None:
        strategy = _make_strategy()
        calls: list[int] = []

        async def create_fn() -> ContainerHandle:
            calls.append(1)
            return _make_handle(f"c-{len(calls)}")

        h1 = await strategy.acquire(
            owner_id="a1",
            create_fn=create_fn,
        )
        h2 = await strategy.acquire(
            owner_id="a2",
            create_fn=create_fn,
        )
        assert h1 is not h2
        assert len(calls) == 2


class TestPerAgentRelease:
    """release() starts grace timer; container survives within window."""

    async def test_release_starts_grace_timer(self) -> None:
        strategy = _make_strategy(grace=0.1)
        destroyed: list[str] = []

        async def create_fn() -> ContainerHandle:
            return _make_handle("grace-test")

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h.container_id)

        await strategy.acquire(owner_id="a1", create_fn=create_fn)
        await strategy.release(
            owner_id="a1",
            destroy_fn=destroy_fn,
        )
        # Container should NOT be destroyed immediately.
        assert destroyed == []
        # Wait for grace period to expire.
        await asyncio.sleep(0.2)
        assert destroyed == ["grace-test"]

    async def test_reacquire_within_grace_cancels_timer(self) -> None:
        strategy = _make_strategy(grace=0.5)
        destroyed: list[str] = []
        calls: list[int] = []

        async def create_fn() -> ContainerHandle:
            calls.append(1)
            return _make_handle(f"c-{len(calls)}")

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h.container_id)

        h1 = await strategy.acquire(
            owner_id="a1",
            create_fn=create_fn,
        )
        await strategy.release(
            owner_id="a1",
            destroy_fn=destroy_fn,
        )
        # Reacquire within grace window.
        h2 = await strategy.acquire(
            owner_id="a1",
            create_fn=create_fn,
        )
        assert h1 is h2
        assert len(calls) == 1
        # Grace timer should have been cancelled -- no destruction.
        await asyncio.sleep(0.6)
        assert destroyed == []

    async def test_release_unknown_owner_noop(self) -> None:
        strategy = _make_strategy()
        destroyed: list[ContainerHandle] = []

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h)

        await strategy.release(
            owner_id="nonexistent",
            destroy_fn=destroy_fn,
        )
        assert destroyed == []


class TestPerAgentCleanup:
    """cleanup_all() cancels timers and destroys all containers."""

    async def test_cleanup_destroys_all(self) -> None:
        strategy = _make_strategy()
        destroyed: list[str] = []

        async def make(cid: str) -> ContainerHandle:
            return _make_handle(cid)

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h.container_id)

        await strategy.acquire(
            owner_id="a1",
            create_fn=lambda: make("c1"),
        )
        await strategy.acquire(
            owner_id="a2",
            create_fn=lambda: make("c2"),
        )
        await strategy.cleanup_all(destroy_fn=destroy_fn)
        assert sorted(destroyed) == ["c1", "c2"]

    async def test_cleanup_cancels_pending_grace_timers(self) -> None:
        strategy = _make_strategy(grace=10.0)
        destroyed: list[str] = []

        async def create_fn() -> ContainerHandle:
            return _make_handle("timer-test")

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h.container_id)

        await strategy.acquire(
            owner_id="a1",
            create_fn=create_fn,
        )
        await strategy.release(
            owner_id="a1",
            destroy_fn=destroy_fn,
        )
        # Timer started but not expired. Cleanup should cancel it.
        await strategy.cleanup_all(destroy_fn=destroy_fn)
        assert "timer-test" in destroyed

    async def test_cleanup_empty_noop(self) -> None:
        strategy = _make_strategy()
        destroyed: list[ContainerHandle] = []

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h)

        await strategy.cleanup_all(destroy_fn=destroy_fn)
        assert destroyed == []

    async def test_cleanup_survives_destroy_failure(self) -> None:
        """cleanup_all continues if one destroy_fn raises."""
        strategy = _make_strategy()

        async def make(cid: str) -> ContainerHandle:
            return _make_handle(cid)

        destroyed: list[str] = []

        async def destroy_fn(h: ContainerHandle) -> None:
            if h.container_id == "c1":
                msg = "docker daemon gone"
                raise RuntimeError(msg)
            destroyed.append(h.container_id)

        await strategy.acquire(
            owner_id="a1",
            create_fn=lambda: make("c1"),
        )
        await strategy.acquire(
            owner_id="a2",
            create_fn=lambda: make("c2"),
        )
        await strategy.cleanup_all(destroy_fn=destroy_fn)
        assert "c2" in destroyed


class TestPerAgentIdleTimeout:
    """Idle timeout enforcement via _max_idle."""

    async def test_idle_container_destroyed_after_release(self) -> None:
        """Container destroyed by idle timer after release."""
        strategy = _make_strategy(grace=10.0, max_idle=0.15)
        destroyed: list[str] = []

        async def create_fn() -> ContainerHandle:
            return _make_handle("idle-test")

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h.container_id)

        await strategy.acquire(owner_id="a1", create_fn=create_fn)
        await strategy.release(owner_id="a1", destroy_fn=destroy_fn)
        # Idle timer armed on release. Wait for it to fire.
        await asyncio.sleep(0.3)
        assert "idle-test" in destroyed

    async def test_zero_max_idle_disables_timer(self) -> None:
        """max_idle=0 means no idle eviction."""
        strategy = _make_strategy(grace=10.0, max_idle=0.0)

        async def create_fn() -> ContainerHandle:
            return _make_handle("no-idle")

        async def destroy_fn(h: ContainerHandle) -> None:
            pass

        await strategy.acquire(owner_id="a1", create_fn=create_fn)
        # No idle timer should be started; container stays.
        await asyncio.sleep(0.05)
        # Verify container is still tracked (acquire returns same).
        h2 = await strategy.acquire(owner_id="a1", create_fn=create_fn)
        assert h2.container_id == "no-idle"
        await strategy.cleanup_all(destroy_fn=destroy_fn)


class TestPerAgentGraceDestroyFailure:
    """Grace-period expiry handles destroy_fn errors gracefully."""

    async def test_grace_expire_survives_destroy_failure(self) -> None:
        strategy = _make_strategy(grace=0.05)

        async def create_fn() -> ContainerHandle:
            return _make_handle("fail-destroy")

        async def destroy_fn(h: ContainerHandle) -> None:
            msg = "container already removed"
            raise RuntimeError(msg)

        await strategy.acquire(owner_id="a1", create_fn=create_fn)
        await strategy.release(
            owner_id="a1",
            destroy_fn=destroy_fn,
        )
        # Grace expires, destroy fails, but no crash.
        await asyncio.sleep(0.15)
        # Container should be forgotten even though destroy failed.
        calls: list[int] = []

        async def new_create() -> ContainerHandle:
            calls.append(1)
            return _make_handle("replacement")

        h = await strategy.acquire(owner_id="a1", create_fn=new_create)
        assert h.container_id == "replacement"
        assert len(calls) == 1
        await strategy.cleanup_all(destroy_fn=destroy_fn)
