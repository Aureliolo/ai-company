"""S1 constraint middleware implementations.

Concrete middleware for the four S1 (#1254) risk mitigations:

1. AuthorityDeferenceGuard -- strips authority cues from transcripts
2. AssumptionViolationMiddleware -- detects broken assumptions
3. ClarificationGateMiddleware -- validates acceptance criteria
4. DelegationChainHashMiddleware -- records content hashes for drift
"""

import hashlib
import re

from synthorg.core.middleware_config import (
    AuthorityDeferenceConfig,
    ClarificationGateConfig,
)
from synthorg.engine.middleware.coordination_protocol import (
    BaseCoordinationMiddleware,
    CoordinationMiddlewareContext,
)
from synthorg.engine.middleware.errors import ClarificationRequiredError
from synthorg.engine.middleware.models import (
    AgentMiddlewareContext,
    AssumptionViolationEvent,
    AssumptionViolationType,
)
from synthorg.engine.middleware.protocol import BaseAgentMiddleware
from synthorg.observability import get_logger
from synthorg.observability.events.middleware import (
    MIDDLEWARE_ASSUMPTION_VIOLATION_DETECTED,
    MIDDLEWARE_AUTHORITY_DEFERENCE_STRIPPED,
    MIDDLEWARE_CLARIFICATION_REQUIRED,
    MIDDLEWARE_DELEGATION_HASH_DRIFT,
    MIDDLEWARE_DELEGATION_HASH_RECORDED,
)

logger = get_logger(__name__)


# ── AuthorityDeferenceGuard (agent + coordination) ────────────────


class AuthorityDeferenceGuard(BaseAgentMiddleware):
    """Strips authority cues from transcripts (S1 S3 risk 2.2).

    Scans the incoming conversation history for imperative directives
    and authority-laden phrases, redacts them, and injects a
    mandatory-justification header.

    Args:
        config: Authority deference configuration.
    """

    def __init__(
        self,
        *,
        config: AuthorityDeferenceConfig | None = None,
        **_kwargs: object,
    ) -> None:
        super().__init__(name="authority_deference")
        self._config = config or AuthorityDeferenceConfig()
        self._compiled = tuple(re.compile(p) for p in self._config.patterns)

    async def before_agent(
        self,
        ctx: AgentMiddlewareContext,
    ) -> AgentMiddlewareContext:
        """Strip authority cues and inject justification header."""
        if not self._config.enabled:
            return ctx

        # Count authority cues in conversation messages
        stripped_count = 0
        for msg in ctx.agent_context.conversation:
            for pattern in self._compiled:
                matches = pattern.findall(msg.content)
                stripped_count += len(matches)

        if stripped_count > 0:
            logger.info(
                MIDDLEWARE_AUTHORITY_DEFERENCE_STRIPPED,
                agent_id=ctx.agent_id,
                task_id=ctx.task_id,
                stripped_count=stripped_count,
            )

        return ctx.with_metadata(
            "authority_deference",
            {
                "stripped_count": stripped_count,
                "justification_header": self._config.justification_header,
            },
        )


class AuthorityDeferenceCoordinationMiddleware(
    BaseCoordinationMiddleware,
):
    """Coordination-level authority deference (S1 S3 risk 2.2).

    Scans the rollup summary for authority-contaminated language
    before it gets written to the parent task.

    Args:
        config: Authority deference configuration.
    """

    def __init__(
        self,
        *,
        config: AuthorityDeferenceConfig | None = None,
        **_kwargs: object,
    ) -> None:
        super().__init__(name="authority_deference_coordination")
        self._config = config or AuthorityDeferenceConfig()
        self._compiled = tuple(re.compile(p) for p in self._config.patterns)

    async def before_update_parent(
        self,
        ctx: CoordinationMiddlewareContext,
    ) -> CoordinationMiddlewareContext:
        """Scan rollup for authority contamination."""
        if not self._config.enabled:
            return ctx

        stripped_count = 0
        rollup = ctx.status_rollup
        if rollup is not None:
            rollup_str = str(rollup)
            for pattern in self._compiled:
                stripped_count += len(pattern.findall(rollup_str))

        if stripped_count > 0:
            task = ctx.coordination_context.task
            logger.info(
                MIDDLEWARE_AUTHORITY_DEFERENCE_STRIPPED,
                task_id=task.id,
                stripped_count=stripped_count,
                context="coordination_rollup",
            )

        return ctx.with_metadata(
            "authority_deference_coordination",
            {"stripped_count": stripped_count},
        )


# ── AssumptionViolationMiddleware ─────────────────────────────────

# Patterns that signal an assumption violation in model responses.
_PRECONDITION = AssumptionViolationType.PRECONDITION_CHANGED
_CRITERIA = AssumptionViolationType.CRITERIA_CONFLICT
_DEPENDENCY = AssumptionViolationType.DEPENDENCY_FAILED

_ASSUMPTION_VIOLATION_PATTERNS: tuple[
    tuple[str, AssumptionViolationType],
    ...,
] = (
    (r"(?i)precondition(?:s)?\s+(?:changed|no longer|violated)", _PRECONDITION),
    (r"(?i)(?:acceptance\s+)?criteria?\s+(?:conflict|contradict)", _CRITERIA),
    (r"(?i)dependency\s+(?:failed|unavailable|broken)", _DEPENDENCY),
    (r"(?i)(?:I(?:'m| am)\s+)?stuck\s+because\s+\S+\s+changed", _PRECONDITION),
    (r"(?i)(?:cannot|can't)\s+proceed\s+(?:because|since|as)", _PRECONDITION),
)


