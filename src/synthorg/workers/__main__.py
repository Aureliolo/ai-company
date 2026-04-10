"""Entry point for `python -m synthorg.workers`.

Launched from the Go CLI via ``synthorg worker start`` (see
``cli/cmd/worker_start.go``). Wires a :class:`JetStreamTaskQueue`
against the current ``NatsConfig`` and runs a pool of
:class:`Worker` instances with a placeholder executor.

The placeholder executor acks each claim as ``SUCCESS`` after
logging it. Wiring the real agent runtime (``agent_engine``) and
the HTTP transition callback is a follow-up; this module exists so
the ``synthorg worker start`` command has something to exec while
the task queue plumbing lands incrementally.
"""

import argparse
import asyncio
import os
import sys

from synthorg.communication.config import NatsConfig
from synthorg.observability import get_logger
from synthorg.observability.events.workers import (
    WORKERS_MAIN_INVALID_WORKER_COUNT,
    WORKERS_MAIN_PLACEHOLDER_EXECUTOR_INVOKED,
)
from synthorg.workers.claim import JetStreamTaskQueue, TaskClaim, TaskClaimStatus
from synthorg.workers.config import QueueConfig
from synthorg.workers.worker import run_worker_pool

logger = get_logger(__name__)


async def _placeholder_executor(claim: TaskClaim) -> TaskClaimStatus:
    """Acknowledge the claim without executing any task logic.

    Real agent runtime integration lands in a follow-up; this
    placeholder exists so operators can smoke-test the dispatch
    path end-to-end (engine -> NATS -> worker -> ack).
    """
    logger.info(
        WORKERS_MAIN_PLACEHOLDER_EXECUTOR_INVOKED,
        task_id=claim.task_id,
        new_status=claim.new_status,
    )
    return TaskClaimStatus.SUCCESS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synthorg.workers",
        description="SynthOrg distributed task queue worker entry point.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("SYNTHORG_WORKER_COUNT", "4")),
        help="Number of concurrent workers in this process (default: 4).",
    )
    parser.add_argument(
        "--nats-url",
        default=os.environ.get("SYNTHORG_NATS_URL", "nats://localhost:4222"),
        help="NATS server URL (default: env SYNTHORG_NATS_URL or nats://localhost:4222).",
    )
    parser.add_argument(
        "--stream-prefix",
        default=os.environ.get("SYNTHORG_NATS_STREAM_PREFIX", "SYNTHORG"),
        help="JetStream stream name prefix (default: SYNTHORG).",
    )
    return parser


async def _async_main(argv: list[str]) -> int:
    """Parse arguments, start the queue, and run the worker pool."""
    args = _build_parser().parse_args(argv)
    if args.workers <= 0:
        logger.error(
            WORKERS_MAIN_INVALID_WORKER_COUNT,
            workers=args.workers,
        )
        return 2

    queue_config = QueueConfig(enabled=True, workers=args.workers)
    nats_config = NatsConfig(
        url=args.nats_url,
        stream_name_prefix=args.stream_prefix,
    )

    task_queue = JetStreamTaskQueue(
        queue_config=queue_config,
        nats_config=nats_config,
    )
    await task_queue.start()
    try:
        await run_worker_pool(
            queue_config=queue_config,
            task_queue=task_queue,
            executor=_placeholder_executor,
            worker_count=args.workers,
        )
    finally:
        await task_queue.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Synchronous entry point that delegates to the asyncio runner."""
    return asyncio.run(_async_main(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
