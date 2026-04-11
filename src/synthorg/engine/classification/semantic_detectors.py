"""LLM-backed semantic detectors for the classification pipeline.

Each detector sends a structured prompt to a ``BaseCompletionProvider``
and parses the JSON response into ``ErrorFinding`` tuples.  All
detectors are disabled by default -- they require explicit opt-in
via ``DetectorVariant.LLM_SEMANTIC`` in the per-category config.
"""

import json
from typing import TYPE_CHECKING

from synthorg.budget.coordination_config import (
    DetectionScope,
    ErrorCategory,
)
from synthorg.engine.classification.models import (
    ErrorFinding,
    ErrorSeverity,
)
from synthorg.engine.sanitization import sanitize_message
from synthorg.observability import get_logger
from synthorg.observability.events.classification import (
    DETECTOR_COMPLETE,
    DETECTOR_ERROR,
    DETECTOR_START,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage

if TYPE_CHECKING:
    from synthorg.engine.classification.budget_tracker import (
        ClassificationBudgetTracker,
    )
    from synthorg.engine.classification.protocol import DetectionContext
    from synthorg.providers.base import BaseCompletionProvider
    from synthorg.providers.resilience.rate_limiter import RateLimiter

logger = get_logger(__name__)

_SANITIZE_MAX_LENGTH = 2000
_SEVERITY_MAP = {
    "low": ErrorSeverity.LOW,
    "medium": ErrorSeverity.MEDIUM,
    "high": ErrorSeverity.HIGH,
}


def _parse_findings(
    raw: str | None,
    category: ErrorCategory,
) -> tuple[ErrorFinding, ...]:
    """Parse LLM JSON output into ErrorFinding tuples.

    Expected format::

        [
            {
                "description": "...",
                "severity": "high|medium|low",
                "evidence": ["..."],
                "turn_start": 0,
                "turn_end": 2,
            }
        ]

    Malformed entries are silently skipped.
    """
    if not raw:
        return ()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(items, list):
        return ()

    findings: list[ErrorFinding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        desc = item.get("description", "")
        if not desc or not isinstance(desc, str):
            continue
        severity = _SEVERITY_MAP.get(
            str(item.get("severity", "medium")).lower(),
            ErrorSeverity.MEDIUM,
        )
        evidence_raw = item.get("evidence", [])
        evidence = tuple(
            str(e) for e in evidence_raw if isinstance(e, str) and e.strip()
        )
        turn_start = item.get("turn_start")
        turn_end = item.get("turn_end")
        turn_range = None
        if (
            isinstance(turn_start, int)
            and isinstance(turn_end, int)
            and turn_start >= 0
            and turn_end >= turn_start
        ):
            turn_range = (turn_start, turn_end)

        findings.append(
            ErrorFinding(
                category=category,
                severity=severity,
                description=desc,
                evidence=evidence,
                turn_range=turn_range,
            ),
        )
    return tuple(findings)


def _build_conversation_text(
    context: DetectionContext,
) -> str:
    """Build sanitized conversation text for the LLM prompt."""
    parts: list[str] = []
    for i, msg in enumerate(context.execution_result.context.conversation):
        if msg.role == MessageRole.ASSISTANT and msg.content:
            sanitized = sanitize_message(
                msg.content,
                max_length=_SANITIZE_MAX_LENGTH,
            )
            parts.append(f"[{i}] {sanitized}")
    return "\n".join(parts)


class _BaseSemanticDetector:
    """Base class for LLM-backed semantic detectors.

    Handles provider invocation, rate limiting, budget tracking,
    and response parsing.  Subclasses provide the category, scopes,
    and prompt text.
    """

    @property
    def category(self) -> ErrorCategory:
        """Error category -- must be overridden by subclasses."""
        msg = "Subclasses must override category"
        raise NotImplementedError(msg)

    def __init__(
        self,
        *,
        provider: BaseCompletionProvider,
        model_id: str,
        rate_limiter: RateLimiter | None = None,
        budget_tracker: ClassificationBudgetTracker | None = None,
    ) -> None:
        self._provider = provider
        self._model_id = model_id
        self._rate_limiter = rate_limiter
        self._budget_tracker = budget_tracker

    def _prompt(self, conversation_text: str) -> str:
        """Build the analysis prompt.  Override in subclasses."""
        msg = "Subclasses must override _prompt"
        raise NotImplementedError(msg)

    async def detect(
        self,
        context: DetectionContext,
    ) -> tuple[ErrorFinding, ...]:
        """Run semantic detection via LLM.

        Args:
            context: Detection context with execution data.

        Returns:
            Tuple of findings parsed from LLM response.
        """
        detector_name = type(self).__name__
        logger.debug(DETECTOR_START, detector=detector_name, message_count=0)

        # Budget gate
        if self._budget_tracker is not None and not self._budget_tracker.can_spend(
            0.001
        ):
            logger.debug(
                DETECTOR_COMPLETE,
                detector=detector_name,
                finding_count=0,
            )
            return ()

        conversation_text = _build_conversation_text(context)
        if not conversation_text:
            logger.debug(
                DETECTOR_COMPLETE,
                detector=detector_name,
                finding_count=0,
            )
            return ()

        prompt_text = self._prompt(conversation_text)
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=prompt_text),
            ChatMessage(
                role=MessageRole.USER,
                content="Analyze the conversation above and return JSON.",
            ),
        ]

        try:
            if self._rate_limiter is not None:
                await self._rate_limiter.acquire()
            try:
                response = await self._provider.complete(
                    messages,
                    self._model_id,
                )
            finally:
                if self._rate_limiter is not None:
                    self._rate_limiter.release()

            # Track cost
            if self._budget_tracker is not None and response.usage is not None:
                self._budget_tracker.record(response.usage.cost_usd)

            findings = _parse_findings(response.content, self.category)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                DETECTOR_ERROR,
                detector=detector_name,
                agent_id=context.agent_id,
                task_id=context.task_id,
                message_count=0,
            )
            findings = ()

        logger.debug(
            DETECTOR_COMPLETE,
            detector=detector_name,
            finding_count=len(findings),
        )
        return findings