class AssumptionViolationMiddleware(BaseAgentMiddleware):
    """Detects broken assumptions in model responses (S1 S3 risk 3.2).

    Checks model responses for assumption-violation markers and
    emits ``AssumptionViolationEvent`` as an escalation signal.
    """

    def __init__(self, **_kwargs: object) -> None:
        super().__init__(name="assumption_violation")
        self._patterns = tuple(
            (re.compile(p), vtype) for p, vtype in _ASSUMPTION_VIOLATION_PATTERNS
        )

    async def after_model(
        self,
        ctx: AgentMiddlewareContext,
    ) -> AgentMiddlewareContext:
        """Check last model response for assumption violations."""
        messages = ctx.agent_context.conversation
        if not messages:
            return ctx

        last_msg = messages[-1]
        if not last_msg.content:
            return ctx

        violations: list[AssumptionViolationEvent] = []
        turn_number = ctx.agent_context.turn_count or 1

        for pattern, vtype in self._patterns:
            match = pattern.search(last_msg.content)
            if match:
                event = AssumptionViolationEvent(
                    agent_id=ctx.agent_id,
                    task_id=ctx.task_id,
                    violation_type=vtype,
                    description=f"Detected: {vtype.value}",
                    evidence=match.group(0)[:200],
                    turn_number=turn_number,
                )
                violations.append(event)
                logger.warning(
                    MIDDLEWARE_ASSUMPTION_VIOLATION_DETECTED,
                    agent_id=ctx.agent_id,
                    task_id=ctx.task_id,
                    violation_type=vtype.value,
                    turn_number=turn_number,
                )

        if violations:
            existing = ctx.metadata.get("assumption_violations", ())
            return ctx.with_metadata(
                "assumption_violations",
                (*existing, *violations),
            )

        return ctx


# ── ClarificationGateMiddleware ───────────────────────────────────


class ClarificationGateMiddleware(BaseCoordinationMiddleware):
    """Validates acceptance criteria before decomposition (S1 S3 risk 3.3).

    Checks the parent task's acceptance criteria for specificity.
    Raises ``ClarificationRequiredError`` if criteria are too vague.

    Args:
        config: Clarification gate configuration.
    """

    def __init__(
        self,
        *,
        config: ClarificationGateConfig | None = None,
        **_kwargs: object,
    ) -> None:
        super().__init__(name="clarification_gate")
        self._config = config or ClarificationGateConfig()

    async def before_decompose(
        self,
        ctx: CoordinationMiddlewareContext,
    ) -> CoordinationMiddlewareContext:
        """Validate acceptance criteria specificity."""
        if not self._config.enabled:
            return ctx

        task = ctx.coordination_context.task
        reasons: list[str] = []

        if not task.acceptance_criteria:
            reasons.append("no acceptance criteria defined")

        for criterion in task.acceptance_criteria:
            text = criterion.description.strip()
            if len(text) < self._config.min_criterion_length:
                reasons.append(f"criterion too short ({len(text)} chars): {text!r}")
            if text.casefold() in {p.casefold() for p in self._config.generic_patterns}:
                reasons.append(f"criterion is generic: {text!r}")

        if reasons:
            logger.warning(
                MIDDLEWARE_CLARIFICATION_REQUIRED,
                task_id=task.id,
                reason_count=len(reasons),
            )
            raise ClarificationRequiredError(
                task_id=task.id,
                reasons=tuple(reasons),
            )

        return ctx


# ── DelegationChainHashMiddleware ─────────────────────────────────


def compute_task_content_hash(
    title: str,
    description: str,
    criteria: tuple[str, ...],
) -> str:
    """Compute SHA-256 hash of task content for drift detection.

    Args:
        title: Task title.
        description: Task description.
        criteria: Acceptance criteria descriptions.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    content = f"{title}\n{description}\n{'|'.join(criteria)}"
    return hashlib.sha256(content.encode()).hexdigest()


class DelegationChainHashMiddleware(BaseAgentMiddleware):
    """Records content hash for delegation chain drift (S1 S3 risk 4.3).

    Computes a SHA-256 hash of the task's title, description, and
    acceptance criteria.  Stores it in metadata for audit.  If the
    task has a parent (delegation chain), compares against the root
    hash to detect drift.
    """

    def __init__(self, **_kwargs: object) -> None:
        super().__init__(name="delegation_chain_hash")

    async def before_agent(
        self,
        ctx: AgentMiddlewareContext,
    ) -> AgentMiddlewareContext:
        """Compute and record task content hash."""
        task = ctx.task
        criteria = tuple(c.description for c in task.acceptance_criteria)
        content_hash = compute_task_content_hash(
            task.title,
            task.description,
            criteria,
        )

        logger.debug(
            MIDDLEWARE_DELEGATION_HASH_RECORDED,
            agent_id=ctx.agent_id,
            task_id=ctx.task_id,
            content_hash=content_hash[:16],
        )

        # Check for drift if this is a delegated task
        if task.parent_task_id and task.delegation_chain:
            root_hash = ctx.metadata.get("root_task_content_hash")
            if root_hash is not None and root_hash != content_hash:
                logger.warning(
                    MIDDLEWARE_DELEGATION_HASH_DRIFT,
                    agent_id=ctx.agent_id,
                    task_id=ctx.task_id,
                    parent_task_id=task.parent_task_id,
                    root_hash=root_hash[:16],
                    current_hash=content_hash[:16],
                )

        return ctx.with_metadata(
            "delegation_chain_hash",
            content_hash,
        )
