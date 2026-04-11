"""Protocol-level detectors for delegation, review, and authority.

These detectors validate structural protocol compliance rather than
analysing conversation semantics.  They check delegation chain
integrity, review pipeline consistency, and authority boundary
adherence.
"""

from typing import TYPE_CHECKING

from synthorg.budget.coordination_config import (
    DetectionScope,
    ErrorCategory,
)
from synthorg.engine.classification.models import (
    ErrorFinding,
    ErrorSeverity,
)
from synthorg.engine.review.models import ReviewVerdict
from synthorg.observability import get_logger
from synthorg.observability.events.classification import (
    DETECTOR_COMPLETE,
    DETECTOR_START,
)

if TYPE_CHECKING:
    from synthorg.engine.classification.protocol import DetectionContext

logger = get_logger(__name__)


class DelegationProtocolDetector:
    """Validates delegation protocol integrity.

    Checks:
    - Delegated tasks have a ``parent_task_id`` linking to the root.
    - Delegation chain does not contain the delegatee (circular).
    - Delegatee is not the same agent as the last delegator in chain.
    """

    @property
    def category(self) -> ErrorCategory:
        """Error category this detector targets."""
        return ErrorCategory.DELEGATION_PROTOCOL_VIOLATION

    @property
    def supported_scopes(self) -> frozenset[DetectionScope]:
        """Detection scopes this detector can operate on."""
        return frozenset({DetectionScope.SAME_TASK, DetectionScope.TASK_TREE})

    async def detect(
        self,
        context: DetectionContext,
    ) -> tuple[ErrorFinding, ...]:
        """Check delegation requests for protocol violations.

        Args:
            context: Detection context with delegation data.

        Returns:
            Tuple of delegation violation findings.
        """
        logger.debug(
            DETECTOR_START,
            detector="delegation_protocol",
            message_count=len(context.delegation_requests),
        )
        findings: list[ErrorFinding] = []

        for req in context.delegation_requests:
            task = req.task

            # Check: delegated task must have parent_task_id
            if task.parent_task_id is None:
                findings.append(
                    ErrorFinding(
                        category=self.category,
                        severity=ErrorSeverity.HIGH,
                        description=(
                            f"Delegated task '{task.id}' has no "
                            f"parent_task_id (broken delegation chain)"
                        ),
                        evidence=(
                            f"delegator={req.delegator_id}",
                            f"delegatee={req.delegatee_id}",
                            f"task_id={task.id}",
                        ),
                    ),
                )

            # Check: delegatee should not appear in delegation_chain
            # (indicates circular delegation)
            if req.delegatee_id in task.delegation_chain:
                findings.append(
                    ErrorFinding(
                        category=self.category,
                        severity=ErrorSeverity.HIGH,
                        description=(
                            f"Delegatee '{req.delegatee_id}' appears "
                            f"in delegation chain of task '{task.id}' "
                            f"(circular delegation)"
                        ),
                        evidence=(
                            f"delegation_chain={task.delegation_chain!r}",
                            f"delegatee={req.delegatee_id}",
                        ),
                    ),
                )

        result = tuple(findings)
        logger.debug(
            DETECTOR_COMPLETE,
            detector="delegation_protocol",
            finding_count=len(result),
        )
        return result


class ReviewPipelineProtocolDetector:
    """Validates review pipeline protocol consistency.

    Checks:
    - PASS verdict requires at least one stage result.
    - PASS verdict must not have any FAIL stages.
    """

    @property
    def category(self) -> ErrorCategory:
        """Error category this detector targets."""
        return ErrorCategory.REVIEW_PIPELINE_VIOLATION

    @property
    def supported_scopes(self) -> frozenset[DetectionScope]:
        """Detection scopes this detector can operate on."""
        return frozenset({DetectionScope.TASK_TREE})

    async def detect(
        self,
        context: DetectionContext,
    ) -> tuple[ErrorFinding, ...]:
        """Check review results for protocol violations.

        Args:
            context: Detection context with review data.

        Returns:
            Tuple of review violation findings.
        """
        logger.debug(
            DETECTOR_START,
            detector="review_pipeline_protocol",
            message_count=len(context.review_results),
        )
        findings: list[ErrorFinding] = []

        for review in context.review_results:
            # Check: PASS verdict with no stages is suspicious
            if review.final_verdict == ReviewVerdict.PASS and not review.stage_results:
                findings.append(
                    ErrorFinding(
                        category=self.category,
                        severity=ErrorSeverity.MEDIUM,
                        description=(
                            f"Task '{review.task_id}' passed review "
                            f"with no stage results (empty pipeline)"
                        ),
                        evidence=(
                            f"task_id={review.task_id}",
                            f"final_verdict={review.final_verdict.value}",
                            "stage_count=0",
                        ),
                    ),
                )

            # Check: PASS verdict contradicting a FAIL stage
            if review.final_verdict == ReviewVerdict.PASS:
                failed = [
                    s for s in review.stage_results if s.verdict == ReviewVerdict.FAIL
                ]
                if failed:
                    stage_names = ", ".join(s.stage_name for s in failed)
                    findings.append(
                        ErrorFinding(
                            category=self.category,
                            severity=ErrorSeverity.HIGH,
                            description=(
                                f"Task '{review.task_id}' passed review "
                                f"despite failed stages: {stage_names}"
                            ),
                            evidence=(
                                f"final_verdict={review.final_verdict.value}",
                                f"failed_stages={stage_names}",
                            ),
                        ),
                    )

        result = tuple(findings)
        logger.debug(
            DETECTOR_COMPLETE,
            detector="review_pipeline_protocol",
            finding_count=len(result),
        )
        return result


class AuthorityBreachDetector:
    """Detects execution cost exceeding authority budget limits.

    Compares total execution cost against the configured budget
    limit and flags when the limit is exceeded.

    Args:
        budget_limit: Maximum allowed cost in USD.  When ``None``,
            no budget check is performed.
    """

    def __init__(self, *, budget_limit: float | None = None) -> None:
        self._budget_limit = budget_limit

    @property
    def category(self) -> ErrorCategory:
        """Error category this detector targets."""
        return ErrorCategory.AUTHORITY_BREACH_ATTEMPT

    @property
    def supported_scopes(self) -> frozenset[DetectionScope]:
        """Detection scopes this detector can operate on."""
        return frozenset({DetectionScope.SAME_TASK})

    async def detect(
        self,
        context: DetectionContext,
    ) -> tuple[ErrorFinding, ...]:
        """Check execution for authority boundary violations.

        Args:
            context: Detection context with execution data.

        Returns:
            Tuple of authority breach findings.
        """
        logger.debug(
            DETECTOR_START,
            detector="authority_breach",
            message_count=len(
                context.execution_result.context.conversation,
            ),
        )
        findings: list[ErrorFinding] = []

        if self._budget_limit is not None:
            total_cost = sum(t.cost_usd for t in context.execution_result.turns)
            if total_cost > self._budget_limit:
                findings.append(
                    ErrorFinding(
                        category=self.category,
                        severity=ErrorSeverity.HIGH,
                        description=(
                            f"Execution cost ${total_cost:.4f} exceeds "
                            f"authority budget limit "
                            f"${self._budget_limit:.4f}"
                        ),
                        evidence=(
                            f"total_cost_usd={total_cost:.4f}",
                            f"budget_limit_usd={self._budget_limit:.4f}",
                            f"turn_count={len(context.execution_result.turns)}",
                        ),
                    ),
                )

        result = tuple(findings)
        logger.debug(
            DETECTOR_COMPLETE,
            detector="authority_breach",
            finding_count=len(result),
        )
        return result
