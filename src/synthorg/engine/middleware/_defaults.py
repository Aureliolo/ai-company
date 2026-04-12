"""Default middleware registration.

Registers all built-in, S1, and #1257 middleware factories so
that ``build_agent_middleware_chain`` and
``build_coordination_middleware_chain`` can resolve the default
chain names.

Call ``register_default_middleware()`` once at application startup
(e.g. from ``AgentEngine.__init__`` or the app entrypoint).
"""

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

logger = get_logger(__name__)

_registered = False


def register_default_middleware() -> None:
    """Register all built-in middleware factories.

    Idempotent: safe to call multiple times (subsequent calls are
    no-ops due to the registry's idempotency semantics).
    """
    global _registered  # noqa: PLW0603
    if _registered:
        return

    # ── Agent middleware ──────────────────────────────────────
    register_agent_middleware(
        "checkpoint_resume",
        CheckpointResumeMiddleware,
    )
    register_agent_middleware(
        "delegation_chain_hash",
        DelegationChainHashMiddleware,
    )
    register_agent_middleware(
        "authority_deference",
        AuthorityDeferenceGuard,
    )
    register_agent_middleware(
        "sanitize_message",
        SanitizeMessageMiddleware,
    )
    register_agent_middleware(
        "security_interceptor",
        SecurityInterceptorMiddleware,
    )
    register_agent_middleware(
        "approval_gate",
        ApprovalGateMiddleware,
    )
    register_agent_middleware(
        "assumption_violation",
        AssumptionViolationMiddleware,
    )
    register_agent_middleware(
        "classification",
        ClassificationMiddleware,
    )
    register_agent_middleware(
        "cost_recording",
        CostRecordingMiddleware,
    )

    # ── Coordination middleware ───────────────────────────────
    register_coordination_middleware(
        "clarification_gate",
        ClarificationGateMiddleware,
    )
    register_coordination_middleware(
        "task_ledger",
        TaskLedgerMiddleware,
    )
    register_coordination_middleware(
        "plan_review_gate",
        PlanReviewGateMiddleware,
    )
    register_coordination_middleware(
        "progress_ledger",
        ProgressLedgerMiddleware,
    )
    register_coordination_middleware(
        "coordination_replan",
        ReplanMiddleware,
    )
    register_coordination_middleware(
        "authority_deference_coordination",
        AuthorityDeferenceCoordinationMiddleware,
    )

    _registered = True
    logger.debug(
        "default_middleware_registered",
        agent_count=9,
        coordination_count=6,
    )
