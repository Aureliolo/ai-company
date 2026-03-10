"""Rule engine — evaluates security rules in order."""

import time
from datetime import UTC, datetime

from ai_company.observability import get_logger
from ai_company.observability.events.security import (
    SECURITY_EVALUATE_COMPLETE,
    SECURITY_EVALUATE_START,
    SECURITY_RULE_MATCHED,
    SECURITY_VERDICT_ALLOW,
)
from ai_company.security.config import RuleEngineConfig  # noqa: TC001
from ai_company.security.models import (
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)
from ai_company.security.rules.protocol import SecurityRule  # noqa: TC001
from ai_company.security.rules.risk_classifier import RiskClassifier  # noqa: TC001

logger = get_logger(__name__)


class RuleEngine:
    """Evaluates security rules in a defined order.

    Rules are run sequentially.  The first DENY or ESCALATE verdict
    wins.  If no rule triggers, the engine returns ALLOW with a risk
    level from the ``RiskClassifier``.

    Evaluation order:
        1. Policy validator (fast path: hard deny / auto approve)
        2. Credential detector
        3. Path traversal detector
        4. Destructive operation detector
        5. Data leak detector

    All rules are synchronous — the engine itself is synchronous.
    """

    def __init__(
        self,
        *,
        rules: tuple[SecurityRule, ...],
        risk_classifier: RiskClassifier,
        config: RuleEngineConfig,
    ) -> None:
        """Initialize the rule engine.

        Args:
            rules: Ordered tuple of rules to evaluate.
            risk_classifier: Fallback risk classifier.
            config: Rule engine configuration.
        """
        self._rules = rules
        self._risk_classifier = risk_classifier
        self._config = config

    def evaluate(self, context: SecurityContext) -> SecurityVerdict:
        """Run all rules in order, returning the final verdict.

        Args:
            context: The tool invocation security context.

        Returns:
            A ``SecurityVerdict`` — DENY/ESCALATE from the first
            matching rule, or ALLOW with risk from the classifier.
        """
        logger.debug(
            SECURITY_EVALUATE_START,
            tool_name=context.tool_name,
            action_type=context.action_type,
        )
        start = time.monotonic()

        for rule in self._rules:
            verdict = rule.evaluate(context)
            if verdict is not None:
                duration_ms = (time.monotonic() - start) * 1000
                logger.debug(
                    SECURITY_RULE_MATCHED,
                    rule_name=rule.name,
                    verdict=verdict.verdict,
                    tool_name=context.tool_name,
                )
                return verdict.model_copy(
                    update={"evaluation_duration_ms": duration_ms},
                )

        # No rule triggered — ALLOW with risk from classifier.
        duration_ms = (time.monotonic() - start) * 1000
        risk = self._risk_classifier.classify(context.action_type)
        logger.debug(
            SECURITY_VERDICT_ALLOW,
            tool_name=context.tool_name,
            risk_level=risk.value,
        )
        logger.debug(
            SECURITY_EVALUATE_COMPLETE,
            tool_name=context.tool_name,
            duration_ms=duration_ms,
        )
        return SecurityVerdict(
            verdict=SecurityVerdictType.ALLOW,
            reason="No security rule triggered",
            risk_level=risk,
            evaluated_at=datetime.now(UTC),
            evaluation_duration_ms=duration_ms,
        )
