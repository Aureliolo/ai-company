"""LLM-based criteria decomposer.

Decomposes acceptance criteria into atomic binary probes by invoking a
structured tool call on a ``CompletionProvider``.  The provider is
expected to invoke the ``emit_atomic_probes`` tool, whose arguments are
strictly validated before being materialized as ``AtomicProbe`` tuples.

Tool-call output is used instead of free-text JSON parsing because every
current provider supports function calling natively, eliminating a whole
class of parse errors, retries on malformed JSON, and prompt-injection
exposure via model-supplied identifiers.  Probe IDs are generated
server-side (never taken from the model).
"""

import json
from typing import TYPE_CHECKING, Any, Final

from synthorg.engine.quality.verification import AtomicProbe
from synthorg.observability import get_logger
from synthorg.observability.events.verification import (
    VERIFICATION_CRITERIA_DECOMPOSED,
    VERIFICATION_DECOMPOSER_CRITERIA_TRUNCATED,
    VERIFICATION_DECOMPOSER_PROBE_REJECTED,
    VERIFICATION_DECOMPOSER_RESPONSE_INVALID,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import (
    ChatMessage,
    CompletionConfig,
    ToolDefinition,
)

if TYPE_CHECKING:
    from synthorg.core.task import AcceptanceCriterion
    from synthorg.core.types import NotBlankStr
    from synthorg.providers.protocol import CompletionProvider

logger = get_logger(__name__)

_DECOMPOSER_TOOL_NAME: Final[str] = "emit_atomic_probes"
_DECOMPOSER_TOOL_DESCRIPTION: Final[str] = (
    "Emit a list of atomic binary (yes/no) probes that together verify "
    "whether the given acceptance criteria have been satisfied.  Each "
    "probe must target exactly one criterion by zero-based index."
)
_DECOMPOSER_TOOL_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "probes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_criterion_index": {
                        "type": "integer",
                        "minimum": 0,
                    },
                    "probe_text": {"type": "string"},
                },
                "required": ["source_criterion_index", "probe_text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["probes"],
    "additionalProperties": False,
}
_DECOMPOSER_SYSTEM_PROMPT: Final[str] = (
    "You are a verification analyst.  Your job is to break acceptance "
    "criteria into atomic binary probes -- each a single yes/no question "
    "whose answer can be determined by inspecting the produced artifact.  "
    "Favor multiple specific probes over one vague probe.  Do not invent "
    "new requirements; every probe must trace to a given criterion."
)
_MAX_PROMPT_CRITERIA_CHARS: Final[int] = 8_000
_MIN_CRITERION_DESC_CHARS: Final[int] = 16


class LLMDecompositionError(RuntimeError):
    """Raised when the LLM decomposer cannot obtain a valid probe list."""


