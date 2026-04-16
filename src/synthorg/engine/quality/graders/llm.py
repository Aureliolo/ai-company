"""LLM-based rubric grader.

Grades a ``HandoffArtifact`` against a ``VerificationRubric`` by
invoking a structured tool call on a ``CompletionProvider``.  The
provider is expected to invoke the ``emit_rubric_verdict`` tool with
per-criterion grades, an overall verdict, a confidence, and optional
findings.

The grader favors *safe* behavior when the model misbehaves: any
malformed response, missing criterion grade, or out-of-range value is
mapped to a ``REFER`` verdict with ``confidence=0.0``.  Per the
verification design, ``REFER`` routes to human review, so the grader
never silently passes on a broken model response.
"""

import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from synthorg.engine.quality.verification import (
    VerificationResult,
    VerificationVerdict,
)
from synthorg.observability import get_logger
from synthorg.observability.events.verification import (
    VERIFICATION_GRADER_CONFIG_INVALID,
    VERIFICATION_GRADER_PAYLOAD_TRUNCATED,
    VERIFICATION_GRADER_RESPONSE_INVALID,
    VERIFICATION_GRADING_COMPLETED,
    VERIFICATION_GRADING_STARTED,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import (
    ChatMessage,
    CompletionConfig,
    ToolDefinition,
)

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.engine.quality.verification import (
        AtomicProbe,
        VerificationRubric,
    )
    from synthorg.engine.workflow.handoff import HandoffArtifact
    from synthorg.providers.protocol import CompletionProvider

logger = get_logger(__name__)

_GRADER_TOOL_NAME: Final[str] = "emit_rubric_verdict"
_GRADER_TOOL_DESCRIPTION: Final[str] = (
    "Emit a calibrated verdict for the artifact against the rubric.  "
    "Provide a grade in [0, 1] for every criterion by name, an overall "
    "verdict, a confidence in [0, 1], and short human-readable findings."
)
_GRADER_TOOL_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "per_criterion_grades": {
            "type": "object",
            "additionalProperties": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
        },
        "verdict": {
            "type": "string",
            "enum": [
                VerificationVerdict.PASS.value,
                VerificationVerdict.FAIL.value,
                VerificationVerdict.REFER.value,
            ],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["per_criterion_grades", "verdict", "confidence", "findings"],
    "additionalProperties": False,
}
_GRADER_SYSTEM_PROMPT: Final[str] = (
    "You are a calibrated verification evaluator.  Grade the artifact "
    "strictly against the rubric criteria using the calibration "
    "examples (when given) as anchor points.  Prefer REFER when the "
    "artifact is insufficient to decide."
)
_MAX_PAYLOAD_CHARS: Final[int] = 16_000
_DEFAULT_MAX_TOKENS: Final[int] = 2048


class LLMRubricGrader:
    """Grade handoff artifacts against rubrics via a provider tool call.

    Args:
        provider: Completion provider used for the grading call.
        model_id: Resolved model identifier for the configured tier.
        min_confidence_override: Optional floor on confidence; when set
            (and greater than the rubric's ``min_confidence``), any
            response with lower confidence is downgraded to REFER.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model_id: NotBlankStr,
        min_confidence_override: float | None = None,
    ) -> None:
        """Store dependencies and validate override bounds."""
        if min_confidence_override is not None and not (
            0.0 <= min_confidence_override <= 1.0
        ):
            logger.error(
                VERIFICATION_GRADER_CONFIG_INVALID,
                min_confidence_override=min_confidence_override,
                reason="out of [0, 1] range",
            )
            msg = "min_confidence_override must be in [0, 1]"
            raise ValueError(msg)
        self._provider = provider
        self._model_id = model_id
        self._min_confidence_override = min_confidence_override

    @property
    def name(self) -> str:
        """Strategy name."""
        return "llm"

    async def grade(
        self,
        *,
        artifact: HandoffArtifact,
        rubric: VerificationRubric,
        probes: tuple[AtomicProbe, ...],
        generator_agent_id: NotBlankStr,
        evaluator_agent_id: NotBlankStr,
    ) -> VerificationResult:
        """Grade *artifact* against *rubric* using the LLM tool schema.

        Args:
            artifact: The handoff artifact to evaluate.
            rubric: Rubric with criteria, weights, and calibration examples.
            probes: Atomic probes derived from the acceptance criteria.
            generator_agent_id: Agent that produced the artifact.
            evaluator_agent_id: Agent performing the evaluation.

        Returns:
            Structured ``VerificationResult``.  Returns ``REFER`` with
            ``confidence=0.0`` on any malformed model response; callers
            route REFER to human review per the spec.
        """
        logger.info(
            VERIFICATION_GRADING_STARTED,
            rubric_name=rubric.name,
            grader=self.name,
            probe_count=len(probes),
        )

        tool = ToolDefinition(
            name=_GRADER_TOOL_NAME,
            description=_GRADER_TOOL_DESCRIPTION,
            parameters_schema=_GRADER_TOOL_SCHEMA,
        )
        user_prompt = self._build_user_prompt(
            artifact=artifact,
            rubric=rubric,
            probes=probes,
        )
        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=_GRADER_SYSTEM_PROMPT,
            ),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        response = await self._provider.complete(
            messages=messages,
            model=self._model_id,
            tools=[tool],
            config=CompletionConfig(
                temperature=0.0,
                max_tokens=_DEFAULT_MAX_TOKENS,
            ),
        )

        tool_call = next(
            (tc for tc in response.tool_calls if tc.name == _GRADER_TOOL_NAME),
            None,
        )
        if tool_call is None:
            return self._refer(
                rubric=rubric,
                generator_agent_id=generator_agent_id,
                evaluator_agent_id=evaluator_agent_id,
                reason="no emit_rubric_verdict tool call in response",
            )

        parsed = self._parse_tool_arguments(
            tool_call.arguments,
            rubric=rubric,
        )
        if isinstance(parsed, str):
            return self._refer(
                rubric=rubric,
                generator_agent_id=generator_agent_id,
                evaluator_agent_id=evaluator_agent_id,
                reason=parsed,
            )
        per_criterion_grades, verdict, confidence, findings = parsed

        applied_min_conf = self._applied_min_confidence(rubric)
        if confidence < applied_min_conf:
            verdict = VerificationVerdict.REFER
            findings = (
                *findings,
                f"Confidence {confidence:.2f} below minimum "
                f"{applied_min_conf:.2f}; downgraded to REFER.",
            )

        result = VerificationResult(
            verdict=verdict,
            confidence=confidence,
            per_criterion_grades=per_criterion_grades,
            findings=findings,
            evaluator_agent_id=evaluator_agent_id,
            generator_agent_id=generator_agent_id,
            rubric_name=rubric.name,
            timestamp=datetime.now(UTC),
        )
        logger.info(
            VERIFICATION_GRADING_COMPLETED,
            rubric_name=rubric.name,
            verdict=result.verdict.value,
            confidence=result.confidence,
            grader=self.name,
        )
        return result

    def _applied_min_confidence(self, rubric: VerificationRubric) -> float:
        """Return the stricter of rubric min_confidence and override."""
        if self._min_confidence_override is None:
            return rubric.min_confidence
        return max(rubric.min_confidence, self._min_confidence_override)

    def _build_user_prompt(
        self,
        *,
        artifact: HandoffArtifact,
        rubric: VerificationRubric,
        probes: tuple[AtomicProbe, ...],
    ) -> str:
        """Render rubric, calibration, probes, and payload as a JSON envelope."""
        payload_text = json.dumps(dict(artifact.payload), ensure_ascii=False)
        original_len = len(payload_text)
        payload_truncated = original_len > _MAX_PAYLOAD_CHARS
        if payload_truncated:
            logger.warning(
                VERIFICATION_GRADER_PAYLOAD_TRUNCATED,
                rubric_name=rubric.name,
                grader=self.name,
                original_chars=original_len,
                truncated_chars=_MAX_PAYLOAD_CHARS,
            )
            payload_text = payload_text[:_MAX_PAYLOAD_CHARS]

        calibration = [
            {
                "artifact_summary": ex.artifact_summary,
                "expected_verdict": ex.expected_verdict.value,
                "rationale": ex.rationale,
                "expected_grades": (
                    dict(ex.expected_grades) if ex.expected_grades is not None else None
                ),
            }
            for ex in rubric.calibration_examples
        ]

        envelope = {
            "rubric": {
                "name": rubric.name,
                "min_confidence": rubric.min_confidence,
                "criteria": [
                    {
                        "name": c.name,
                        "description": c.description,
                        "weight": c.weight,
                        "grade_type": c.grade_type.value,
                    }
                    for c in rubric.criteria
                ],
                "calibration_examples": calibration,
            },
            "probes": [
                {
                    "id": p.id,
                    "probe_text": p.probe_text,
                    "source_criterion": p.source_criterion,
                }
                for p in probes
            ],
            "artifact": {
                "from_agent_id": artifact.from_agent_id,
                "to_agent_id": artifact.to_agent_id,
                "from_stage": artifact.from_stage,
                "to_stage": artifact.to_stage,
                "artifact_refs": list(artifact.artifact_refs),
                "payload": payload_text,
            },
            "instructions": (
                "Call emit_rubric_verdict exactly once.  Provide a grade "
                "for every rubric criterion by name (use the criterion "
                "'name' field).  The overall verdict must be 'pass' only "
                "when the weighted evidence supports it; otherwise 'fail' "
                "or 'refer'.  Confidence reflects your certainty."
                + (
                    (
                        f"  Note: the artifact payload was truncated from "
                        f"{original_len} to {_MAX_PAYLOAD_CHARS} characters; "
                        "if the visible payload is insufficient to decide, "
                        "return 'refer' rather than guessing."
                    )
                    if payload_truncated
                    else ""
                )
            ),
        }
        return json.dumps(envelope, ensure_ascii=False)

    def _parse_tool_arguments(
        self,
        arguments: Mapping[str, Any],
        *,
        rubric: VerificationRubric,
    ) -> tuple[dict[str, float], VerificationVerdict, float, tuple[str, ...]] | str:
        """Parse and validate the tool call arguments.

        Returns the parsed tuple on success or a reason string on failure.
        """
        grades_or_reason = _parse_grades(
            arguments.get("per_criterion_grades"),
            rubric=rubric,
        )
        if not isinstance(grades_or_reason, dict):
            return grades_or_reason
        grades = grades_or_reason

        verdict_or_reason = _parse_verdict(arguments.get("verdict"))
        if not isinstance(verdict_or_reason, VerificationVerdict):
            return verdict_or_reason
        verdict = verdict_or_reason

        confidence_or_reason = _parse_confidence(arguments.get("confidence"))
        if isinstance(confidence_or_reason, str):
            return confidence_or_reason
        confidence = float(confidence_or_reason)

        findings_or_reason = _parse_findings(arguments.get("findings", []))
        if not isinstance(findings_or_reason, tuple):
            return findings_or_reason
        findings = findings_or_reason

        return grades, verdict, confidence, findings

    def _refer(
        self,
        *,
        rubric: VerificationRubric,
        generator_agent_id: NotBlankStr,
        evaluator_agent_id: NotBlankStr,
        reason: str,
    ) -> VerificationResult:
        """Build a safe REFER result when the model response is unusable."""
        logger.error(
            VERIFICATION_GRADER_RESPONSE_INVALID,
            rubric_name=rubric.name,
            grader=self.name,
            reason=reason,
        )
        result = VerificationResult(
            verdict=VerificationVerdict.REFER,
            confidence=0.0,
            per_criterion_grades={c.name: 0.0 for c in rubric.criteria},
            findings=(f"LLM grader response invalid: {reason}",),
            evaluator_agent_id=evaluator_agent_id,
            generator_agent_id=generator_agent_id,
            rubric_name=rubric.name,
            timestamp=datetime.now(UTC),
        )
        logger.info(
            VERIFICATION_GRADING_COMPLETED,
            rubric_name=rubric.name,
            verdict=result.verdict.value,
            confidence=result.confidence,
            grader=self.name,
        )
        return result


def _parse_grades(
    raw: Any,
    *,
    rubric: VerificationRubric,
) -> dict[str, float] | str:
    """Validate the per-criterion grades mapping."""
    if not isinstance(raw, Mapping):
        return "per_criterion_grades is not an object"
    expected = {c.name for c in rubric.criteria}
    grades: dict[str, float] = {}
    for name, value in raw.items():
        if name not in expected:
            return f"unknown criterion {name!r}"
        parsed = _parse_unit_interval(value)
        if isinstance(parsed, str):
            return f"grade for {name!r}: {parsed}"
        grades[name] = parsed
    missing = expected - set(grades)
    if missing:
        return f"missing grades for criteria: {sorted(missing)}"
    return grades


def _parse_verdict(raw: Any) -> VerificationVerdict | str:
    """Coerce the verdict string into a ``VerificationVerdict``."""
    if not isinstance(raw, str):
        return "verdict is not a string"
    try:
        return VerificationVerdict(raw)
    except ValueError:
        return f"unknown verdict {raw!r}"


def _parse_confidence(raw: Any) -> float | str:
    """Validate confidence is a finite float in [0, 1]."""
    return _parse_unit_interval(raw, label="confidence")


def _parse_findings(raw: Any) -> tuple[str, ...] | str:
    """Validate findings is a list of strings, trimming blanks."""
    if not isinstance(raw, list):
        return "findings is not a list"
    findings: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        findings.append(item.strip())
    return tuple(findings)


def _parse_unit_interval(value: Any, *, label: str = "value") -> float | str:
    """Return *value* as a finite float in [0, 1] or a reason string."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return f"{label} is not numeric"
    parsed = float(value)
    if math.isnan(parsed) or math.isinf(parsed):
        return f"{label} is not finite"
    if not (0.0 <= parsed <= 1.0):
        return f"{label} out of [0, 1]"
    return parsed
