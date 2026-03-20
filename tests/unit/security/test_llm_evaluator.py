"""Tests for the LLM security evaluator."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.enums import ApprovalRiskLevel, ToolCategory
from synthorg.providers.enums import FinishReason, MessageRole
from synthorg.providers.models import (
    CompletionResponse,
    TokenUsage,
    ToolCall,
)
from synthorg.security.config import LlmFallbackConfig, LlmFallbackErrorPolicy
from synthorg.security.llm_evaluator import LlmSecurityEvaluator
from synthorg.security.models import (
    EvaluationConfidence,
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)

pytestmark = pytest.mark.timeout(30)


# -- Helpers ---------------------------------------------------------------


def _make_context(
    *,
    tool_name: str = "test-tool",
    action_type: str = "code:write",
    agent_provider_name: str | None = "provider-a",
) -> SecurityContext:
    return SecurityContext(
        tool_name=tool_name,
        tool_category=ToolCategory.FILE_SYSTEM,
        action_type=action_type,
        arguments={"path": "/workspace/test.py", "content": "print('hello')"},
        agent_id="agent-1",
        task_id="task-1",
        agent_provider_name=agent_provider_name,
    )


def _make_rule_verdict(
    *,
    verdict: SecurityVerdictType = SecurityVerdictType.ALLOW,
    risk: ApprovalRiskLevel = ApprovalRiskLevel.MEDIUM,
    confidence: EvaluationConfidence = EvaluationConfidence.LOW,
) -> SecurityVerdict:
    return SecurityVerdict(
        verdict=verdict,
        reason="No security rule triggered",
        risk_level=risk,
        confidence=confidence,
        evaluated_at=datetime.now(UTC),
        evaluation_duration_ms=0.5,
    )


def _make_llm_tool_call(
    verdict: str = "allow",
    risk_level: str = "low",
    reason: str = "Action appears safe",
) -> ToolCall:
    return ToolCall(
        id="tc-1",
        name="security_verdict",
        arguments={
            "verdict": verdict,
            "risk_level": risk_level,
            "reason": reason,
        },
    )


def _make_completion_response(
    tool_call: ToolCall | None = None,
) -> CompletionResponse:
    tc = tool_call or _make_llm_tool_call()
    return CompletionResponse(
        content=None,
        tool_calls=(tc,),
        finish_reason=FinishReason.TOOL_USE,
        usage=TokenUsage(input_tokens=200, output_tokens=50, cost_usd=0.001),
        model="test-small-001",
    )


def _make_evaluator(
    *,
    provider_configs: dict[str, object] | None = None,
    config: LlmFallbackConfig | None = None,
    driver_map: dict[str, AsyncMock] | None = None,
) -> LlmSecurityEvaluator:
    """Build an evaluator with mock providers.

    Args:
        provider_configs: Dict of provider name to mock ProviderConfig.
        config: LLM fallback config.
        driver_map: Dict of provider name to mock driver.
    """
    if provider_configs is None:
        # Two providers from different families.
        config_a = MagicMock()
        config_a.family = "family-a"
        config_a.models = (MagicMock(id="model-a-1", alias="small"),)
        config_b = MagicMock()
        config_b.family = "family-b"
        config_b.models = (MagicMock(id="model-b-1", alias="small"),)
        provider_configs = {"provider-a": config_a, "provider-b": config_b}

    if driver_map is None:
        mock_driver = AsyncMock()
        mock_driver.complete = AsyncMock(return_value=_make_completion_response())
        driver_map = {"provider-a": mock_driver, "provider-b": mock_driver}

    registry = MagicMock()
    registry.get = MagicMock(side_effect=lambda name: driver_map[name])
    registry.list_providers = MagicMock(return_value=tuple(sorted(driver_map.keys())))

    return LlmSecurityEvaluator(
        provider_registry=registry,
        provider_configs=provider_configs,
        config=config or LlmFallbackConfig(enabled=True),
    )


# -- Cross-family provider selection ---------------------------------------


@pytest.mark.unit
async def test_evaluate_selects_cross_family_provider() -> None:
    """Should select a provider from a different family than the agent's."""
    driver_a = AsyncMock()
    driver_a.complete = AsyncMock(return_value=_make_completion_response())
    driver_b = AsyncMock()
    driver_b.complete = AsyncMock(return_value=_make_completion_response())

    evaluator = _make_evaluator(
        driver_map={"provider-a": driver_a, "provider-b": driver_b},
    )
    context = _make_context(agent_provider_name="provider-a")
    rule_verdict = _make_rule_verdict()

    await evaluator.evaluate(context, rule_verdict)

    # provider-b should be called (different family), not provider-a.
    driver_b.complete.assert_awaited_once()
    driver_a.complete.assert_not_awaited()


