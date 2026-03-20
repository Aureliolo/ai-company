"""Integration tests for SecOpsService with LLM fallback."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.enums import (
    ApprovalRiskLevel,
    AutonomyLevel,
    ToolCategory,
)
from synthorg.security.audit import AuditLog
from synthorg.security.autonomy.models import EffectiveAutonomy
from synthorg.security.config import LlmFallbackConfig, SecurityConfig
from synthorg.security.llm_evaluator import LlmSecurityEvaluator
from synthorg.security.models import (
    EvaluationConfidence,
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)
from synthorg.security.output_scanner import OutputScanner
from synthorg.security.rules.engine import RuleEngine
from synthorg.security.service import SecOpsService

pytestmark = pytest.mark.timeout(30)


# -- Helpers ---------------------------------------------------------------


def _make_context(
    *,
    action_type: str = "code:write",
    agent_provider_name: str | None = "provider-a",
) -> SecurityContext:
    return SecurityContext(
        tool_name="test-tool",
        tool_category=ToolCategory.FILE_SYSTEM,
        action_type=action_type,
        arguments={"path": "/workspace/test.py"},
        agent_id="agent-1",
        task_id="task-1",
        agent_provider_name=agent_provider_name,
    )


def _make_verdict(
    *,
    verdict: SecurityVerdictType = SecurityVerdictType.ALLOW,
    confidence: EvaluationConfidence = EvaluationConfidence.LOW,
    risk: ApprovalRiskLevel = ApprovalRiskLevel.MEDIUM,
    reason: str = "No security rule triggered",
) -> SecurityVerdict:
    return SecurityVerdict(
        verdict=verdict,
        reason=reason,
        risk_level=risk,
        confidence=confidence,
        evaluated_at=datetime.now(UTC),
        evaluation_duration_ms=0.5,
    )


def _make_llm_verdict(
    *,
    verdict: SecurityVerdictType = SecurityVerdictType.ALLOW,
    risk: ApprovalRiskLevel = ApprovalRiskLevel.LOW,
    reason: str = "LLM evaluation: action is safe",
) -> SecurityVerdict:
    return SecurityVerdict(
        verdict=verdict,
        reason=reason,
        risk_level=risk,
        confidence=EvaluationConfidence.HIGH,
        matched_rules=("llm_security_eval",),
        evaluated_at=datetime.now(UTC),
        evaluation_duration_ms=50.0,
    )


def _make_service(
    *,
    rule_engine_verdict: SecurityVerdict | None = None,
    llm_evaluator: LlmSecurityEvaluator | None = None,
    effective_autonomy: EffectiveAutonomy | None = None,
    config: SecurityConfig | None = None,
) -> SecOpsService:
    rule_engine = MagicMock(spec=RuleEngine)
    rule_engine.evaluate = MagicMock(
        return_value=rule_engine_verdict
        or _make_verdict(confidence=EvaluationConfidence.LOW),
    )

    return SecOpsService(
        config=config
        or SecurityConfig(
            llm_fallback=LlmFallbackConfig(enabled=True),
        ),
        rule_engine=rule_engine,
        audit_log=AuditLog(),
        output_scanner=OutputScanner(),
        llm_evaluator=llm_evaluator,
        effective_autonomy=effective_autonomy,
    )


# -- LLM fallback triggering ----------------------------------------------


@pytest.mark.unit
async def test_low_confidence_triggers_llm_fallback() -> None:
    """LOW confidence verdict should trigger LLM evaluation."""
    llm_eval = AsyncMock()
    llm_eval.evaluate = AsyncMock(return_value=_make_llm_verdict())

    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.LOW),
        llm_evaluator=llm_eval,
    )
    context = _make_context()

    result = await service.evaluate_pre_tool(context)

    llm_eval.evaluate.assert_awaited_once()
    assert result.confidence == EvaluationConfidence.HIGH


@pytest.mark.unit
async def test_high_confidence_skips_llm_fallback() -> None:
    """HIGH confidence verdict should NOT trigger LLM evaluation."""
    llm_eval = AsyncMock()

    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.HIGH),
        llm_evaluator=llm_eval,
    )
    context = _make_context()

    await service.evaluate_pre_tool(context)

    llm_eval.evaluate.assert_not_awaited()


@pytest.mark.unit
async def test_full_autonomy_skips_llm_fallback() -> None:
    """FULL autonomy mode skips LLM evaluation entirely."""
    llm_eval = AsyncMock()

    full_autonomy = EffectiveAutonomy(
        level=AutonomyLevel.FULL,
        auto_approve_actions=frozenset({"code:write"}),
        human_approval_actions=frozenset(),
        security_agent=False,
    )
    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.LOW),
        llm_evaluator=llm_eval,
        effective_autonomy=full_autonomy,
    )
    context = _make_context()

    await service.evaluate_pre_tool(context)

    llm_eval.evaluate.assert_not_awaited()


@pytest.mark.unit
async def test_llm_fallback_disabled_skips_evaluation() -> None:
    """Disabled LLM fallback should not trigger even on LOW confidence."""
    llm_eval = AsyncMock()

    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.LOW),
        llm_evaluator=llm_eval,
        config=SecurityConfig(llm_fallback=LlmFallbackConfig(enabled=False)),
    )
    context = _make_context()

    await service.evaluate_pre_tool(context)

    llm_eval.evaluate.assert_not_awaited()


@pytest.mark.unit
async def test_no_llm_evaluator_skips_fallback() -> None:
    """When no LLM evaluator is injected, LOW confidence proceeds as-is."""
    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.LOW),
        llm_evaluator=None,
    )
    context = _make_context()

    result = await service.evaluate_pre_tool(context)

    assert result.confidence == EvaluationConfidence.LOW
    assert result.verdict == SecurityVerdictType.ALLOW


# -- Hard deny invariant ---------------------------------------------------


@pytest.mark.unit
async def test_hard_deny_never_reaches_llm() -> None:
    """DENY from rule engine has HIGH confidence, so LLM is never called."""
    llm_eval = AsyncMock()

    service = _make_service(
        rule_engine_verdict=_make_verdict(
            verdict=SecurityVerdictType.DENY,
            confidence=EvaluationConfidence.HIGH,
            risk=ApprovalRiskLevel.CRITICAL,
            reason="Hard deny: credential exposure",
        ),
        llm_evaluator=llm_eval,
    )
    context = _make_context()

    result = await service.evaluate_pre_tool(context)

    llm_eval.evaluate.assert_not_awaited()
    assert result.verdict == SecurityVerdictType.DENY


# -- LLM verdict integration ----------------------------------------------


@pytest.mark.unit
async def test_llm_deny_overrides_rule_allow() -> None:
    """LLM DENY should override the rule engine's ALLOW."""
    llm_eval = AsyncMock()
    llm_eval.evaluate = AsyncMock(
        return_value=_make_llm_verdict(
            verdict=SecurityVerdictType.DENY,
            risk=ApprovalRiskLevel.HIGH,
            reason="LLM: suspicious pattern detected",
        ),
    )

    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.LOW),
        llm_evaluator=llm_eval,
    )
    context = _make_context()

    result = await service.evaluate_pre_tool(context)

    assert result.verdict == SecurityVerdictType.DENY
    assert result.risk_level == ApprovalRiskLevel.HIGH


