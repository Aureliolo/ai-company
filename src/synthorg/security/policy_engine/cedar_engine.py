"""Cedar policy engine adapter using ``cedarpy``."""

import time

import cedarpy

from synthorg.observability import get_logger
from synthorg.observability.events.security import (
    SECURITY_POLICY_DECISION_ALLOW,
    SECURITY_POLICY_DECISION_DENY,
    SECURITY_POLICY_ENGINE_ERROR,
    SECURITY_POLICY_EVALUATE_START,
)
from synthorg.security.policy_engine.models import (
    PolicyActionRequest,
    PolicyDecision,
)

logger = get_logger(__name__)


class CedarPolicyEngine:
    """Cedar-based runtime policy evaluator.

    Uses ``cedarpy.is_authorized()`` for stateless embedded policy
    evaluation.  Policies are loaded at construction time from text
    strings.

    Args:
        policy_texts: Cedar policy source strings.
        schema_text: Optional Cedar schema JSON string.
        fail_closed: If ``True``, return deny on evaluation errors.
    """

    def __init__(
        self,
        policy_texts: tuple[str, ...],
        *,
        schema_text: str | None = None,
        fail_closed: bool = False,
    ) -> None:
        self._policies = "\n".join(policy_texts)
        self._schema = schema_text
        self._fail_closed = fail_closed

    @property
    def name(self) -> str:
        """Engine identifier."""
        return "cedar"

    async def evaluate(
        self,
        request: PolicyActionRequest,
    ) -> PolicyDecision:
        """Evaluate a policy action request using Cedar.

        Args:
            request: The action to evaluate.

        Returns:
            Allow/deny decision with reason and timing.
        """
        logger.debug(
            SECURITY_POLICY_EVALUATE_START,
            action_type=request.action_type,
            principal=request.principal,
            resource=request.resource,
        )

        cedar_request = {
            "principal": f'Principal::"{request.principal}"',
            "action": f'Action::"{request.action_type}"',
            "resource": f'Resource::"{request.resource}"',
            "context": dict(request.context),
        }

        start = time.perf_counter()
        try:
            result = cedarpy.is_authorized(
                cedar_request,
                self._policies,
                [],
            )
            latency_ms = (time.perf_counter() - start) * 1000

            allowed = result.decision == cedarpy.Decision.Allow
            reason = (
                "Cedar policy permits action"
                if allowed
                else "Cedar policy denies action"
            )

            event = (
                SECURITY_POLICY_DECISION_ALLOW
                if allowed
                else SECURITY_POLICY_DECISION_DENY
            )
            logger.info(
                event,
                action_type=request.action_type,
                principal=request.principal,
                resource=request.resource,
                allowed=allowed,
                latency_ms=latency_ms,
            )

            return PolicyDecision(
                allow=allowed,
                reason=reason,
                matched_policy="cedar_policy_set",
                latency_ms=latency_ms,
            )

        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(
                SECURITY_POLICY_ENGINE_ERROR,
                error=str(exc),
                action_type=request.action_type,
                principal=request.principal,
                resource=request.resource,
                fail_closed=self._fail_closed,
                exc_info=True,
            )

            if self._fail_closed:
                return PolicyDecision(
                    allow=False,
                    reason=f"Policy evaluation error (fail-closed): {exc}",
                    latency_ms=latency_ms,
                )
            return PolicyDecision(
                allow=True,
                reason=f"Policy evaluation error (fail-open): {exc}",
                latency_ms=latency_ms,
            )
