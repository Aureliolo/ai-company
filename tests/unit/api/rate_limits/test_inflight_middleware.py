"""Unit tests for PerOpConcurrencyMiddleware (#1489, SEC-2).

Concurrent scenarios use :class:`TestClient` (sync) driven by a
``ThreadPoolExecutor`` so requests land in the Litestar app truly in
parallel.  ``AsyncTestClient`` + ``httpx.ASGITransport`` serialises
requests in this harness and hides concurrency races -- see
``test_per_op_rate_limit_concurrent.py`` for the end-to-end integration
spec that mirrors this pattern.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import pytest
from litestar import Litestar, post
from litestar.datastructures import State
from litestar.testing import AsyncTestClient, TestClient

from synthorg.api.exception_handlers import EXCEPTION_HANDLERS
from synthorg.api.rate_limits.in_memory_inflight import InMemoryInflightStore
from synthorg.api.rate_limits.inflight_config import PerOpConcurrencyConfig
from synthorg.api.rate_limits.inflight_guard import per_op_concurrency
from synthorg.api.rate_limits.inflight_middleware import PerOpConcurrencyMiddleware

pytestmark = pytest.mark.unit

_HOLD_SECONDS = 0.3


def _make_test_app(
    handler: Any,
    *,
    config: PerOpConcurrencyConfig | None = None,
) -> Litestar:
    """Build a Litestar app with the inflight store + middleware wired."""
    store = InMemoryInflightStore()
    cfg = config or PerOpConcurrencyConfig()
    return Litestar(
        route_handlers=[handler],
        middleware=[PerOpConcurrencyMiddleware()],
        state=State(
            {
                "per_op_inflight_store": store,
                "per_op_inflight_config": cfg,
            },
        ),
        exception_handlers=dict(EXCEPTION_HANDLERS),  # type: ignore[arg-type]
    )


def _fire_concurrent_posts(
    client: TestClient[Any],
    path: str,
    count: int,
) -> list[httpx.Response]:
    """Fire ``count`` POSTs in parallel via a thread pool."""
    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = [pool.submit(client.post, path) for _ in range(count)]
        return [f.result() for f in futures]


class TestUnannotatedHandlersPassThrough:
    """Handlers without ``opt[per_op_concurrency]`` are unaffected."""

    async def test_no_opt_means_no_enforcement(self) -> None:
        @post("/t")
        async def handler() -> dict[str, bool]:
            return {"ok": True}

        async with AsyncTestClient(app=_make_test_app(handler)) as client:
            resp = await client.post("/t")
            assert resp.status_code == 201


class TestConcurrencyEnforcement:
    """Opt-annotated handlers enforce inflight caps."""

    def test_concurrent_requests_partially_denied(self) -> None:
        """5 concurrent requests with max_inflight=2 -> 2 ok, 3 denied."""

        @post(
            "/t",
            opt=per_op_concurrency("test.cap", max_inflight=2, key="ip"),
        )
        async def handler() -> dict[str, bool]:
            await asyncio.sleep(_HOLD_SECONDS)
            return {"ok": True}

        with TestClient(app=_make_test_app(handler)) as client:
            results = _fire_concurrent_posts(client, "/t", 5)
        statuses = [r.status_code for r in results]
        assert statuses.count(201) == 2
        assert statuses.count(429) == 3
        # Every 429 carries the concurrency error code + Retry-After.
        for resp in results:
            if resp.status_code == 429:
                body = resp.json()
                assert body["error_detail"]["error_category"] == "rate_limit"
                assert body["error_detail"]["error_code"] == 5002
                assert body["error_detail"]["retryable"] is True
                assert int(resp.headers["Retry-After"]) >= 1

    async def test_permit_released_on_success(self) -> None:
        @post(
            "/t",
            opt=per_op_concurrency("test.released", max_inflight=1, key="ip"),
        )
        async def handler() -> dict[str, bool]:
            return {"ok": True}

        async with AsyncTestClient(app=_make_test_app(handler)) as client:
            for _ in range(5):
                resp = await client.post("/t")
                assert resp.status_code == 201

    async def test_permit_released_on_handler_exception(self) -> None:
        fail_first = {"n": 1}

        @post(
            "/t",
            opt=per_op_concurrency(
                "test.exception",
                max_inflight=1,
                key="ip",
            ),
        )
        async def handler() -> dict[str, bool]:
            if fail_first["n"] > 0:
                fail_first["n"] -= 1
                msg = "first-try-boom"
                raise RuntimeError(msg)
            return {"ok": True}

        async with AsyncTestClient(app=_make_test_app(handler)) as client:
            first = await client.post("/t")
            assert first.status_code == 500  # handler raised
            # If the permit leaked, this would be 429.  It should be 201.
            second = await client.post("/t")
            assert second.status_code == 201


class TestConfigGates:
    """Config ``enabled=False`` and zero-override disable enforcement."""

    async def test_disabled_config_bypasses_middleware(self) -> None:
        @post(
            "/t",
            opt=per_op_concurrency(
                "test.disabled",
                max_inflight=1,
                key="ip",
            ),
        )
        async def handler() -> dict[str, bool]:
            await asyncio.sleep(_HOLD_SECONDS)
            return {"ok": True}

        cfg = PerOpConcurrencyConfig(enabled=False)
        async with AsyncTestClient(
            app=_make_test_app(handler, config=cfg),
        ) as client:
            results = await asyncio.gather(
                *(client.post("/t") for _ in range(3)),
            )
            for resp in results:
                assert resp.status_code == 201

    async def test_zero_override_disables_single_operation(self) -> None:
        @post(
            "/t",
            opt=per_op_concurrency(
                "test.zero",
                max_inflight=1,
                key="ip",
            ),
        )
        async def handler() -> dict[str, bool]:
            await asyncio.sleep(_HOLD_SECONDS)
            return {"ok": True}

        cfg = PerOpConcurrencyConfig(overrides={"test.zero": 0})
        async with AsyncTestClient(
            app=_make_test_app(handler, config=cfg),
        ) as client:
            results = await asyncio.gather(
                *(client.post("/t") for _ in range(3)),
            )
            for resp in results:
                assert resp.status_code == 201


class TestOverrides:
    """Config overrides replace decorator defaults."""

    def test_override_tightens_default(self) -> None:
        @post(
            "/t",
            opt=per_op_concurrency(
                "test.tightened",
                max_inflight=100,
                key="ip",
            ),
        )
        async def handler() -> dict[str, bool]:
            await asyncio.sleep(_HOLD_SECONDS)
            return {"ok": True}

        cfg = PerOpConcurrencyConfig(overrides={"test.tightened": 1})
        with TestClient(app=_make_test_app(handler, config=cfg)) as client:
            results = _fire_concurrent_posts(client, "/t", 3)
        statuses = [r.status_code for r in results]
        assert statuses.count(201) == 1
        assert statuses.count(429) == 2


class TestBucketSharing:
    """Two operations passing the SAME operation name share a bucket."""

    def test_same_operation_shares_bucket(self) -> None:
        @post(
            "/start",
            opt=per_op_concurrency(
                "test.shared",
                max_inflight=1,
                key="ip",
            ),
        )
        async def start() -> dict[str, bool]:
            await asyncio.sleep(_HOLD_SECONDS)
            return {"ok": True}

        @post(
            "/resume",
            opt=per_op_concurrency(
                "test.shared",
                max_inflight=1,
                key="ip",
            ),
        )
        async def resume() -> dict[str, bool]:
            await asyncio.sleep(_HOLD_SECONDS)
            return {"ok": True}

        store = InMemoryInflightStore()
        cfg = PerOpConcurrencyConfig()
        app = Litestar(
            route_handlers=[start, resume],
            middleware=[PerOpConcurrencyMiddleware()],
            state=State(
                {
                    "per_op_inflight_store": store,
                    "per_op_inflight_config": cfg,
                },
            ),
            exception_handlers=dict(EXCEPTION_HANDLERS),  # type: ignore[arg-type]
        )
        with TestClient(app=app) as client, ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(client.post, "/start"),
                pool.submit(client.post, "/resume"),
            ]
            results = [f.result() for f in futures]
        statuses = sorted(r.status_code for r in results)
        # Exactly one succeeded; the other was denied by the shared bucket.
        assert statuses == [201, 429]


class TestGuardFactoryValidation:
    """``per_op_concurrency`` opt-factory rejects invalid arguments."""

    def test_empty_operation_rejected(self) -> None:
        with pytest.raises(ValueError, match="operation"):
            per_op_concurrency("", max_inflight=1)

    def test_whitespace_only_operation_rejected(self) -> None:
        with pytest.raises(ValueError, match="operation"):
            per_op_concurrency("   ", max_inflight=1)

    def test_zero_max_inflight_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_inflight"):
            per_op_concurrency("test.op", max_inflight=0)

    def test_negative_max_inflight_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_inflight"):
            per_op_concurrency("test.op", max_inflight=-1)
