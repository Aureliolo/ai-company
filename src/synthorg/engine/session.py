"""Stateless session replay from observability event log.

Reconstructs an ``AgentContext`` from the structured event stream
recorded during a previous execution.  This is a lighter-weight
alternative to full checkpoint/resume: read-only reconstruction
that enables brain-failure recovery without persistence dependencies.

Terminology follows the Anthropic managed-agents engineering post:

- **Brain**: inference loop (``harness.py``, ``AgentContext``, loop protocol)
- **Hands**: tool execution (``ToolInvoker``, ``tools/sandbox/``, credential proxy)
- **Session**: durable event history (``observability/events/``, replay)
"""

import copy
from typing import Any, Protocol, runtime_checkable

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from synthorg.core.agent import AgentIdentity  # noqa: TC001
from synthorg.core.task import Task  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.engine.context import DEFAULT_MAX_TURNS, AgentContext
from synthorg.observability import get_logger
from synthorg.observability.events.execution import (
    EXECUTION_CONTEXT_CREATED,
    EXECUTION_CONTEXT_TURN,
    EXECUTION_ENGINE_START,
    EXECUTION_TASK_TRANSITION,
)
from synthorg.observability.events.session import (
    SESSION_REPLAY_COMPLETE,
    SESSION_REPLAY_ERROR,
    SESSION_REPLAY_NO_EVENTS,
    SESSION_REPLAY_PARTIAL,
    SESSION_REPLAY_START,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage, TokenUsage

logger = get_logger(__name__)

_COMPLETENESS_THRESHOLD: float = 0.85
"""Replay completeness at or above which the replay is considered full."""


# ── Models ────────────────────────────────────────────────────────


class SessionEvent(BaseModel):
    """A single event from the observability event log.

    Attributes:
        event_name: Dotted event constant (e.g. ``"execution.context.turn"``).
        timestamp: When the event was recorded.
        execution_id: Execution run this event belongs to.
        data: Structured event payload (deep-copied at construction).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    event_name: str = Field(description="Dotted event constant")
    timestamp: AwareDatetime = Field(description="Event timestamp")
    execution_id: NotBlankStr = Field(
        description="Execution run this event belongs to",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured event payload",
    )

    @model_validator(mode="after")
    def _deepcopy_data(self) -> SessionEvent:
        """Defensive copy so callers cannot mutate the frozen model."""
        object.__setattr__(self, "data", copy.deepcopy(self.data))
        return self


class ReplayResult(BaseModel):
    """Result of a session replay attempt.

    Attributes:
        context: Reconstructed agent context (may be partial).
        replay_completeness: Fraction of expected state recovered
            (0.0 = nothing, 1.0 = everything).
        events_processed: Number of events consumed during replay.
        events_total: Total events found for this execution.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    context: AgentContext = Field(
        description="Reconstructed agent context",
    )
    replay_completeness: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of expected state recovered",
    )
    events_processed: int = Field(
        ge=0,
        description="Events consumed during replay",
    )
    events_total: int = Field(
        ge=0,
        description="Total events found for this execution",
    )


# ── Protocol ──────────────────────────────────────────────────────


@runtime_checkable
class EventReader(Protocol):
    """Read observability events by execution ID.

    Concrete implementations may read from structured log files,
    OTLP backends, or the Postgres ``observability_events`` table.
    """

    async def read_events(
        self,
        execution_id: str,
    ) -> tuple[SessionEvent, ...]:
        """Return events for the given execution, ordered by timestamp."""
        ...


# ── Session replay ────────────────────────────────────────────────


