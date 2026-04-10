"""Distributed worker: pulls claims, executes tasks, transitions via HTTP.

The worker is a separate Python process launched via
``synthorg worker start`` (Go CLI wrapper at ``cli/cmd/worker_start.go``).
It connects to NATS JetStream for claim delivery and to the backend
HTTP API for task transitions, preserving the ``TaskEngine``
single-writer invariant: workers never write to persistence directly.

The execution path is intentionally minimal in this initial
implementation: the worker fetches a claim, calls an injected
``executor`` callable with the claim's ``task_id``, and surfaces the
outcome back to the backend. The executor is the seam where future
work plugs in the real agent runtime; today it is a callable the
caller provides (typically ``synthorg.engine.agent_engine`` in a
follow-up PR).
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from synthorg.observability import get_logger
from synthorg.workers.claim import (
    JetStreamTaskQueue,
    TaskClaim,
    TaskClaimStatus,
)
from synthorg.workers.config import QueueConfig  # noqa: TC001

logger = get_logger(__name__)


TaskExecutor = Callable[[TaskClaim], Awaitable[TaskClaimStatus]]
"""Callable the worker invokes for each claim.

Takes a :class:`TaskClaim` and returns a terminal
:class:`TaskClaimStatus`. The executor is responsible for calling
the backend HTTP API to transition the task; the worker only handles
the claim ack/nack based on the returned status.
"""


class Worker:
    """Single-process distributed worker.

    Args:
        queue_config: Queue configuration (ack wait, max deliver).
        task_queue: Connected :class:`JetStreamTaskQueue`.
        executor: Async callable invoked for each claim.
        worker_id: Identifier for logging + heartbeat subject.
    """

    def __init__(
        self,
        *,
        queue_config: QueueConfig,
        task_queue: JetStreamTaskQueue,
        executor: TaskExecutor,
        worker_id: str,
    ) -> None:
        self._queue_config = queue_config
        self._task_queue = task_queue
        self._executor = executor
        self._worker_id = worker_id
        self._running = False
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Whether the worker's claim loop is active."""
        return self._running

    async def run(self) -> None:
        """Run the claim loop until :meth:`stop` is called.

        Pulls one claim at a time, invokes the executor, and acks or
        nacks the JetStream message based on the executor's returned
        status.
        """
        if self._running:
            msg = f"Worker {self._worker_id} is already running"
            raise RuntimeError(msg)
        self._running = True
        self._stop_event.clear()
        logger.info("workers.worker.started", worker_id=self._worker_id)

        try:
            while not self._stop_event.is_set():
                await self._run_once()
        finally:
            self._running = False
            logger.info("workers.worker.stopped", worker_id=self._worker_id)

    async def stop(self) -> None:
        """Signal the claim loop to exit after the current claim."""
        self._stop_event.set()

    async def _run_once(self) -> None:
        """Fetch and process a single claim."""
        claim_and_raw = await self._task_queue.next_claim(
            timeout=float(self._queue_config.ack_wait_seconds) / 2.0,
        )
        if claim_and_raw is None:
            return
        claim, raw = claim_and_raw
        status = await self._execute_claim(claim)
        await self._finalize_claim(raw, status)

    async def _execute_claim(self, claim: TaskClaim) -> TaskClaimStatus:
        """Invoke the executor, translating exceptions into RETRY."""
        logger.info(
            "workers.worker.claim_received",
            worker_id=self._worker_id,
            task_id=claim.task_id,
        )
        try:
            return await self._executor(claim)
        except Exception:
            logger.exception(
                "workers.worker.executor_failed",
                worker_id=self._worker_id,
                task_id=claim.task_id,
            )
            return TaskClaimStatus.RETRY

    async def _finalize_claim(
        self,
        raw: Any,
        status: TaskClaimStatus,
    ) -> None:
        """Ack or nack the JetStream message based on outcome."""
        terminal = {TaskClaimStatus.SUCCESS, TaskClaimStatus.FAILED}
        try:
            if status in terminal:
                await JetStreamTaskQueue.ack(raw)
            else:
                await JetStreamTaskQueue.nack(raw)
        except Exception:
            logger.exception(
                "workers.worker.finalize_failed",
                worker_id=self._worker_id,
                status=str(status),
            )


async def run_worker_pool(
    *,
    queue_config: QueueConfig,
    task_queue: JetStreamTaskQueue,
    executor: TaskExecutor,
    worker_count: int,
    worker_id_prefix: str = "worker",
) -> None:
    """Run ``worker_count`` workers concurrently until cancelled.

    Blocks until all workers exit (via ``stop`` or cancellation).
    Uses :class:`asyncio.TaskGroup` so a failing worker propagates
    the exception after sibling cancellation.
    """
    workers = [
        Worker(
            queue_config=queue_config,
            task_queue=task_queue,
            executor=executor,
            worker_id=f"{worker_id_prefix}-{i}",
        )
        for i in range(worker_count)
    ]
    logger.info(
        "workers.pool.started",
        worker_count=worker_count,
    )
    try:
        async with asyncio.TaskGroup() as tg:
            for worker in workers:
                tg.create_task(worker.run())
    finally:
        with contextlib.suppress(Exception):
            await asyncio.gather(
                *(w.stop() for w in workers),
                return_exceptions=True,
            )
