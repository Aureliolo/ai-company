"""LLM-backed requirement generator."""

import json
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from synthorg.client.models import GenerationContext, TaskRequirement
from synthorg.core.enums import Complexity, Priority, TaskType
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.prompt_safety import (
    TAG_TASK_DATA,
    untrusted_content_directive,
    wrap_untrusted,
)
from synthorg.observability import get_logger
from synthorg.observability.events.client import CLIENT_REQUIREMENT_GENERATED
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage, CompletionConfig
from synthorg.providers.protocol import CompletionProvider  # noqa: TC001

logger = get_logger(__name__)


_DEFAULT_PERSONA = (
    "You are a product manager drafting concrete, testable task "
    "requirements for an engineering team. Return machine-readable "
    "JSON only, never prose.\n\n" + untrusted_content_directive((TAG_TASK_DATA,))
)


class LLMGenerator:
    """Generates requirements via any ``CompletionProvider``.

    Vendor-agnostic: accepts a pluggable provider at construction
    time. Builds a structured JSON prompt from the generation
    context, parses the provider response into ``TaskRequirement``
    instances. On parse or validation failure, logs a warning and
    returns an empty tuple -- provider exceptions (network, rate
    limit, etc.) propagate so the base retry/rate-limit logic can
    handle them uniformly.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model: NotBlankStr,
        persona: str = _DEFAULT_PERSONA,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        """Initialize the LLM generator.

        Args:
            provider: Vendor-agnostic completion provider.
            model: Model identifier passed to the provider.
            persona: System prompt persona for the generator. If a
                caller supplies a custom persona, they own its prompt-
                safety posture -- the default persona already carries
                the SEC-1 ``untrusted_content_directive``.
            temperature: Sampling temperature (default 0.7 -- creative
                requirement generation benefits from variety; pin to
                0.0 for reproducible eval runs).
            max_tokens: Maximum tokens in the completion response.
        """
        self._provider = provider
        self._model = model
        self._persona = persona
        # SEC-1 fingerprint: pin temperature + max_tokens so test suites
        # can assert a stable call shape across provider-default changes.
        self._completion_config = CompletionConfig(
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate(
        self,
        context: GenerationContext,
    ) -> tuple[TaskRequirement, ...]:
        """Ask the provider for requirements and parse the response.

        Args:
            context: Generation context passed into the prompt.

        Returns:
            Tuple of validated requirements; empty if the provider
            response cannot be parsed into valid requirements.
        """
        messages = self._build_prompt(context)
        response = await self._provider.complete(
            messages=messages,
            model=self._model,
            config=self._completion_config,
        )
        content = response.content or ""
        payload = self._extract_json_array(content)
        if payload is None:
            logger.warning(
                CLIENT_REQUIREMENT_GENERATED,
                strategy="llm",
                error="no JSON array found in response",
            )
            return ()

        requirements: list[TaskRequirement] = []
        for item in payload:
            try:
                requirements.append(self._to_requirement(item))
            except (KeyError, ValueError, TypeError, ValidationError) as exc:
                logger.warning(
                    CLIENT_REQUIREMENT_GENERATED,
                    strategy="llm",
                    skipped=True,
                    error=str(exc),
                )
        logger.debug(
            CLIENT_REQUIREMENT_GENERATED,
            strategy="llm",
            generated=len(requirements),
            domain=context.domain,
        )
        return tuple(requirements)

    def _build_prompt(
        self,
        context: GenerationContext,
    ) -> list[ChatMessage]:
        allowed = ", ".join(c.value for c in context.complexity_range)
        # SEC-1 / audit 92: ``domain`` and ``project_id`` are caller-
        # supplied strings that reach the model verbatim.  Wrap them in
        # the ``<task-data>`` fence declared by ``_DEFAULT_PERSONA``.
        fenced_domain = wrap_untrusted(TAG_TASK_DATA, context.domain)
        fenced_project = wrap_untrusted(TAG_TASK_DATA, context.project_id)
        user = (
            f"Generate {context.count} task requirements for the "
            f"{fenced_domain} area of project {fenced_project}.\n\n"
            "Each requirement must include: title, description, "
            "task_type, priority, estimated_complexity, "
            "acceptance_criteria.\n"
            f"Allowed complexity levels: {allowed}.\n"
            "Return ONLY a JSON array of requirement objects."
        )
        return [
            ChatMessage(role=MessageRole.SYSTEM, content=self._persona),
            ChatMessage(role=MessageRole.USER, content=user),
        ]

    @staticmethod
    def _extract_json_array(content: str) -> list[dict[str, Any]] | None:
        stripped = content.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("[")
            end = stripped.rfind("]")
            if start == -1 or end == -1 or end < start:
                return None
            try:
                parsed = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                return None
        if not isinstance(parsed, list):
            return None
        return [item for item in parsed if isinstance(item, dict)]

    @staticmethod
    def _to_requirement(item: dict[str, Any]) -> TaskRequirement:
        return TaskRequirement(
            title=item["title"],
            description=item["description"],
            task_type=TaskType(item.get("task_type", "development")),
            priority=Priority(item.get("priority", "medium")),
            estimated_complexity=Complexity(
                item.get("estimated_complexity", "medium"),
            ),
            acceptance_criteria=_normalize_criteria(
                item.get("acceptance_criteria"),
            ),
        )


def _normalize_criteria(raw: object) -> tuple[str, ...]:
    """Coerce acceptance_criteria to a string tuple."""
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Sequence):
        return tuple(str(c) for c in raw)
    return ()
