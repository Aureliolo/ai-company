"""Tests for per-task lifecycle strategy."""

import pytest

from synthorg.tools.sandbox.lifecycle.per_task import PerTaskStrategy
from synthorg.tools.sandbox.lifecycle.protocol import ContainerHandle

pytestmark = pytest.mark.unit


def _make_handle(cid: str = "c1") -> ContainerHandle:
    return ContainerHandle(container_id=cid)


class TestPerTaskAcquire:
    """acquire() reuses within same owner, creates for new owners."""

    async def test_creates_new_container(self) -> None:
        strategy = PerTaskStrategy()
        created = _make_handle("task-c1")

        async def create_fn() -> ContainerHandle:
            return created

        handle = await strategy.acquire(
            owner_id="task-1",
            create_fn=create_fn,
        )
        assert handle is created

    async def test_reuses_existing_container(self) -> None:
        strategy = PerTaskStrategy()
        calls: list[int] = []

        async def create_fn() -> ContainerHandle:
            calls.append(1)
            return _make_handle(f"c-{len(calls)}")

        h1 = await strategy.acquire(owner_id="task-1", create_fn=create_fn)
        h2 = await strategy.acquire(owner_id="task-1", create_fn=create_fn)
        assert h1 is h2
        assert len(calls) == 1

    async def test_different_owners_get_different_containers(self) -> None:
        strategy = PerTaskStrategy()
        calls: list[int] = []

        async def create_fn() -> ContainerHandle:
            calls.append(1)
            return _make_handle(f"c-{len(calls)}")

        h1 = await strategy.acquire(owner_id="task-1", create_fn=create_fn)
        h2 = await strategy.acquire(owner_id="task-2", create_fn=create_fn)
        assert h1 is not h2
        assert len(calls) == 2


class TestPerTaskRelease:
    """release() destroys the container immediately."""

    async def test_release_destroys(self) -> None:
        strategy = PerTaskStrategy()
        handle = _make_handle("to-destroy")
        destroyed: list[ContainerHandle] = []

        async def create_fn() -> ContainerHandle:
            return handle

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h)

        await strategy.acquire(owner_id="t1", create_fn=create_fn)
        await strategy.release(owner_id="t1", destroy_fn=destroy_fn)
        assert destroyed == [handle]

    async def test_release_unknown_owner_noop(self) -> None:
        strategy = PerTaskStrategy()
        destroyed: list[ContainerHandle] = []

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h)

        await strategy.release(
            owner_id="nonexistent",
            destroy_fn=destroy_fn,
        )
        assert destroyed == []

    async def test_acquire_after_release_creates_new(self) -> None:
        strategy = PerTaskStrategy()
        calls: list[int] = []

        async def create_fn() -> ContainerHandle:
            calls.append(1)
            return _make_handle(f"c-{len(calls)}")

        async def destroy_fn(h: ContainerHandle) -> None:
            pass

        h1 = await strategy.acquire(owner_id="t1", create_fn=create_fn)
        await strategy.release(owner_id="t1", destroy_fn=destroy_fn)
        h2 = await strategy.acquire(owner_id="t1", create_fn=create_fn)
        assert h1 is not h2
        assert len(calls) == 2


class TestPerTaskCleanup:
    """cleanup_all() destroys all tracked containers."""

    async def test_cleanup_destroys_all(self) -> None:
        strategy = PerTaskStrategy()
        destroyed: list[str] = []

        async def make(cid: str) -> ContainerHandle:
            return _make_handle(cid)

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h.container_id)

        await strategy.acquire(
            owner_id="t1",
            create_fn=lambda: make("c1"),
        )
        await strategy.acquire(
            owner_id="t2",
            create_fn=lambda: make("c2"),
        )
        await strategy.cleanup_all(destroy_fn=destroy_fn)
        assert sorted(destroyed) == ["c1", "c2"]

    async def test_cleanup_empty_noop(self) -> None:
        strategy = PerTaskStrategy()
        destroyed: list[ContainerHandle] = []

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h)

        await strategy.cleanup_all(destroy_fn=destroy_fn)
        assert destroyed == []

    async def test_cleanup_survives_destroy_failure(self) -> None:
        """cleanup_all continues if one destroy_fn raises."""
        strategy = PerTaskStrategy()
        destroyed: list[str] = []

        async def make(cid: str) -> ContainerHandle:
            return _make_handle(cid)

        async def destroy_fn(h: ContainerHandle) -> None:
            if h.container_id == "c1":
                msg = "docker daemon gone"
                raise RuntimeError(msg)
            destroyed.append(h.container_id)

        await strategy.acquire(
            owner_id="t1",
            create_fn=lambda: make("c1"),
        )
        await strategy.acquire(
            owner_id="t2",
            create_fn=lambda: make("c2"),
        )
        await strategy.cleanup_all(destroy_fn=destroy_fn)
        assert "c2" in destroyed


class TestPerTaskDoubleRelease:
    """Edge cases around release semantics."""

    async def test_double_release_noop(self) -> None:
        """Second release for same owner is a no-op."""
        strategy = PerTaskStrategy()
        destroyed: list[str] = []

        async def create_fn() -> ContainerHandle:
            return _make_handle("double-rel")

        async def destroy_fn(h: ContainerHandle) -> None:
            destroyed.append(h.container_id)

        await strategy.acquire(owner_id="t1", create_fn=create_fn)
        await strategy.release(owner_id="t1", destroy_fn=destroy_fn)
        await strategy.release(owner_id="t1", destroy_fn=destroy_fn)
        assert destroyed == ["double-rel"]
