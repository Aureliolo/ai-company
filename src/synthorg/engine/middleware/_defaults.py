"""Default middleware registration.

Registers all built-in, S1, and #1257 middleware factories so
that ``build_agent_middleware_chain`` and
``build_coordination_middleware_chain`` can resolve the default
chain names.

Call ``register_default_middleware()`` once at application startup
(e.g. from ``AgentEngine.__init__`` or the app entrypoint).
"""

from typing import Any

from synthorg.engine.middleware.builtin import (
    ApprovalGateMiddleware,
    CheckpointResumeMiddleware,
    ClassificationMiddleware,
    CostRecordingMiddleware,
    SanitizeMessageMiddleware,
    SecurityInterceptorMiddleware,
)
from synthorg.engine.middleware.coordination_constraints import (
    PlanReviewGateMiddleware,
    ProgressLedgerMiddleware,
    ReplanMiddleware,
    TaskLedgerMiddleware,
)
from synthorg.engine.middleware.registry import (
    register_agent_middleware,
    register_coordination_middleware,
)
from synthorg.engine.middleware.s1_constraints import (
    AssumptionViolationMiddleware,
    AuthorityDeferenceCoordinationMiddleware,
    AuthorityDeferenceGuard,
    ClarificationGateMiddleware,
    DelegationChainHashMiddleware,
)
from synthorg.observability import get_logger
from synthorg.observability.events.middleware import (
    MIDDLEWARE_DEFAULTS_REGISTERED,
)

logger = get_logger(__name__)

_registered = False

# ── Default middleware tables ─────────────────────────────────────

_AGENT_DEFAULTS: tuple[tuple[str, Any], ...] = (
    ("checkpoint_resume", CheckpointResumeMiddleware),
    ("delegation_chain_hash", DelegationChainHashMiddleware),
    ("authority_deference", AuthorityDeferenceGuard),
    ("sanitize_message", SanitizeMessageMiddleware),
    ("security_interceptor", SecurityInterceptorMiddleware),
    ("approval_gate", ApprovalGateMiddleware),
    ("assumption_violation", AssumptionViolationMiddleware),
    ("classification", ClassificationMiddleware),
    ("cost_recording", CostRecordingMiddleware),
)

_COORDINATION_DEFAULTS: tuple[tuple[str, Any], ...] = (
    ("clarification_gate", ClarificationGateMiddleware),
    ("task_ledger", TaskLedgerMiddleware),
    ("plan_review_gate", PlanReviewGateMiddleware),
    ("progress_ledger", ProgressLedgerMiddleware),
    ("coordination_replan", ReplanMiddleware),
    (
        "authority_deference_coordination",
        AuthorityDeferenceCoordinationMiddleware,
    ),
)


def register_default_middleware() -> None:
    """Register all built-in middleware factories.

    Idempotent: safe to call multiple times (subsequent calls are
    no-ops due to the registry's idempotency semantics).
    """
    global _registered  # noqa: PLW0603
    if _registered:
        return

    for name, factory in _AGENT_DEFAULTS:
        register_agent_middleware(name, factory)

    for name, factory in _COORDINATION_DEFAULTS:
        register_coordination_middleware(name, factory)

    _registered = True
    logger.debug(
        MIDDLEWARE_DEFAULTS_REGISTERED,
        agent_count=len(_AGENT_DEFAULTS),
        coordination_count=len(_COORDINATION_DEFAULTS),
    )