class Session:
    """Stateless session replay from the observability event log.

    Provides ``replay()`` to reconstruct an ``AgentContext`` from
    the event stream of a previous (possibly crashed) execution.
    """

    @staticmethod
    async def replay(
        *,
        execution_id: str,
        event_reader: EventReader,
        identity: AgentIdentity,
        task: Task | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> ReplayResult:
        """Reconstruct an ``AgentContext`` from the event log.

        Best-effort: if the event stream is incomplete, returns a
        partial context with ``replay_completeness < 1.0``.

        Args:
            execution_id: The execution to replay.
            event_reader: Source of observability events.
            identity: Agent identity for the reconstructed context.
            task: Optional task to bind to the context.
            max_turns: Maximum turns for the reconstructed context.

        Returns:
            ``ReplayResult`` with the reconstructed context and
            completeness score.
        """
        logger.info(
            SESSION_REPLAY_START,
            execution_id=execution_id,
            agent_id=str(identity.id),
        )

        try:
            events = await event_reader.read_events(execution_id)
        except Exception:
            logger.exception(
                SESSION_REPLAY_ERROR,
                execution_id=execution_id,
                reason="failed to read events",
            )
            raise

        if not events:
            logger.info(
                SESSION_REPLAY_NO_EVENTS,
                execution_id=execution_id,
            )
            ctx = AgentContext.from_identity(
                identity,
                task=task,
                max_turns=max_turns,
            )
            return ReplayResult(
                context=ctx,
                replay_completeness=0.0,
                events_processed=0,
                events_total=0,
            )

        sorted_events = sorted(events, key=lambda e: e.timestamp)
        return _replay_from_events(
            sorted_events=sorted_events,
            identity=identity,
            task=task,
            max_turns=max_turns,
            execution_id=execution_id,
        )


# ── Internal replay logic ─────────────────────────────────────────


def _replay_from_events(
    *,
    sorted_events: list[SessionEvent],
    identity: AgentIdentity,
    task: Task | None,
    max_turns: int,
    execution_id: str,
) -> ReplayResult:
    """Walk sorted events and reconstruct AgentContext."""
    ctx = AgentContext.from_identity(
        identity,
        task=task,
        max_turns=max_turns,
    )

    # Tracking for completeness scoring.
    found_engine_start = False
    found_context_created = False
    turn_numbers: list[int] = []
    total_cost = 0.0
    found_transition = False
    processed = 0

    for event in sorted_events:
        try:
            processed += 1
            name = event.event_name

            if name == EXECUTION_ENGINE_START:
                found_engine_start = True

            elif name == EXECUTION_CONTEXT_CREATED:
                found_context_created = True

            elif name == EXECUTION_CONTEXT_TURN:
                turn = event.data.get("turn", 0)
                cost_usd = float(event.data.get("cost_usd", 0.0))
                turn_numbers.append(int(turn))
                total_cost += cost_usd

                usage = TokenUsage(
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=cost_usd,
                )
                replay_msg = ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=f"[replayed turn {turn}]",
                )
                ctx = ctx.with_turn_completed(usage, replay_msg)

            elif name == EXECUTION_TASK_TRANSITION:
                found_transition = True

        except Exception:
            logger.warning(
                SESSION_REPLAY_ERROR,
                execution_id=execution_id,
                event_name=event.event_name,
                reason="failed to process event",
            )

    completeness = _compute_completeness(
        found_engine_start=found_engine_start,
        found_context_created=found_context_created,
        turn_numbers=turn_numbers,
        total_cost=total_cost,
        found_transition=found_transition,
    )

    event_name = (
        SESSION_REPLAY_COMPLETE
        if completeness >= _COMPLETENESS_THRESHOLD
        else SESSION_REPLAY_PARTIAL
    )
    logger.info(
        event_name,
        execution_id=execution_id,
        replay_completeness=completeness,
        turns_replayed=len(turn_numbers),
        events_processed=processed,
    )

    return ReplayResult(
        context=ctx,
        replay_completeness=completeness,
        events_processed=processed,
        events_total=len(sorted_events),
    )


def _compute_completeness(
    *,
    found_engine_start: bool,
    found_context_created: bool,
    turn_numbers: list[int],
    total_cost: float,
    found_transition: bool,
) -> float:
    """Compute replay completeness as a weighted score.

    Weights:
        Engine start event:          0.15
        Context created event:       0.10
        At least one turn event:     0.20
        Contiguous turn sequence:    0.25
        Cost data in turn events:    0.15
        Task transition events:      0.15
    """
    score = 0.0

    if found_engine_start:
        score += 0.15
    if found_context_created:
        score += 0.10
    if turn_numbers:
        score += 0.20
        # Check contiguity: turns should be 1, 2, 3, ...
        expected = list(range(1, len(turn_numbers) + 1))
        if sorted(turn_numbers) == expected:
            score += 0.25
    if total_cost > 0.0:
        score += 0.15
    if found_transition:
        score += 0.15

    return min(score, 1.0)
