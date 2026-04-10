"""Distributed task queue workers (see Distributed Runtime design page).

Plugs into :class:`TaskEngine` via ``register_observer`` so the
single-writer mutation queue invariant is preserved. Workers are
separate Python processes that:

1. Subscribe to the JetStream work-queue stream for ready tasks.
2. Execute the task via the agent runtime.
3. Transition the task via the backend HTTP API (routing through
   the normal mutation queue).
4. Ack the JetStream message on success or nack on failure.

Import-light public surface: import the sub-modules directly to
avoid pulling ``nats-py`` on installs that do not opt into the
``distributed`` extra.
"""

from synthorg.workers.claim import TaskClaim, TaskClaimStatus
from synthorg.workers.config import QueueConfig

__all__ = ("QueueConfig", "TaskClaim", "TaskClaimStatus")
