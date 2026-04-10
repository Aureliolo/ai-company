"""Distributed task queue configuration.

Part of the Distributed Runtime design (see
``docs/design/distributed-runtime.md``). Opt-in: ``enabled=False`` by
default, and when set to ``True`` the message bus backend must be
distributed (not ``internal``).
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001


class QueueConfig(BaseModel):
    """Distributed task queue configuration.

    When ``enabled`` is ``True``, the task engine registers a
    :class:`DistributedDispatcher` observer that publishes ready tasks
    to a JetStream work-queue stream. Workers (``synthorg worker
    start``) pull claims from the stream and execute tasks via the
    backend HTTP API.

    Attributes:
        enabled: Whether the distributed queue is active. Default
            ``False`` (in-process dispatch only).
        stream_name: JetStream stream name for the work queue.
        ready_subject_prefix: Subject prefix for claim messages.
            Full subject is ``<prefix>.<task_id>``.
        dead_subject_prefix: Subject prefix for dead-letter messages.
        workers: Default worker count for ``synthorg worker start``.
        ack_wait_seconds: JetStream ack deadline. Workers must ack
            within this many seconds or the message is redelivered.
        max_deliver: Maximum redelivery attempts before a claim is
            routed to the dead-letter subject.
        heartbeat_interval_seconds: Seconds between worker heartbeat
            publications. Used for liveness detection in monitoring.
        api_url: Backend HTTP API URL that workers call to transition
            tasks. ``None`` means "derive from env at runtime".
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = Field(
        default=False,
        description="Whether the distributed queue is active",
    )
    stream_name: NotBlankStr = Field(
        default="SYNTHORG_TASKS",
        description="JetStream stream name for the work queue",
    )
    ready_subject_prefix: NotBlankStr = Field(
        default="synthorg.tasks.ready",
        description="Subject prefix for claim messages",
    )
    dead_subject_prefix: NotBlankStr = Field(
        default="synthorg.tasks.dead",
        description="Subject prefix for dead-letter messages",
    )
    workers: int = Field(
        default=4,
        gt=0,
        description="Default worker count",
    )
    ack_wait_seconds: int = Field(
        default=300,
        gt=0,
        description="JetStream ack deadline in seconds",
    )
    max_deliver: int = Field(
        default=3,
        gt=0,
        description="Max redelivery attempts before DLQ",
    )
    heartbeat_interval_seconds: int = Field(
        default=30,
        gt=0,
        description="Seconds between worker heartbeats",
    )
    api_url: str | None = Field(
        default=None,
        description="Backend HTTP API URL for task transitions",
    )

    @model_validator(mode="after")
    def _validate_subjects(self) -> Self:
        """Ensure ready and dead subjects do not overlap."""
        if self.ready_subject_prefix == self.dead_subject_prefix:
            msg = "ready_subject_prefix and dead_subject_prefix must differ"
            raise ValueError(msg)
        return self