class LLMCriteriaDecomposer:
    """Decompose acceptance criteria into probes via a provider tool call.

    The decomposer sends the rubric's acceptance criteria to the model
    along with a strict tool schema.  The model is expected to reply
    with a single ``emit_atomic_probes`` tool invocation; any other
    response shape raises ``LLMDecompositionError``.

    Args:
        provider: Completion provider used for the decomposition call.
            The base class already applies retry and rate limiting.
        model_id: Resolved model identifier for the configured tier.
        max_probes_per_criterion: Upper bound on probes per criterion.
            Extra probes from the model are dropped with a log line.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model_id: NotBlankStr,
        max_probes_per_criterion: int = 5,
    ) -> None:
        """Store dependencies and enforce a positive cap."""
        if max_probes_per_criterion < 1:
            msg = "max_probes_per_criterion must be >= 1"
            raise ValueError(msg)
        self._provider = provider
        self._model_id = model_id
        self._max_probes_per_criterion = max_probes_per_criterion

    @property
    def name(self) -> str:
        """Strategy name."""
        return "llm"

    async def decompose(
        self,
        criteria: tuple[AcceptanceCriterion, ...],
        *,
        task_id: NotBlankStr,
        agent_id: NotBlankStr,
    ) -> tuple[AtomicProbe, ...]:
        """Decompose criteria into atomic probes via the configured LLM.

        Args:
            criteria: Acceptance criteria to decompose.
            task_id: Task identifier (used to stamp deterministic probe IDs).
            agent_id: Agent identifier for logging context.

        Returns:
            Tuple of validated atomic probes.  Empty when ``criteria``
            is empty.

        Raises:
            LLMDecompositionError: If the model does not emit a valid
                ``emit_atomic_probes`` tool call or the returned probes
                do not pass structural validation.
        """
        if not criteria:
            logger.info(
                VERIFICATION_CRITERIA_DECOMPOSED,
                task_id=task_id,
                agent_id=agent_id,
                probe_count=0,
                decomposer=self.name,
                reason="empty criteria",
            )
            return ()

        tool, messages = self._prepare_tool_and_messages(criteria)
        response = await self._invoke_provider(messages, tool)
        raw_probes = self._extract_raw_probes(
            response,
            task_id=task_id,
            agent_id=agent_id,
        )
        probes = self._materialize_probes(
            raw_probes,
            criteria=criteria,
            task_id=task_id,
            agent_id=agent_id,
        )

        logger.info(
            VERIFICATION_CRITERIA_DECOMPOSED,
            task_id=task_id,
            agent_id=agent_id,
            probe_count=len(probes),
            decomposer=self.name,
        )
        return probes

    def _prepare_tool_and_messages(
        self,
        criteria: tuple[AcceptanceCriterion, ...],
    ) -> tuple[ToolDefinition, list[ChatMessage]]:
        """Build the ``emit_atomic_probes`` tool + system/user messages."""
        tool = ToolDefinition(
            name=_DECOMPOSER_TOOL_NAME,
            description=_DECOMPOSER_TOOL_DESCRIPTION,
            parameters_schema=_DECOMPOSER_TOOL_SCHEMA,
        )
        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=_DECOMPOSER_SYSTEM_PROMPT,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=self._build_user_prompt(criteria),
            ),
        ]
        return tool, messages

    async def _invoke_provider(
        self,
        messages: list[ChatMessage],
        tool: ToolDefinition,
    ) -> Any:
        """Invoke ``self._provider.complete`` with the decomposer config."""
        return await self._provider.complete(
            messages=messages,
            model=self._model_id,
            tools=[tool],
            config=CompletionConfig(temperature=0.0, max_tokens=2048),
        )

    def _extract_raw_probes(
        self,
        response: Any,
        *,
        task_id: NotBlankStr,
        agent_id: NotBlankStr,
    ) -> list[Any]:
        """Pull the ``probes`` list from the tool-call response or raise."""
        tool_call = next(
            (tc for tc in response.tool_calls if tc.name == _DECOMPOSER_TOOL_NAME),
            None,
        )
        if tool_call is None:
            logger.error(
                VERIFICATION_DECOMPOSER_RESPONSE_INVALID,
                task_id=task_id,
                agent_id=agent_id,
                decomposer=self.name,
                reason="no tool call",
                finish_reason=response.finish_reason.value,
            )
            msg = f"LLM decomposer response did not invoke {_DECOMPOSER_TOOL_NAME!r}"
            raise LLMDecompositionError(msg)

        raw_probes = tool_call.arguments.get("probes")
        if not isinstance(raw_probes, list):
            logger.error(
                VERIFICATION_DECOMPOSER_RESPONSE_INVALID,
                task_id=task_id,
                agent_id=agent_id,
                decomposer=self.name,
                reason="probes is not a list",
            )
            msg = "LLM decomposer response missing 'probes' list"
            raise LLMDecompositionError(msg)
        return raw_probes

    def _build_user_prompt(
        self,
        criteria: tuple[AcceptanceCriterion, ...],
    ) -> str:
        """Render criteria as an indexed list inside a JSON envelope.

        Individual criterion descriptions are truncated before JSON
        encoding so the resulting envelope is always syntactically
        valid, instructions are always preserved, and the final size
        fits ``_MAX_PROMPT_CRITERIA_CHARS``.  When truncation happens a
        ``VERIFICATION_DECOMPOSER_CRITERIA_TRUNCATED`` warning is logged
        so operators can spot runaway criteria lengths.
        """
        instructions = (
            "Call emit_atomic_probes with one array of probe "
            "objects.  Each probe references a criterion by its "
            "zero-based index and asks one yes/no question.  Emit "
            "at least one probe per criterion and at most "
            f"{self._max_probes_per_criterion} probes per criterion."
        )
        descriptions = [c.description for c in criteria]
        truncated_descriptions: list[str] = list(descriptions)

        def _encode(descs: list[str]) -> str:
            payload = {
                "criteria": [
                    {"index": i, "description": d} for i, d in enumerate(descs)
                ],
                "max_probes_per_criterion": self._max_probes_per_criterion,
                "instructions": instructions,
            }
            return json.dumps(payload, ensure_ascii=False)

        text = _encode(truncated_descriptions)
        if len(text) <= _MAX_PROMPT_CRITERIA_CHARS:
            return text

        # Proportionally trim each description; keep at least a short
        # stub so every criterion remains identifiable.
        overflow = len(text) - _MAX_PROMPT_CRITERIA_CHARS
        total_desc_chars = sum(len(d) for d in truncated_descriptions) or 1
        per_desc_cuts = [
            max(0, round(len(d) * overflow / total_desc_chars))
            for d in truncated_descriptions
        ]
        truncated_descriptions = [
            (d[: max(_MIN_CRITERION_DESC_CHARS, len(d) - cut)] if cut else d)
            for d, cut in zip(truncated_descriptions, per_desc_cuts, strict=True)
        ]
        text = _encode(truncated_descriptions)

        # If proportional trimming still overshoots, iteratively shrink
        # every description to fit the envelope.  Stop once each
        # description has reached ``_MIN_CRITERION_DESC_CHARS`` -- if the
        # payload is still oversized at that floor the prompt is
        # irreducible and we surface an explicit error rather than
        # returning oversized text.
        while len(text) > _MAX_PROMPT_CRITERIA_CHARS:
            at_minimum = all(
                len(d) <= _MIN_CRITERION_DESC_CHARS for d in truncated_descriptions
            )
            if at_minimum:
                msg = (
                    "LLM decomposer prompt cannot fit within "
                    f"{_MAX_PROMPT_CRITERIA_CHARS} chars even after "
                    "shrinking every criterion to "
                    f"{_MIN_CRITERION_DESC_CHARS} chars "
                    f"({len(criteria)} criteria)"
                )
                logger.error(
                    VERIFICATION_DECOMPOSER_CRITERIA_TRUNCATED,
                    decomposer=self.name,
                    reason="irreducible prompt",
                    criteria_count=len(criteria),
                    final_prompt_chars=len(text),
                    max_prompt_chars=_MAX_PROMPT_CRITERIA_CHARS,
                )
                raise LLMDecompositionError(msg)
            remaining = max(
                0,
                _MAX_PROMPT_CRITERIA_CHARS
                - (len(text) - sum(len(d) for d in truncated_descriptions)),
            )
            per_item_cap = max(
                _MIN_CRITERION_DESC_CHARS,
                remaining // max(1, len(truncated_descriptions)),
            )
            truncated_descriptions = [d[:per_item_cap] for d in truncated_descriptions]
            text = _encode(truncated_descriptions)

        truncated_indices = [
            i
            for i, (orig, new) in enumerate(
                zip(descriptions, truncated_descriptions, strict=True)
            )
            if orig != new
        ]
        logger.warning(
            VERIFICATION_DECOMPOSER_CRITERIA_TRUNCATED,
            decomposer=self.name,
            original_chars=len("".join(descriptions)),
            final_prompt_chars=len(text),
            max_prompt_chars=_MAX_PROMPT_CRITERIA_CHARS,
            truncated_criteria_indices=tuple(truncated_indices),
        )
        return text

    def _materialize_probes(
        self,
        raw_probes: list[Any],
        *,
        criteria: tuple[AcceptanceCriterion, ...],
        task_id: NotBlankStr,
        agent_id: NotBlankStr,
    ) -> tuple[AtomicProbe, ...]:
        """Validate probe dicts and build ``AtomicProbe`` instances.

        Args:
            raw_probes: Probe dicts as returned by the model.
            criteria: Original criteria (for index bounds and source text).
            task_id: Task identifier for deterministic probe IDs.
            agent_id: Agent identifier for log context.

        Returns:
            Validated tuple of ``AtomicProbe`` instances.

        Raises:
            LLMDecompositionError: If no valid probes remain after validation.
        """
        kept: list[AtomicProbe] = []
        per_criterion_counts: dict[int, int] = dict.fromkeys(range(len(criteria)), 0)
        for raw in raw_probes:
            if not isinstance(raw, dict):
                logger.warning(
                    VERIFICATION_DECOMPOSER_PROBE_REJECTED,
                    task_id=task_id,
                    agent_id=agent_id,
                    reason="not a dict",
                )
                continue
            index = raw.get("source_criterion_index")
            probe_text = raw.get("probe_text")
            if not isinstance(index, int) or not (0 <= index < len(criteria)):
                logger.warning(
                    VERIFICATION_DECOMPOSER_PROBE_REJECTED,
                    task_id=task_id,
                    agent_id=agent_id,
                    reason="index out of range",
                    index=index,
                )
                continue
            if not isinstance(probe_text, str) or not probe_text.strip():
                logger.warning(
                    VERIFICATION_DECOMPOSER_PROBE_REJECTED,
                    task_id=task_id,
                    agent_id=agent_id,
                    reason="blank probe_text",
                    index=index,
                )
                continue
            if per_criterion_counts[index] >= self._max_probes_per_criterion:
                logger.warning(
                    VERIFICATION_DECOMPOSER_PROBE_REJECTED,
                    task_id=task_id,
                    agent_id=agent_id,
                    reason="per-criterion cap reached",
                    index=index,
                )
                continue
            probe = AtomicProbe(
                id=f"{task_id}-probe-{len(kept)}",
                probe_text=probe_text.strip(),
                source_criterion=criteria[index].description,
            )
            kept.append(probe)
            per_criterion_counts[index] += 1

        if not kept:
            logger.error(
                VERIFICATION_DECOMPOSER_RESPONSE_INVALID,
                task_id=task_id,
                agent_id=agent_id,
                decomposer=self.name,
                reason="no valid probes after validation",
            )
            msg = "LLM decomposer produced no valid probes"
            raise LLMDecompositionError(msg)
        return tuple(kept)
