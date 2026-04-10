"""Agent-driven intake strategy using a completion provider."""

import json
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from synthorg.client.models import (
    ClientRequest,  # noqa: TC001
    TaskRequirement,  # noqa: TC001
)
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.intake.models import IntakeResult
from synthorg.engine.task_engine_models import CreateTaskData
from synthorg.observability import get_logger
from synthorg.observability.events.review_pipeline import (
    INTAKE_AGENT_EMPTY_RESPONSE,
    INTAKE_AGENT_PARSE_FAILED,
    INTAKE_AGENT_REFINED_INVALID,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage

if TYPE_CHECKING:
    from synthorg.engine.task_engine import TaskEngine
    from synthorg.providers.protocol import CompletionProvider

logger = get_logger(__name__)


_DEFAULT_PERSONA = (
    "You are an intake manager evaluating client requests. For each "
    "request, decide whether it is ready to become a task. Respond "
    "with JSON only."
)


class AgentIntake:
    """Intake strategy that routes each request through an LLM.

    Builds a structured triage prompt, asks the provider for an
    accept/reject decision with an optional refined title and
    description, and either creates a task or returns a rejection
    with the model's reason. On parse or validation failure, the
    request is rejected with an explanatory reason so downstream
    state transitions remain deterministic.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        task_engine: TaskEngine,
        provider: CompletionProvider,
        model: NotBlankStr,
        project: NotBlankStr = "simulation",
        requested_by: NotBlankStr = "intake-agent",
        persona: str = _DEFAULT_PERSONA,
    ) -> None:
        """Initialize the agent intake strategy.

        Args:
            task_engine: Task engine used on acceptance.
            provider: Vendor-agnostic completion provider for the
                triage agent.
            model: Model identifier passed to the provider.
            project: Project stamped on created tasks.
            requested_by: Identity recorded as the task creator.
            persona: System prompt persona for the triage agent.
        """
        self._task_engine = task_engine
        self._provider = provider
        self._model = model
        self._project = project
        self._requested_by = requested_by
        self._persona = persona

    async def process(self, request: ClientRequest) -> IntakeResult:
        """Invoke the triage agent and create a task on acceptance."""
        messages = self._build_prompt(request.requirement)
        response = await self._provider.complete(
            messages=messages,
            model=self._model,
        )
        content = response.content
        if not content:
            logger.warning(
                INTAKE_AGENT_EMPTY_RESPONSE,
                request_id=request.request_id,
            )
            return IntakeResult.rejected_result(
                request_id=request.request_id,
                reason="intake agent returned empty response",
            )
        decision = self._parse_decision(content)
        if decision is None:
            reason = "intake agent returned malformed response"
            logger.warning(
                INTAKE_AGENT_PARSE_FAILED,
                request_id=request.request_id,
            )
            return IntakeResult.rejected_result(
                request_id=request.request_id,
                reason=reason,
            )
        accepted = decision.get("accepted")
        if not isinstance(accepted, bool):
            logger.warning(
                INTAKE_AGENT_PARSE_FAILED,
                request_id=request.request_id,
            )
            return IntakeResult.rejected_result(
                request_id=request.request_id,
                reason="intake agent returned malformed 'accepted' field",
            )
        if not accepted:
            reason = str(decision.get("reason") or "intake agent rejected request")
            return IntakeResult.rejected_result(
                request_id=request.request_id,
                reason=reason,
            )

        try:
            refined = self._refine_requirement(request.requirement, decision)
            data = self._build_task_data(refined)
        except ValidationError:
            logger.warning(
                INTAKE_AGENT_REFINED_INVALID,
                request_id=request.request_id,
            )
            return IntakeResult.rejected_result(
                request_id=request.request_id,
                reason="refined requirement failed validation",
            )
        task = await self._task_engine.create_task(
            data,
            requested_by=self._requested_by,
        )
        return IntakeResult.accepted_result(
            request_id=request.request_id,
            task_id=task.id,
        )

    def _build_prompt(self, requirement: TaskRequirement) -> list[ChatMessage]:
        user = (
            "Review this client request and decide if it should "
            "become a task.\n\n"
            f"Title: {requirement.title}\n"
            f"Description: {requirement.description}\n"
            f"Type: {requirement.task_type.value}\n"
            f"Priority: {requirement.priority.value}\n"
            f"Complexity: {requirement.estimated_complexity.value}\n\n"
            "Return JSON only, with these keys:\n"
            "  accepted: boolean\n"
            "  reason: string (required when rejected)\n"
            "  refined_title: optional string\n"
            "  refined_description: optional string"
        )
        return [
            ChatMessage(role=MessageRole.SYSTEM, content=self._persona),
            ChatMessage(role=MessageRole.USER, content=user),
        ]

    @staticmethod
    def _parse_decision(content: str) -> dict[str, Any] | None:
        stripped = content.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start == -1 or end == -1 or end < start:
                return None
            try:
                parsed = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    @staticmethod
    def _refine_requirement(
        original: TaskRequirement,
        decision: dict[str, Any],
    ) -> TaskRequirement:
        refined_title = decision.get("refined_title")
        refined_description = decision.get("refined_description")
        if not refined_title and not refined_description:
            return original
        payload = original.model_dump()
        payload.update(
            {
                "title": refined_title or original.title,
                "description": (refined_description or original.description),
            },
        )
        return type(original).model_validate(payload)

    def _build_task_data(self, requirement: TaskRequirement) -> CreateTaskData:
        return CreateTaskData(
            title=requirement.title,
            description=requirement.description,
            type=requirement.task_type,
            priority=requirement.priority,
            project=self._project,
            created_by=self._requested_by,
            estimated_complexity=requirement.estimated_complexity,
        )
