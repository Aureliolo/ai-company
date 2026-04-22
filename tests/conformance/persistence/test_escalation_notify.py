"""Conformance tests for ``EscalationQueueStore.subscribe_notifications``.

Postgres arm emits a ``NOTIFY`` via a second pool connection and
verifies the subscriber receives the payload within a short window.
SQLite arm asserts the context manager enters + exits cleanly on
cancellation without yielding (the protocol explicitly allows a noop
iterator for single-process backends).
"""

import asyncio
import contextlib

import pytest

from synthorg.persistence.protocol import PersistenceBackend

pytestmark = pytest.mark.integration


class TestEscalationNotifyConformance:
    async def test_postgres_emits_and_receives(
        self, backend: PersistenceBackend
    ) -> None:
        """Postgres LISTEN/NOTIFY delivers payloads to the subscriber."""
        if backend.backend_name != "postgres":
            pytest.skip("Postgres-only: exercises LISTEN/NOTIFY semantics")

        repo = backend.build_escalations(notify_channel="conformance_channel")
        payload_queue: asyncio.Queue[str] = asyncio.Queue()
        received_first = asyncio.Event()
        listener_ready = asyncio.Event()

        async def _listen() -> None:
            async with repo.subscribe_notifications("conformance_channel") as gen:
                # LISTEN has registered by the time the context manager
                # yields; signal the producer to fire the NOTIFY.
                listener_ready.set()
                async for payload in gen:
                    await payload_queue.put(payload)
                    received_first.set()
                    return

        listener = asyncio.create_task(_listen())
        try:
            await asyncio.wait_for(listener_ready.wait(), timeout=5.0)
            pool = repo.pool  # type: ignore[attr-defined]
            async with pool.connection() as conn, conn.cursor() as cur:
                await conn.set_autocommit(True)
                await cur.execute(
                    "SELECT pg_notify(%s, %s)",
                    ("conformance_channel", "esc-001:decided"),
                )
            await asyncio.wait_for(received_first.wait(), timeout=5.0)
            assert await payload_queue.get() == "esc-001:decided"
        finally:
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener

    async def test_sqlite_subscription_is_noop(
        self, backend: PersistenceBackend
    ) -> None:
        """SQLite (single-process) yields an iterator that never emits."""
        if backend.backend_name != "sqlite":
            pytest.skip("SQLite-only: single-process noop subscription")

        repo = backend.build_escalations()
        # Deterministic readiness signal: the consumer sets this once the
        # context manager has actually entered. Using ``asyncio.sleep`` as
        # a readiness check was scheduler-dependent under ``-n 8`` and
        # could race the assertion on busy workers.
        entered = asyncio.Event()

        async def _consume() -> None:
            async with repo.subscribe_notifications("conformance_channel") as gen:
                entered.set()
                async for _ in gen:
                    # Should never yield on SQLite.
                    msg = "sqlite subscribe_notifications yielded unexpectedly"
                    raise AssertionError(msg)

        consumer = asyncio.create_task(_consume())
        try:
            await asyncio.wait_for(entered.wait(), timeout=5.0)
            assert not consumer.done()
        finally:
            consumer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await consumer