class SemanticContradictionDetector(_BaseSemanticDetector):
    """LLM-backed detector for logical contradictions."""

    @property
    def category(self) -> ErrorCategory:
        """Error category this detector targets."""
        return ErrorCategory.LOGICAL_CONTRADICTION

    @property
    def supported_scopes(self) -> frozenset[DetectionScope]:
        """Detection scopes this detector can operate on."""
        return frozenset({DetectionScope.SAME_TASK})

    def _prompt(self, conversation_text: str) -> str:
        return (
            "You are an error analysis assistant. Below are assistant "
            "messages from a multi-agent conversation, indexed by "
            "position.\n\n"
            f"{conversation_text}\n\n"
            "Identify any logical contradictions where one message "
            "asserts something and another negates it. Return a JSON "
            'array. Each item: {"description": "...", "severity": '
            '"high|medium|low", "evidence": ["msg text"], '
            '"turn_start": N, "turn_end": N}. Return [] if none.'
        )


class SemanticNumericalVerificationDetector(_BaseSemanticDetector):
    """LLM-backed detector for numerical inconsistencies."""

    @property
    def category(self) -> ErrorCategory:
        """Error category this detector targets."""
        return ErrorCategory.NUMERICAL_DRIFT

    @property
    def supported_scopes(self) -> frozenset[DetectionScope]:
        """Detection scopes this detector can operate on."""
        return frozenset(
            {DetectionScope.SAME_TASK, DetectionScope.TASK_TREE},
        )

    def _prompt(self, conversation_text: str) -> str:
        return (
            "You are a numerical verification assistant. Below are "
            "assistant messages from a conversation.\n\n"
            f"{conversation_text}\n\n"
            "Identify any numerical values that change inconsistently "
            "between messages (drift, contradictory figures). Return "
            'a JSON array. Each item: {"description": "...", '
            '"severity": "high|medium|low", "evidence": ["..."], '
            '"turn_start": N, "turn_end": N}. Return [] if none.'
        )


class SemanticMissingReferenceDetector(_BaseSemanticDetector):
    """LLM-backed detector for missing entity references."""

    @property
    def category(self) -> ErrorCategory:
        """Error category this detector targets."""
        return ErrorCategory.CONTEXT_OMISSION

    @property
    def supported_scopes(self) -> frozenset[DetectionScope]:
        """Detection scopes this detector can operate on."""
        return frozenset(
            {DetectionScope.SAME_TASK, DetectionScope.TASK_TREE},
        )

    def _prompt(self, conversation_text: str) -> str:
        return (
            "You are a context analysis assistant. Below are "
            "assistant messages from a conversation.\n\n"
            f"{conversation_text}\n\n"
            "Identify entities, concepts, or requirements introduced "
            "early that are dropped or never referenced again in "
            "later messages. Return a JSON array. Each item: "
            '{"description": "...", "severity": "high|medium|low", '
            '"evidence": ["..."], "turn_start": N, "turn_end": N}. '
            "Return [] if none."
        )


class SemanticCoordinationDetector(_BaseSemanticDetector):
    """LLM-backed detector for coordination breakdowns."""

    @property
    def category(self) -> ErrorCategory:
        """Error category this detector targets."""
        return ErrorCategory.COORDINATION_FAILURE

    @property
    def supported_scopes(self) -> frozenset[DetectionScope]:
        """Detection scopes this detector can operate on."""
        return frozenset({DetectionScope.TASK_TREE})

    def _prompt(self, conversation_text: str) -> str:
        return (
            "You are a coordination analysis assistant. Below are "
            "assistant messages from a multi-agent conversation.\n\n"
            f"{conversation_text}\n\n"
            "Identify coordination breakdowns: misinterpreted "
            "instructions, conflicting task approaches, missing "
            "handoff information, or state synchronization failures. "
            'Return a JSON array. Each item: {"description": "...", '
            '"severity": "high|medium|low", "evidence": ["..."], '
            '"turn_start": N, "turn_end": N}. Return [] if none.'
        )