@pytest.mark.unit
async def test_llm_escalate_result_handled() -> None:
    """LLM ESCALATE should flow through to the escalation handler."""
    llm_eval = AsyncMock()
    llm_eval.evaluate = AsyncMock(
        return_value=_make_llm_verdict(
            verdict=SecurityVerdictType.ESCALATE,
            risk=ApprovalRiskLevel.HIGH,
            reason="LLM: needs human review",
        ),
    )

    # No approval store -> ESCALATE converts to DENY.
    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.LOW),
        llm_evaluator=llm_eval,
    )
    context = _make_context()

    result = await service.evaluate_pre_tool(context)

    # Without approval store, ESCALATE becomes DENY.
    assert result.verdict == SecurityVerdictType.DENY


# -- LLM error handling ---------------------------------------------------


@pytest.mark.unit
async def test_llm_error_with_use_rule_verdict_policy() -> None:
    """On LLM error with USE_RULE_VERDICT, original verdict is used."""
    llm_eval = AsyncMock()
    llm_eval.evaluate = AsyncMock(
        return_value=_make_verdict(
            confidence=EvaluationConfidence.LOW,
            reason="LLM evaluation failed -- using rule verdict",
        ),
    )

    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.LOW),
        llm_evaluator=llm_eval,
    )
    context = _make_context()

    result = await service.evaluate_pre_tool(context)

    assert result.verdict == SecurityVerdictType.ALLOW


# -- Autonomy augmentation after LLM --------------------------------------


@pytest.mark.unit
async def test_autonomy_augmentation_still_applies_after_llm() -> None:
    """Autonomy can still escalate ALLOW -> ESCALATE after LLM says allow."""
    llm_eval = AsyncMock()
    llm_eval.evaluate = AsyncMock(return_value=_make_llm_verdict())

    supervised = EffectiveAutonomy(
        level=AutonomyLevel.SUPERVISED,
        auto_approve_actions=frozenset({"code:read"}),
        human_approval_actions=frozenset({"code:write"}),
        security_agent=True,
    )
    service = _make_service(
        rule_engine_verdict=_make_verdict(confidence=EvaluationConfidence.LOW),
        llm_evaluator=llm_eval,
        effective_autonomy=supervised,
    )
    context = _make_context(action_type="code:write")

    result = await service.evaluate_pre_tool(context)

    # LLM allowed it, but autonomy escalates code:write.
    # Without approval store, ESCALATE -> DENY.
    assert result.verdict in (
        SecurityVerdictType.ESCALATE,
        SecurityVerdictType.DENY,
    )


# -- Audit recording ------------------------------------------------------


@pytest.mark.unit
async def test_audit_records_llm_evaluation_source() -> None:
    """Audit entry should reflect the LLM-evaluated verdict."""
    llm_eval = AsyncMock()
    llm_eval.evaluate = AsyncMock(
        return_value=_make_llm_verdict(
            verdict=SecurityVerdictType.DENY,
            reason="LLM: denied for safety",
        ),
    )
    audit_log = AuditLog()

    service = SecOpsService(
        config=SecurityConfig(llm_fallback=LlmFallbackConfig(enabled=True)),
        rule_engine=MagicMock(
            spec=RuleEngine,
            evaluate=MagicMock(
                return_value=_make_verdict(confidence=EvaluationConfidence.LOW),
            ),
        ),
        audit_log=audit_log,
        output_scanner=OutputScanner(),
        llm_evaluator=llm_eval,
    )
    context = _make_context()

    await service.evaluate_pre_tool(context)

    entries = audit_log.query(limit=1)
    assert len(entries) == 1
    assert entries[0].verdict == "deny"
    assert "LLM" in entries[0].reason
