"""LLM-based security evaluator for uncertain rule engine verdicts.

When the rule engine cannot classify an action (no rule matched,
``EvaluationConfidence.LOW``), this evaluator routes the security
context to an LLM from a different provider family for cross-
validation.  The LLM returns a structured verdict via tool calling.

Design invariants:
    - Hard-deny rules always have HIGH confidence and are never
      re-evaluated by the LLM.
    - Full-autonomy mode skips LLM evaluation entirely (enforced
      by ``SecOpsService``, not here).
    - Cross-family selection is best-effort: same-family with a
      warning if no alternative exists.
    - LLM failures apply the configured error policy
      (``LlmFallbackErrorPolicy``).
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.enums import ApprovalRiskLevel
from synthorg.observability import get_logger
from synthorg.observability.events.security import (
    SECURITY_LLM_EVAL_COMPLETE,
    SECURITY_LLM_EVAL_CROSS_FAMILY,
    SECURITY_LLM_EVAL_ERROR,
    SECURITY_LLM_EVAL_NO_PROVIDER,
    SECURITY_LLM_EVAL_SAME_FAMILY_FALLBACK,
    SECURITY_LLM_EVAL_START,
    SECURITY_LLM_EVAL_TIMEOUT,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.family import get_family, providers_excluding_family
from synthorg.providers.models import ChatMessage, CompletionConfig, ToolDefinition
from synthorg.security.config import LlmFallbackConfig, LlmFallbackErrorPolicy
from synthorg.security.models import (
    EvaluationConfidence,
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)

if TYPE_CHECKING:
    from synthorg.config.schema import ProviderConfig
    from synthorg.providers.base import BaseCompletionProvider
    from synthorg.providers.models import CompletionResponse
    from synthorg.providers.registry import ProviderRegistry

logger = get_logger(__name__)

# Maximum length for serialized arguments in the prompt.
_MAX_ARGS_DISPLAY = 1500

# Tool schema for structured LLM response.
_SECURITY_VERDICT_TOOL = ToolDefinition(
    name="security_verdict",
    description=(
        "Submit your security evaluation verdict for the proposed "
        "agent action.  You MUST call this tool with your assessment."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["allow", "deny", "escalate"],
                "description": (
                    "Security verdict: allow (safe), deny (unsafe), "
                    "or escalate (needs human review)."
                ),
            },
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Assessed risk level of the action.",
            },
            "reason": {
                "type": "string",
                "description": ("Brief explanation for the verdict (1-2 sentences)."),
            },
        },
        "required": ["verdict", "risk_level", "reason"],
        "additionalProperties": False,
    },
)

_SYSTEM_PROMPT = (
    "You are a security evaluator for an AI agent orchestration system. "
    "An agent is requesting to execute a tool action.  The rule-based "
    "security engine could not classify this action and needs your "
    "assessment.\n\n"
    "Evaluate whether the action is safe to execute.  Consider:\n"
    "- Could this action expose credentials or sensitive data?\n"
    "- Could this action cause data loss or destruction?\n"
    "- Are the arguments suspicious or potentially malicious?\n"
    "- Is this action appropriate for the stated context?\n\n"
    "You MUST call the security_verdict tool with your assessment.  "
    "Do not respond with text -- only use the tool."
)

_VALID_VERDICTS = frozenset({"allow", "deny", "escalate"})
_VALID_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})

_RISK_LEVEL_MAP: dict[str, ApprovalRiskLevel] = {
    "low": ApprovalRiskLevel.LOW,
    "medium": ApprovalRiskLevel.MEDIUM,
    "high": ApprovalRiskLevel.HIGH,
    "critical": ApprovalRiskLevel.CRITICAL,
}

_VERDICT_MAP: dict[str, SecurityVerdictType] = {
    "allow": SecurityVerdictType.ALLOW,
    "deny": SecurityVerdictType.DENY,
    "escalate": SecurityVerdictType.ESCALATE,
}


class LlmSecurityEvaluator:
    """Evaluates uncertain security contexts using an LLM.

    Selects a model from a different provider family than the agent
    being evaluated, sends a structured prompt, and parses the tool-
    call response into a ``SecurityVerdict``.

    Args:
        provider_registry: Registry of provider drivers.
        provider_configs: Provider config dict for family lookup.
        config: LLM fallback configuration.
    """

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        provider_configs: dict[str, ProviderConfig],
        config: LlmFallbackConfig,
    ) -> None:
        self._registry = provider_registry
        self._configs = provider_configs
        self._config = config

    async def evaluate(
        self,
        context: SecurityContext,
        rule_verdict: SecurityVerdict,
    ) -> SecurityVerdict:
        """Run LLM-based security evaluation.

        Args:
            context: The tool invocation security context.
            rule_verdict: The original rule engine verdict (LOW
                confidence).

        Returns:
            An LLM-derived ``SecurityVerdict`` with HIGH confidence,
            or the original verdict if the LLM call fails (per error
            policy).
        """
        start = time.monotonic()
        logger.info(
            SECURITY_LLM_EVAL_START,
            tool_name=context.tool_name,
            action_type=context.action_type,
            agent_provider=context.agent_provider_name,
        )

        # Select provider.
        provider_name, driver = self._select_provider(
            context.agent_provider_name,
        )
        if provider_name is None or driver is None:
            return self._apply_error_policy(
                rule_verdict,
                "No provider available for LLM security evaluation",
            )

        # Select model.
        model = self._select_model(provider_name)

        # Build messages and call LLM.
        messages = self._build_messages(context)
        try:
            response = await asyncio.wait_for(
                driver.complete(
                    messages,
                    model,
                    tools=[_SECURITY_VERDICT_TOOL],
                    config=CompletionConfig(
                        temperature=0.0,
                        max_tokens=256,
                    ),
                ),
                timeout=self._config.timeout_seconds,
            )
        except TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning(
                SECURITY_LLM_EVAL_TIMEOUT,
                tool_name=context.tool_name,
                timeout_seconds=self._config.timeout_seconds,
                duration_ms=duration_ms,
            )
            return self._apply_error_policy(
                rule_verdict,
                f"LLM evaluation timed out after {self._config.timeout_seconds}s",
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception(
                SECURITY_LLM_EVAL_ERROR,
                tool_name=context.tool_name,
                duration_ms=duration_ms,
            )
            return self._apply_error_policy(
                rule_verdict,
                "LLM evaluation failed",
            )

        # Parse response.
        verdict = self._parse_llm_response(response, rule_verdict, start)

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            SECURITY_LLM_EVAL_COMPLETE,
            tool_name=context.tool_name,
            verdict=verdict.verdict.value,
            risk_level=verdict.risk_level.value,
            confidence=verdict.confidence.value,
            duration_ms=duration_ms,
            cost_usd=response.usage.cost_usd,
            model=response.model,
        )

        return verdict

    def _select_provider(
        self,
        agent_provider_name: str | None,
    ) -> tuple[str | None, BaseCompletionProvider | None]:
        """Select a provider for security evaluation.

        Prefers a provider from a different family than the agent's.
        Falls back to same-family with a warning if needed.

        Returns:
            ``(provider_name, driver)`` or ``(None, None)`` if no
            provider is available.
        """
        available = self._registry.list_providers()
        if not available:
            logger.warning(
                SECURITY_LLM_EVAL_NO_PROVIDER,
                agent_provider=agent_provider_name,
            )
            return None, None

        # Try cross-family first.
        if agent_provider_name is not None:
            agent_family = get_family(agent_provider_name, self._configs)
            cross_family = providers_excluding_family(
                agent_family,
                self._configs,
            )
            # Filter to actually registered providers.
            cross_family = tuple(p for p in cross_family if p in available)
            if cross_family:
                name = cross_family[0]
                logger.debug(
                    SECURITY_LLM_EVAL_CROSS_FAMILY,
                    selected_provider=name,
                    agent_provider=agent_provider_name,
                    agent_family=agent_family,
                )
                return name, self._registry.get(name)

            # Same-family fallback.
            logger.warning(
                SECURITY_LLM_EVAL_SAME_FAMILY_FALLBACK,
                agent_provider=agent_provider_name,
                agent_family=agent_family,
                note="No cross-family provider available",
            )

        # Pick the first available (may be same family).
        name = available[0]
        return name, self._registry.get(name)

    def _select_model(self, provider_name: str) -> str:
        """Select the model to use for security evaluation.

        Uses explicit config model if set, otherwise picks the first
        model from the selected provider's config.
        """
        if self._config.model is not None:
            return self._config.model

        config = self._configs.get(provider_name)
        if config is not None and config.models:
            # Prefer alias if available, otherwise model ID.
            first = config.models[0]
            return first.alias or first.id

        # Last resort: use provider name as model hint.
        return provider_name

    def _build_messages(
        self,
        context: SecurityContext,
    ) -> list[ChatMessage]:
        """Build the LLM prompt messages from the security context."""
        # Serialize and truncate arguments.
        try:
            args_str = json.dumps(
                context.arguments,
                indent=None,
                default=str,
                ensure_ascii=False,
            )
        except TypeError, ValueError:
            args_str = str(context.arguments)

        if len(args_str) > _MAX_ARGS_DISPLAY:
            args_str = args_str[:_MAX_ARGS_DISPLAY] + "... [truncated]"

        user_content = (
            f"Action: {context.tool_name} ({context.action_type})\n"
            f"Category: {context.tool_category.value}\n"
            f"Agent: {context.agent_id or 'unknown'}\n"
            f"Task: {context.task_id or 'unknown'}\n"
            f"Arguments:\n{args_str}"
        )

        # Enforce max_input_tokens budget (rough char estimate).
        max_chars = self._config.max_input_tokens * 4
        if len(user_content) > max_chars:
            user_content = user_content[:max_chars] + "\n... [truncated]"

        return [
            ChatMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT),
            ChatMessage(role=MessageRole.USER, content=user_content),
        ]

    def _parse_llm_response(
        self,
        response: CompletionResponse,
        rule_verdict: SecurityVerdict,
        start: float,
    ) -> SecurityVerdict:
        """Parse the LLM response into a SecurityVerdict.

        Falls back to error policy on parse failure.
        """
        # Find the security_verdict tool call.
        for tc in response.tool_calls:
            if tc.name == "security_verdict":
                return self._parse_tool_call_args(
                    tc.arguments,
                    rule_verdict,
                    start,
                )

        # No matching tool call found.
        logger.warning(
            SECURITY_LLM_EVAL_ERROR,
            note="LLM did not call security_verdict tool",
            tool_calls=[tc.name for tc in response.tool_calls],
        )
        return self._apply_error_policy(
            rule_verdict,
            "LLM did not call the security_verdict tool",
        )

    def _parse_tool_call_args(
        self,
        args: dict[str, object],
        rule_verdict: SecurityVerdict,
        start: float,
    ) -> SecurityVerdict:
        """Parse tool call arguments into a SecurityVerdict."""
        raw_verdict = args.get("verdict", "")
        raw_risk = args.get("risk_level", "")
        raw_reason = args.get("reason", "")

        if raw_verdict not in _VALID_VERDICTS:
            logger.warning(
                SECURITY_LLM_EVAL_ERROR,
                note=f"Invalid verdict value: {raw_verdict!r}",
            )
            return self._apply_error_policy(
                rule_verdict,
                f"LLM returned invalid verdict: {raw_verdict!r}",
            )

        if raw_risk not in _VALID_RISK_LEVELS:
            logger.warning(
                SECURITY_LLM_EVAL_ERROR,
                note=f"Invalid risk_level value: {raw_risk!r}",
            )
            return self._apply_error_policy(
                rule_verdict,
                f"LLM returned invalid risk_level: {raw_risk!r}",
            )

        reason = str(raw_reason).strip() if raw_reason else "LLM security evaluation"
        duration_ms = (time.monotonic() - start) * 1000

        return SecurityVerdict(
            verdict=_VERDICT_MAP[str(raw_verdict)],
            reason=f"LLM security eval: {reason}",
            risk_level=_RISK_LEVEL_MAP[str(raw_risk)],
            confidence=EvaluationConfidence.HIGH,
            matched_rules=("security_verdict",),
            evaluated_at=datetime.now(UTC),
            evaluation_duration_ms=duration_ms,
        )

    def _apply_error_policy(
        self,
        rule_verdict: SecurityVerdict,
        reason: str,
    ) -> SecurityVerdict:
        """Apply the configured error policy.

        Args:
            rule_verdict: Original rule engine verdict to fall back to.
            reason: Why the LLM evaluation failed.

        Returns:
            A ``SecurityVerdict`` based on the error policy.
        """
        policy = self._config.on_error
        now = datetime.now(UTC)

        if policy == LlmFallbackErrorPolicy.ESCALATE:
            return SecurityVerdict(
                verdict=SecurityVerdictType.ESCALATE,
                reason=f"{reason} -- escalated per error policy",
                risk_level=ApprovalRiskLevel.HIGH,
                confidence=EvaluationConfidence.LOW,
                evaluated_at=now,
                evaluation_duration_ms=0.0,
            )

        if policy == LlmFallbackErrorPolicy.DENY:
            return SecurityVerdict(
                verdict=SecurityVerdictType.DENY,
                reason=f"{reason} -- denied per error policy",
                risk_level=ApprovalRiskLevel.HIGH,
                confidence=EvaluationConfidence.LOW,
                evaluated_at=now,
                evaluation_duration_ms=0.0,
            )

        # USE_RULE_VERDICT (default): return original verdict as-is.
        return rule_verdict
