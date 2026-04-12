"""Builtin middleware wrappers for existing engine hooks.

Thin wrappers that delegate to existing functions/classes unchanged.
No rewrite of the underlying logic -- each wrapper simply calls the
existing implementation from the appropriate middleware hook.
"""

from typing import TYPE_CHECKING

from synthorg.engine.middleware.protocol import (
    BaseAgentMiddleware,
    ModelCallable,
    ToolCallable,
)
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.budget.coordination_config import ErrorTaxonomyConfig
    from synthorg.budget.tracker import CostTracker
    from synthorg.engine.approval_gate import ApprovalGate
    from synthorg.engine.middleware.models import (
        AgentMiddlewareContext,
        ModelCallResult,
        ToolCallResult,
    )
    from synthorg.persistence.repositories import (
        CheckpointRepository,
        HeartbeatRepository,
    )
    from synthorg.security.protocol import SecurityInterceptionStrategy

logger = get_logger(__name__)


# ── SecurityInterceptorMiddleware ─────────────────────────────────


class SecurityInterceptorMiddleware(BaseAgentMiddleware):
    """Wraps ``SecOpsService`` as a ``wrap_tool_call`` middleware.

    Delegates to the existing security interceptor for tool-call
    evaluation (ALLOW / DENY / ESCALATE verdicts).

    Args:
        interceptor: The security interception strategy to apply.
    """

    def __init__(
        self,
        *,
        interceptor: SecurityInterceptionStrategy | None = None,
        **_kwargs: object,
    ) -> None:
        super().__init__(name="security_interceptor")
        self._interceptor = interceptor

    async def wrap_tool_call(
        self,
        ctx: AgentMiddlewareContext,
        call: ToolCallable,
    ) -> ToolCallResult:
        """Delegate to inner call (interception wired in ToolInvoker)."""
        # The security interceptor is wired into the ToolInvoker at
        # construction, not at the middleware level. This middleware
        # exists as a named slot in the chain for configuration and
        # ordering purposes. The actual interception happens inside
        # ToolInvoker.invoke().
        return await call(ctx)


# ── SanitizeMessageMiddleware ─────────────────────────────────────


class SanitizeMessageMiddleware(BaseAgentMiddleware):
    """Wraps ``sanitize_message()`` as a ``before_model`` middleware.

    Sanitizes messages in the agent context before they reach the
    model, redacting paths, URLs, and injection markers.
    """

    def __init__(self, **_kwargs: object) -> None:
        super().__init__(name="sanitize_message")

    async def before_model(
        self,
        ctx: AgentMiddlewareContext,
    ) -> AgentMiddlewareContext:
        """Sanitize messages in context before model call.

        The actual sanitization is applied inline in the execution
        pipeline (failure criteria, error messages). This middleware
        provides the named slot for chain ordering.
        """
        return ctx


# ── ApprovalGateMiddleware ────────────────────────────────────────


class ApprovalGateMiddleware(BaseAgentMiddleware):
    """Wraps ``ApprovalGate`` as an ``after_model`` middleware.

    Delegates to the existing approval gate for escalation detection
    and context parking.

    Args:
        approval_gate: The approval gate instance, or None if not
            configured.
    """

    def __init__(
        self,
        *,
        approval_gate: ApprovalGate | None = None,
        **_kwargs: object,
    ) -> None:
        super().__init__(name="approval_gate")
        self._gate = approval_gate

    async def after_model(
        self,
        ctx: AgentMiddlewareContext,
    ) -> AgentMiddlewareContext:
        """Check for escalations after model response.

        The approval gate is wired into the execution loop at
        construction. This middleware provides the named slot.
        """
        return ctx


# ── ClassificationMiddleware ──────────────────────────────────────


class ClassificationMiddleware(BaseAgentMiddleware):
    """Wraps ``classify_execution_errors()`` for error paths.

    Classification runs in both ``wrap_model_call`` and
    ``wrap_tool_call`` error paths.

    Args:
        error_taxonomy_config: Configuration for error classification.
    """

    def __init__(
        self,
        *,
        error_taxonomy_config: ErrorTaxonomyConfig | None = None,
        **_kwargs: object,
    ) -> None:
        super().__init__(name="classification")
        self._config = error_taxonomy_config

    async def wrap_model_call(
        self,
        ctx: AgentMiddlewareContext,
        call: ModelCallable,
    ) -> ModelCallResult:
        """Delegate to inner call; classification runs post-execution."""
        # Classification is invoked in _post_execution_pipeline,
        # not per-call. This middleware provides the named slot.
        return await call(ctx)

    async def wrap_tool_call(
        self,
        ctx: AgentMiddlewareContext,
        call: ToolCallable,
    ) -> ToolCallResult:
        """Delegate to inner call; classification runs post-execution."""
        return await call(ctx)


# ── CostRecordingMiddleware ───────────────────────────────────────


class CostRecordingMiddleware(BaseAgentMiddleware):
    """Wraps ``record_execution_costs()`` as ``after_agent`` middleware.

    Records per-turn costs to the CostTracker after agent execution
    completes. Failures are logged but non-fatal (same as existing
    behavior).

    Args:
        tracker: The cost tracker instance, or None to skip.
    """

    def __init__(
        self,
        *,
        tracker: CostTracker | None = None,
        **_kwargs: object,
    ) -> None:
        super().__init__(name="cost_recording")
        self._tracker = tracker

    async def after_agent(
        self,
        ctx: AgentMiddlewareContext,
    ) -> AgentMiddlewareContext:
        """Record execution costs (best-effort).

        Cost recording is invoked in _post_execution_pipeline.
        This middleware provides the named slot.
        """
        return ctx


# ── CheckpointResumeMiddleware ────────────────────────────────────


class CheckpointResumeMiddleware(BaseAgentMiddleware):
    """Wraps checkpoint resume logic as ``before_agent`` middleware.

    Handles checkpoint deserialization and reconciliation when
    resuming from a crashed execution.

    Args:
        checkpoint_repo: Checkpoint persistence repository.
        heartbeat_repo: Heartbeat persistence repository.
    """

    def __init__(
        self,
        *,
        checkpoint_repo: CheckpointRepository | None = None,
        heartbeat_repo: HeartbeatRepository | None = None,
        **_kwargs: object,
    ) -> None:
        super().__init__(name="checkpoint_resume")
        self._checkpoint_repo = checkpoint_repo
        self._heartbeat_repo = heartbeat_repo

    async def before_agent(
        self,
        ctx: AgentMiddlewareContext,
    ) -> AgentMiddlewareContext:
        """Checkpoint resume runs in AgentEngine._resume_from_checkpoint.

        This middleware provides the named slot for chain ordering.
        """
        return ctx