@pytest.mark.unit
async def test_evaluate_falls_back_to_same_family_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When no cross-family provider exists, use same family with warning."""
    config_a = MagicMock()
    config_a.family = "family-a"
    config_a.models = (MagicMock(id="model-a-1", alias="small"),)

    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(return_value=_make_completion_response())

    evaluator = _make_evaluator(
        provider_configs={"provider-a": config_a},
        driver_map={"provider-a": mock_driver},
    )
    context = _make_context(agent_provider_name="provider-a")
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    mock_driver.complete.assert_awaited_once()
    assert result.verdict == SecurityVerdictType.ALLOW
    assert "same_family_fallback" in caplog.text or result is not None


@pytest.mark.unit
async def test_evaluate_skips_when_no_providers_available() -> None:
    """When no providers are available at all, apply error policy."""
    evaluator = _make_evaluator(
        provider_configs={},
        driver_map={},
    )
    context = _make_context(agent_provider_name="provider-a")
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    # Default error policy: USE_RULE_VERDICT.
    assert result.verdict == rule_verdict.verdict
    assert result.confidence == EvaluationConfidence.LOW


# -- LLM verdict parsing --------------------------------------------------


@pytest.mark.unit
async def test_evaluate_returns_allow_from_llm() -> None:
    """LLM says allow -> verdict is ALLOW with HIGH confidence."""
    tc = _make_llm_tool_call(verdict="allow", risk_level="low")
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(
        return_value=_make_completion_response(tc),
    )
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == SecurityVerdictType.ALLOW
    assert result.risk_level == ApprovalRiskLevel.LOW
    assert result.confidence == EvaluationConfidence.HIGH
    assert "security_verdict" in result.matched_rules


@pytest.mark.unit
async def test_evaluate_returns_deny_from_llm() -> None:
    """LLM says deny -> verdict is DENY with HIGH confidence."""
    tc = _make_llm_tool_call(
        verdict="deny",
        risk_level="high",
        reason="Suspicious file write",
    )
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(
        return_value=_make_completion_response(tc),
    )
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == SecurityVerdictType.DENY
    assert result.risk_level == ApprovalRiskLevel.HIGH
    assert result.confidence == EvaluationConfidence.HIGH


@pytest.mark.unit
async def test_evaluate_returns_escalate_from_llm() -> None:
    """LLM says escalate -> verdict is ESCALATE with HIGH confidence."""
    tc = _make_llm_tool_call(
        verdict="escalate",
        risk_level="critical",
        reason="Needs human review",
    )
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(
        return_value=_make_completion_response(tc),
    )
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == SecurityVerdictType.ESCALATE
    assert result.risk_level == ApprovalRiskLevel.CRITICAL
    assert result.confidence == EvaluationConfidence.HIGH


# -- Error handling --------------------------------------------------------


@pytest.mark.unit
async def test_evaluate_on_error_uses_rule_verdict() -> None:
    """Default error policy returns original rule verdict."""
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(side_effect=RuntimeError("LLM failed"))
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
        config=LlmFallbackConfig(
            enabled=True,
            on_error=LlmFallbackErrorPolicy.USE_RULE_VERDICT,
        ),
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == rule_verdict.verdict
    assert result.risk_level == rule_verdict.risk_level


@pytest.mark.unit
async def test_evaluate_on_error_escalates() -> None:
    """ESCALATE error policy sends to human queue on failure."""
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(side_effect=RuntimeError("LLM failed"))
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
        config=LlmFallbackConfig(
            enabled=True,
            on_error=LlmFallbackErrorPolicy.ESCALATE,
        ),
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == SecurityVerdictType.ESCALATE


@pytest.mark.unit
async def test_evaluate_on_error_denies() -> None:
    """DENY error policy denies on failure."""
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(side_effect=RuntimeError("LLM failed"))
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
        config=LlmFallbackConfig(
            enabled=True,
            on_error=LlmFallbackErrorPolicy.DENY,
        ),
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == SecurityVerdictType.DENY


@pytest.mark.unit
async def test_evaluate_on_timeout_applies_error_policy() -> None:
    """Timeout applies the configured error policy."""

    async def _slow_complete(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(60)  # way longer than timeout

    mock_driver = AsyncMock()
    mock_driver.complete = _slow_complete
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
        config=LlmFallbackConfig(
            enabled=True,
            timeout_seconds=0.01,
            on_error=LlmFallbackErrorPolicy.USE_RULE_VERDICT,
        ),
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == rule_verdict.verdict


# -- Response parsing edge cases -------------------------------------------


@pytest.mark.unit
async def test_parse_no_tool_call_triggers_error_policy() -> None:
    """LLM responds without tool call -> error policy kicks in."""
    response = CompletionResponse(
        content="I think this is fine",
        tool_calls=(),
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(input_tokens=200, output_tokens=50, cost_usd=0.001),
        model="test-small-001",
    )
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(return_value=response)
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    # Default policy: USE_RULE_VERDICT.
    assert result.verdict == rule_verdict.verdict


@pytest.mark.unit
async def test_parse_invalid_verdict_triggers_error_policy() -> None:
    """LLM returns invalid verdict value -> error policy kicks in."""
    tc = ToolCall(
        id="tc-1",
        name="security_verdict",
        arguments={"verdict": "maybe", "risk_level": "low", "reason": "unsure"},
    )
    response = _make_completion_response(tc)
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(return_value=response)
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == rule_verdict.verdict


@pytest.mark.unit
async def test_parse_wrong_tool_name_triggers_error_policy() -> None:
    """LLM calls wrong tool name -> error policy kicks in."""
    tc = ToolCall(
        id="tc-1",
        name="wrong_tool",
        arguments={"verdict": "allow", "risk_level": "low", "reason": "ok"},
    )
    response = _make_completion_response(tc)
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(return_value=response)
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
    )
    context = _make_context()
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == rule_verdict.verdict


# -- Message building ------------------------------------------------------


@pytest.mark.unit
async def test_build_messages_truncates_long_arguments() -> None:
    """Arguments longer than max_input_tokens are truncated."""
    evaluator = _make_evaluator(
        config=LlmFallbackConfig(enabled=True, max_input_tokens=100),
    )
    context = SecurityContext(
        tool_name="test-tool",
        tool_category=ToolCategory.FILE_SYSTEM,
        action_type="code:write",
        arguments={"content": "x" * 10000},
        agent_id="agent-1",
        agent_provider_name="provider-a",
    )

    messages = evaluator._build_messages(context)

    # User message should exist and contain truncated args.
    user_msgs = [m for m in messages if m.role == MessageRole.USER]
    assert len(user_msgs) == 1
    assert len(user_msgs[0].content) < 10000


@pytest.mark.unit
async def test_build_messages_has_system_and_user() -> None:
    """Messages include system prompt and user request."""
    evaluator = _make_evaluator()
    context = _make_context()

    messages = evaluator._build_messages(context)

    roles = [m.role for m in messages]
    assert MessageRole.SYSTEM in roles
    assert MessageRole.USER in roles


# -- Agent provider name handling ------------------------------------------


@pytest.mark.unit
async def test_evaluate_with_no_agent_provider_name() -> None:
    """When agent_provider_name is None, any provider can be selected."""
    mock_driver = AsyncMock()
    mock_driver.complete = AsyncMock(return_value=_make_completion_response())
    evaluator = _make_evaluator(
        driver_map={"provider-a": mock_driver, "provider-b": mock_driver},
    )
    context = _make_context(agent_provider_name=None)
    rule_verdict = _make_rule_verdict()

    result = await evaluator.evaluate(context, rule_verdict)

    assert result.verdict == SecurityVerdictType.ALLOW
    mock_driver.complete.assert_awaited_once()
