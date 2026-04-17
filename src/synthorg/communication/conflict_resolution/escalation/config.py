"""Escalation queue configuration (#1418)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EscalationQueueConfig(BaseModel):
    """Pluggable configuration for the human escalation approval queue.

    Attributes:
        backend: Which :class:`EscalationQueueStore` strategy to use.
            ``memory`` is the default for tests / ephemeral deployments;
            ``sqlite`` and ``postgres`` use the corresponding persistence
            backends.
        decision_strategy: Which :class:`DecisionProcessor` strategy to
            use.  ``winner`` only accepts "pick a winning agent"
            decisions -- the safest default.  ``hybrid`` also accepts
            ``reject`` (abandon the conflict).
        default_timeout_seconds: Maximum seconds to await a human
            decision before the resolver gives up with an ``EXPIRED``
            outcome.  ``None`` means wait forever; operators opting in
            to "wait forever" must also arrange some manual cancellation
            workflow.
        sweeper_interval_seconds: How often the
            :class:`EscalationExpirationSweeper` runs.  Values below
            ``5`` are rejected to keep the background loop inexpensive.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    backend: Literal["memory", "sqlite", "postgres"] = "memory"
    decision_strategy: Literal["winner", "hybrid"] = "winner"
    default_timeout_seconds: int | None = Field(default=None, ge=1)
    sweeper_interval_seconds: float = Field(default=30.0, ge=5.0)
