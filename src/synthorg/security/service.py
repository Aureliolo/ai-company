"""SecOps service -- the security meta-agent.

Coordinates the rule engine, audit log, output scanner, output scan
response policy, and approval store into a single
``SecurityInterceptionStrategy`` implementation that the
``ToolInvoker`` calls.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.approval import ApprovalItem
from synthorg.core.enums import ApprovalRiskLevel, ApprovalStatus, AutonomyLevel
from synthorg.observability import get_logger
from synthorg.observability.events.autonomy import (
    AUTONOMY_ACTION_AUTO_APPROVED,
    AUTONOMY_ACTION_HUMAN_REQUIRED,
)
from synthorg.observability.events.security import (
    SECURITY_AUDIT_RECORD_ERROR,
    SECURITY_DISABLED,
    SECURITY_ESCALATION_CREATED,
    SECURITY_ESCALATION_STORE_ERROR,
    SECURITY_EVALUATE_COMPLETE,
    SECURITY_EVALUATE_START,
    SECURITY_INTERCEPTOR_ERROR,
    SECURITY_LLM_EVAL_SKIPPED_FULL_AUTONOMY,
    SECURITY_SAFETY_CLASSIFY_BLOCKED,
    SECURITY_SAFETY_CLASSIFY_ERROR,
    SECURITY_SAFETY_CLASSIFY_SUSPICIOUS,
    SECURITY_SHADOW_WOULD_BLOCK,
    SECURITY_TIER_SAFE_TOOL,
    SECURITY_UNCERTAINTY_CHECK_ERROR,
    SECURITY_VERDICT_ALLOW,
    SECURITY_VERDICT_DENY,
    SECURITY_VERDICT_ESCALATE,
)
from synthorg.security.audit import AuditLog  # noqa: TC001
from synthorg.security.autonomy.models import EffectiveAutonomy  # noqa: TC001
from synthorg.security.config import (
    LlmFallbackErrorPolicy,
    SecurityConfig,
    SecurityEnforcementMode,
)
from synthorg.security.denial_tracker import (
    DenialAction,
    DenialTracker,
)
from synthorg.security.models import (
    OUTPUT_SCAN_VERDICT,
    AuditEntry,
    EvaluationConfidence,
    OutputScanResult,
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)
from synthorg.security.output_scan_policy import (
    OutputScanResponsePolicy,  # noqa: TC001
)
from synthorg.security.output_scan_policy_factory import (
    build_output_scan_policy,
)
from synthorg.security.output_scanner import OutputScanner  # noqa: TC001
from synthorg.security.rules.engine import RuleEngine  # noqa: TC001
from synthorg.security.safety_classifier import (
    PermissionTier,
    SafetyClassification,
)
from synthorg.security.timeout.protocol import RiskTierClassifier  # noqa: TC001

if TYPE_CHECKING:
    from synthorg.api.approval_store import ApprovalStore
    from synthorg.security.llm_evaluator import LlmSecurityEvaluator
    from synthorg.security.safety_classifier import SafetyClassifier
    from synthorg.security.uncertainty import UncertaintyChecker

logger = get_logger(__name__)


def _hash_arguments(arguments: dict[str, object]) -> str:
    """SHA-256 hex digest of serialized arguments (``default=str``)."""
    serialized = json.dumps(arguments, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


class SecOpsService:
    """Implements ``SecurityInterceptionStrategy``.

    Coordinates the rule engine, audit log, output scanner, output
    scan response policy, and optional approval store.  Enforces
    security policies, scans for sensitive data, and records audit
    entries.

    On ESCALATE: creates an ``ApprovalItem`` in the ``ApprovalStore``
    and returns the verdict with ``approval_id`` set.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        config: SecurityConfig,
        rule_engine: RuleEngine,
        audit_log: AuditLog,
        output_scanner: OutputScanner,
        approval_store: ApprovalStore | None = None,
        effective_autonomy: EffectiveAutonomy | None = None,
        risk_classifier: RiskTierClassifier | None = None,
        output_scan_policy: OutputScanResponsePolicy | None = None,
        llm_evaluator: LlmSecurityEvaluator | None = None,
        safety_classifier: SafetyClassifier | None = None,
        uncertainty_checker: UncertaintyChecker | None = None,
        denial_tracker: DenialTracker | None = None,
    ) -> None:
        """Initialize the SecOps service.

        Args:
            config: Security configuration.
            rule_engine: The synchronous rule engine.
            audit_log: Audit log for recording evaluations.
            output_scanner: Post-tool output scanner.
            approval_store: Optional store for escalation items.
            effective_autonomy: Resolved autonomy for the current
                run.  Autonomy can only tighten verdicts.
            risk_classifier: Risk level classifier for autonomy
                escalations.  Defaults to HIGH when absent.
            output_scan_policy: Output scan policy override.
            llm_evaluator: LLM fallback for uncertain verdicts.
            safety_classifier: Two-stage safety classifier for
                approval gates.
            uncertainty_checker: Cross-provider uncertainty checker.
            denial_tracker: Deny-and-continue retry tracker for
                BLOCKED classifications.
        """
        self._config = config
        self._rule_engine = rule_engine
        self._audit_log = audit_log
        self._output_scanner = output_scanner
        self._approval_store = approval_store
        self._effective_autonomy = effective_autonomy
        self._risk_classifier = risk_classifier
        self._llm_evaluator = llm_evaluator
        self._safety_classifier = safety_classifier
        self._uncertainty_checker = uncertainty_checker
        self._denial_tracker = denial_tracker
        self._output_scan_policy: OutputScanResponsePolicy = (
            output_scan_policy
            if output_scan_policy is not None
            else build_output_scan_policy(
                config.output_scan_policy_type,
                effective_autonomy=effective_autonomy,
            )
        )

        # Custom policy loading is logged by _build_rule_engine in
        # _security_factory.py (includes bypasses_detectors detail).

    async def evaluate_pre_tool(
        self,
        context: SecurityContext,
    ) -> SecurityVerdict:
        """Evaluate a tool invocation before execution.

        Steps:
            1. Check disabled/DISABLED enforcement mode.
            2. Run rule engine.
            3. LLM fallback for uncertain evaluations.
            4. Autonomy augmentation (tighten only).
            5. If ESCALATE, create approval item or convert to DENY.
            6. Record audit entry.
            7. Apply shadow mode conversion if applicable.
            8. Return verdict.
        """
        if (
            not self._config.enabled
            or self._config.enforcement_mode == SecurityEnforcementMode.DISABLED
        ):
            logger.warning(SECURITY_DISABLED, tool_name=context.tool_name)
            verdict = SecurityVerdict(
                verdict=SecurityVerdictType.ALLOW,
                reason="Security subsystem disabled",
                risk_level=ApprovalRiskLevel.LOW,
                evaluated_at=datetime.now(UTC),
                evaluation_duration_ms=0.0,
            )
            if self._config.audit_enabled:
                self._record_audit(context, verdict)
            return verdict

        logger.info(
            SECURITY_EVALUATE_START,
            tool_name=context.tool_name,
            action_type=context.action_type,
            agent_id=context.agent_id,
        )

        # Always run the rule engine first -- security detectors must
        # never be bypassed, regardless of autonomy configuration.
        try:
            verdict = self._rule_engine.evaluate(context)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_INTERCEPTOR_ERROR,
                tool_name=context.tool_name,
                note="Rule engine evaluation failed (fail-closed)",
            )
            verdict = SecurityVerdict(
                verdict=SecurityVerdictType.DENY,
                reason="Rule engine evaluation failed (fail-closed)",
                risk_level=ApprovalRiskLevel.CRITICAL,
                evaluated_at=datetime.now(UTC),
                evaluation_duration_ms=0.0,
            )

        # LLM fallback for uncertain evaluations (~5% of cases).
        verdict = await self._maybe_llm_fallback(context, verdict)

        # Apply autonomy augmentation *after* the rule engine (and
        # optional LLM fallback).  Autonomy can only add stricter
        # requirements (ALLOW -> ESCALATE), never weaken a DENY or
        # ESCALATE from security detectors.
        verdict = self._apply_autonomy_augmentation(context, verdict)

        # Handle escalation.
        if verdict.verdict == SecurityVerdictType.ESCALATE:
            verdict = await self._handle_escalation(context, verdict)

        # Record audit.
        if self._config.audit_enabled:
            self._record_audit(context, verdict)

        # Shadow mode: log blocking verdicts but return ALLOW.
        # Only replace non-ALLOW verdicts to preserve legitimate
        # ALLOW reasons in the audit trail.
        if (
            self._config.enforcement_mode == SecurityEnforcementMode.SHADOW
            and verdict.verdict != SecurityVerdictType.ALLOW
        ):
            logger.warning(
                SECURITY_SHADOW_WOULD_BLOCK,
                tool_name=context.tool_name,
                original_verdict=verdict.verdict.value,
                risk_level=verdict.risk_level.value,
                reason=verdict.reason,
            )
            verdict = SecurityVerdict(
                verdict=SecurityVerdictType.ALLOW,
                reason=f"Shadow mode (original: {verdict.verdict.value})",
                risk_level=verdict.risk_level,
                confidence=verdict.confidence,
                matched_rules=verdict.matched_rules,
                evaluated_at=verdict.evaluated_at,
                evaluation_duration_ms=verdict.evaluation_duration_ms,
            )

        # Log verdict.
        event = {
            SecurityVerdictType.ALLOW: SECURITY_VERDICT_ALLOW,
            SecurityVerdictType.DENY: SECURITY_VERDICT_DENY,
            SecurityVerdictType.ESCALATE: SECURITY_VERDICT_ESCALATE,
        }.get(verdict.verdict, SECURITY_EVALUATE_COMPLETE)
        logger.info(
            event,
            tool_name=context.tool_name,
            verdict=verdict.verdict.value,
            risk_level=verdict.risk_level.value,
        )

        return verdict

    async def scan_output(
        self,
        context: SecurityContext,
        output: str,
    ) -> OutputScanResult:
        """Scan tool output for sensitive data.

        Steps:
            1. Delegate to the output scanner.
            2. Record an audit entry if sensitive data is found.
            3. Apply the output scan response policy to transform
               the result before returning.
        """
        if not self._config.post_tool_scanning_enabled:
            logger.debug(
                SECURITY_EVALUATE_COMPLETE,
                note="output scanning disabled",
                tool_name=context.tool_name,
            )
            return OutputScanResult()

        result = self._output_scanner.scan(output)

        if result.has_sensitive_data and self._config.audit_enabled:
            entry = AuditEntry(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC),
                agent_id=context.agent_id,
                task_id=context.task_id,
                tool_name=context.tool_name,
                tool_category=context.tool_category,
                action_type=context.action_type,
                arguments_hash=_hash_arguments(context.arguments),
                verdict=OUTPUT_SCAN_VERDICT,
                risk_level=ApprovalRiskLevel.HIGH,
                reason=("Sensitive data in output: " + ", ".join(result.findings)),
                evaluation_duration_ms=0.0,
            )
            try:
                self._audit_log.record(entry)
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(
                    SECURITY_AUDIT_RECORD_ERROR,
                    tool_name=context.tool_name,
                    note="Output scan audit recording failed",
                )

        # Apply the output scan response policy.  On failure, fall back
        # to the raw scan result which already has scanner-level redaction
        # applied (pattern matches replaced with [REDACTED]), so the
        # fallback is still reasonably safe even if the intended policy
        # (e.g. WithholdPolicy) would have been stricter.
        policy_name = getattr(self._output_scan_policy, "name", "<unknown>")
        try:
            result = self._output_scan_policy.apply(result, context)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_INTERCEPTOR_ERROR,
                tool_name=context.tool_name,
                policy=policy_name,
                fallback_outcome=result.outcome.value,
                note="Output scan policy application failed "
                "-- returning raw scan result "
                "(may be less strict than intended policy)",
            )

        return result

    async def _maybe_llm_fallback(  # noqa: PLR0911
        self,
        context: SecurityContext,
        verdict: SecurityVerdict,
    ) -> SecurityVerdict:
        """Run LLM fallback if the verdict is uncertain.

        Triggers when confidence is LOW, LLM fallback is enabled, an
        evaluator is injected, and autonomy is not FULL.  Full-autonomy
        mode skips LLM evaluation (rules + audit only, per spec D4).

        Returns the (possibly re-evaluated) verdict.
        """
        if verdict.confidence != EvaluationConfidence.LOW:
            return verdict
        # Safety net: never re-evaluate non-ALLOW verdicts through LLM,
        # regardless of confidence (defensive against buggy custom rules
        # that might return DENY/ESCALATE with LOW confidence).
        if verdict.verdict != SecurityVerdictType.ALLOW:
            return verdict
        if not self._config.llm_fallback.enabled:
            return verdict
        if self._llm_evaluator is None:
            return verdict

        # Full autonomy: rules + audit only, no LLM path.
        if (
            self._effective_autonomy is not None
            and self._effective_autonomy.level == AutonomyLevel.FULL
        ):
            logger.debug(
                SECURITY_LLM_EVAL_SKIPPED_FULL_AUTONOMY,
                tool_name=context.tool_name,
                action_type=context.action_type,
            )
            return verdict

        try:
            return await self._llm_evaluator.evaluate(context, verdict)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_INTERCEPTOR_ERROR,
                tool_name=context.tool_name,
                note="LLM security evaluation failed (applying error policy)",
            )
            # Respect the configured error policy rather than
            # unconditionally returning the rule verdict.
            policy = self._config.llm_fallback.on_error
            if policy == LlmFallbackErrorPolicy.DENY:
                return verdict.model_copy(
                    update={
                        "verdict": SecurityVerdictType.DENY,
                        "reason": (
                            f"{verdict.reason} "
                            "(LLM evaluator error -- denied per policy)"
                        ),
                        "risk_level": ApprovalRiskLevel.HIGH,
                    },
                )
            if policy == LlmFallbackErrorPolicy.ESCALATE:
                return verdict.model_copy(
                    update={
                        "verdict": SecurityVerdictType.ESCALATE,
                        "reason": (
                            f"{verdict.reason} "
                            "(LLM evaluator error -- escalated per policy)"
                        ),
                        "risk_level": ApprovalRiskLevel.HIGH,
                    },
                )
            return verdict

    def _apply_autonomy_augmentation(
        self,
        context: SecurityContext,
        verdict: SecurityVerdict,
    ) -> SecurityVerdict:
        """Augment the rule engine verdict with autonomy routing.

        Autonomy can only *tighten* a verdict (ALLOW → ESCALATE), never
        weaken one.  DENY and ESCALATE from the rule engine are always
        preserved -- security detectors take precedence over autonomy.

        Returns the (possibly upgraded) verdict.
        """
        if self._effective_autonomy is None:
            return verdict

        # Security DENY/ESCALATE always takes precedence.
        if verdict.verdict != SecurityVerdictType.ALLOW:
            return verdict

        action = context.action_type
        autonomy = self._effective_autonomy

        if action in autonomy.auto_approve_actions:
            logger.info(
                AUTONOMY_ACTION_AUTO_APPROVED,
                tool_name=context.tool_name,
                action_type=action,
                autonomy_level=autonomy.level.value,
            )
            return verdict

        if action in autonomy.human_approval_actions:
            risk_level = (
                self._risk_classifier.classify(action)
                if self._risk_classifier
                else ApprovalRiskLevel.HIGH
            )
            logger.info(
                AUTONOMY_ACTION_HUMAN_REQUIRED,
                tool_name=context.tool_name,
                action_type=action,
                autonomy_level=autonomy.level.value,
                risk_level=risk_level.value,
            )
            return verdict.model_copy(
                update={
                    "verdict": SecurityVerdictType.ESCALATE,
                    "reason": (
                        f"Human approval required by autonomy level "
                        f"'{autonomy.level.value}'"
                    ),
                    "risk_level": risk_level,
                },
            )

        # Not classified by autonomy -- keep rule engine's verdict.
        return verdict

    def _record_audit(
        self,
        context: SecurityContext,
        verdict: SecurityVerdict,
    ) -> None:
        """Record an audit entry for a pre-tool evaluation.

        Model construction errors propagate (they indicate programming
        bugs).  Storage errors are caught and logged -- they must never
        prevent the verdict from being returned.
        """
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            timestamp=verdict.evaluated_at,
            agent_id=context.agent_id,
            task_id=context.task_id,
            tool_name=context.tool_name,
            tool_category=context.tool_category,
            action_type=context.action_type,
            arguments_hash=_hash_arguments(context.arguments),
            verdict=verdict.verdict.value,
            risk_level=verdict.risk_level,
            reason=verdict.reason,
            matched_rules=verdict.matched_rules,
            evaluation_duration_ms=verdict.evaluation_duration_ms,
            confidence=verdict.confidence,
            approval_id=verdict.approval_id,
        )
        try:
            self._audit_log.record(entry)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_AUDIT_RECORD_ERROR,
                tool_name=context.tool_name,
                note="Audit recording failed -- verdict still returned",
            )

    async def _handle_escalation(
        self,
        context: SecurityContext,
        verdict: SecurityVerdict,
    ) -> SecurityVerdict:
        """Create an approval item in the approval store.

        When a safety classifier is configured, the action is
        classified before creating the approval item.  BLOCKED
        actions are auto-rejected (returned as DENY).  SUSPICIOUS
        actions get a warning badge via metadata.  When an
        uncertainty checker is configured, a cross-provider
        confidence score is attached.

        Falls back to DENY if no approval store is configured or if
        the store raises an exception.
        """
        if self._approval_store is None:
            logger.warning(
                SECURITY_VERDICT_DENY,
                tool_name=context.tool_name,
                original_verdict="escalate",
                note="no approval store -- converting to DENY",
            )
            return verdict.model_copy(
                update={
                    "verdict": SecurityVerdictType.DENY,
                    "reason": (f"{verdict.reason} (escalation unavailable -- denied)"),
                },
            )

        approval_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        description = verdict.reason
        metadata: dict[str, str] = {
            "tool_name": context.tool_name,
            "tool_category": context.tool_category.value,
        }

        # Stage 1+2: safety classification (if configured).
        if self._safety_classifier is not None:
            auto_rejected = await self._run_safety_classifier(
                context,
                verdict,
                metadata,
            )
            if auto_rejected:
                deny_reason = self._build_deny_reason(
                    verdict.reason,
                    metadata,
                )
                return verdict.model_copy(
                    update={
                        "verdict": SecurityVerdictType.DENY,
                        "reason": deny_reason,
                    },
                )
            # Use stripped description for the reviewer view.
            stripped = metadata.get("stripped_description")
            if stripped:
                description = stripped

        # Cross-provider uncertainty check (if configured).
        # Use stripped description when available to avoid
        # broadcasting raw PII/secrets to all providers.
        if self._uncertainty_checker is not None:
            check_text = metadata.get(
                "stripped_description",
                verdict.reason,
            )
            await self._run_uncertainty_check(
                check_text,
                metadata,
            )

        item = ApprovalItem(
            id=approval_id,
            action_type=context.action_type,
            title=f"Security escalation: {context.tool_name}",
            description=description,
            requested_by=context.agent_id or "system",
            risk_level=verdict.risk_level,
            status=ApprovalStatus.PENDING,
            created_at=now,
            task_id=context.task_id,
            metadata=metadata,
        )
        try:
            await self._approval_store.add(item)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_ESCALATION_STORE_ERROR,
                approval_id=approval_id,
                tool_name=context.tool_name,
                agent_id=context.agent_id,
            )
            return verdict.model_copy(
                update={
                    "verdict": SecurityVerdictType.DENY,
                    "reason": (f"{verdict.reason} (escalation store error -- denied)"),
                },
            )
        logger.info(
            SECURITY_ESCALATION_CREATED,
            approval_id=approval_id,
            tool_name=context.tool_name,
            agent_id=context.agent_id,
        )
        return verdict.model_copy(
            update={"approval_id": approval_id},
        )

    @staticmethod
    def _build_deny_reason(
        base_reason: str,
        metadata: dict[str, str],
    ) -> str:
        """Build DENY reason -- retry hint when tracker signals RETRY."""
        if metadata.get("denial_action") == DenialAction.RETRY:
            return f"{base_reason} (blocked -- agent may retry with safer approach)"
        return f"{base_reason} (auto-rejected: safety classifier blocked)"

    async def _run_safety_classifier(
        self,
        context: SecurityContext,
        verdict: SecurityVerdict,
        metadata: dict[str, str],
    ) -> bool:
        """Run the safety classifier and populate metadata.

        Returns ``True`` if the action should be auto-rejected,
        ``False`` otherwise.  SAFE_TOOL tier bypasses the classifier.
        On error, returns ``False`` (fail-safe: proceed to review).
        """
        assert self._safety_classifier is not None  # noqa: S101 -- caller guarantees

        # Permission tier: SAFE_TOOL bypasses the classifier.
        tier = self._safety_classifier.classify_tier(context.action_type)
        if tier == PermissionTier.SAFE_TOOL:
            logger.info(
                SECURITY_TIER_SAFE_TOOL,
                tool_name=context.tool_name,
                action_type=context.action_type,
            )
            return False

        try:
            result = await self._safety_classifier.classify(
                verdict.reason,
                context.action_type,
                context.tool_name,
                verdict.risk_level,
            )
            metadata["safety_classification"] = result.classification.value
            metadata["stripped_description"] = result.stripped_description
            metadata["safety_reason"] = result.reason

            return self._process_classification(
                result.classification,
                context,
                result.reason,
                metadata,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_SAFETY_CLASSIFY_ERROR,
                tool_name=context.tool_name,
                note="Safety classifier failed -- proceeding without classification",
            )
        return False

    def _process_classification(
        self,
        classification: SafetyClassification,
        context: SecurityContext,
        reason: str,
        metadata: dict[str, str],
    ) -> bool:
        """Process classification: denial tracking + consecutive reset."""
        agent_id = context.agent_id or "unknown"

        if (
            classification == SafetyClassification.BLOCKED
            and self._config.safety_classifier.auto_reject_blocked
        ):
            return self._handle_blocked_denial(
                agent_id,
                context.tool_name,
                reason,
                metadata,
            )

        # SAFE or SUSPICIOUS: reset consecutive denial count.
        if self._denial_tracker is not None:
            self._denial_tracker.reset_consecutive(agent_id)

        if classification == SafetyClassification.SUSPICIOUS:
            logger.warning(
                SECURITY_SAFETY_CLASSIFY_SUSPICIOUS,
                tool_name=context.tool_name,
                reason=reason,
            )
        return False

    def _handle_blocked_denial(
        self,
        agent_id: str,
        tool_name: str,
        reason: str,
        metadata: dict[str, str],
    ) -> bool:
        """Handle BLOCKED with denial tracking.  Always returns True."""
        if self._denial_tracker is None:
            logger.warning(
                SECURITY_SAFETY_CLASSIFY_BLOCKED,
                tool_name=tool_name,
                reason=reason,
            )
            return True

        action = self._denial_tracker.record_denial(agent_id)
        metadata["denial_action"] = action.value
        consecutive, total = self._denial_tracker.get_counts(agent_id)
        metadata["denial_consecutive"] = str(consecutive)
        metadata["denial_total"] = str(total)

        if action == DenialAction.ESCALATE:
            logger.warning(
                SECURITY_SAFETY_CLASSIFY_BLOCKED,
                tool_name=tool_name,
                reason=reason,
                note="max denials reached -- escalating",
                consecutive=consecutive,
                total=total,
            )
            return True

        # RETRY: agent may retry with safer approach.
        logger.warning(
            SECURITY_SAFETY_CLASSIFY_BLOCKED,
            tool_name=tool_name,
            reason=f"{reason} -- agent may retry with safer approach",
            consecutive=consecutive,
            total=total,
        )
        return True

    async def _run_uncertainty_check(
        self,
        prompt: str,
        metadata: dict[str, str],
    ) -> None:
        """Run the uncertainty checker and populate metadata."""
        assert self._uncertainty_checker is not None  # noqa: S101 -- caller guarantees
        try:
            result = await self._uncertainty_checker.check(
                prompt,
            )
            metadata["confidence_score"] = str(result.confidence_score)
            threshold = self._config.uncertainty_check.low_confidence_threshold
            if result.confidence_score < threshold:
                metadata["low_confidence"] = "true"
            if result.keyword_overlap is not None:
                metadata["keyword_overlap"] = str(result.keyword_overlap)
            if result.embedding_similarity is not None:
                metadata["embedding_similarity"] = str(
                    result.embedding_similarity,
                )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_UNCERTAINTY_CHECK_ERROR,
                note="Uncertainty check failed -- proceeding without score",
            )
            metadata["uncertainty_check_error"] = "true"
