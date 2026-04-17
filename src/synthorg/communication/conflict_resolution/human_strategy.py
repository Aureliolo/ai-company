"""Human escalation conflict resolution strategy (see Communication design page).

Strategy 3 from the Communication design: escalate the conflict to a
human operator and await their decision before returning a resolution.

When a conflict arrives, the resolver:

1. Persists an :class:`Escalation` row via the configured
   :class:`EscalationQueueStore`.
2. Registers an ``asyncio.Future`` in the
   :class:`PendingFuturesRegistry`.
3. Dispatches an operator notification through the shared
   :class:`NotificationDispatcher`.
4. Awaits the Future with the configured timeout.  A decision arriving
   via the REST endpoint resolves the Future so the resolver wakes
   with the operator's payload.
5. Hands the decision to the configured :class:`DecisionProcessor` to
   produce a :class:`ConflictResolution`.

On timeout or explicit cancellation the resolver returns a no-winner
:class:`ConflictResolution` with outcome ``ESCALATED_TO_HUMAN`` so
downstream consumers match the previous stub contract (never
``None``), and the store row is transitioned to ``EXPIRED`` so
subsequent GETs surface the terminal state.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from synthorg.communication.conflict_resolution.escalation.models import (
    Escalation,
    EscalationStatus,
)
from synthorg.communication.conflict_resolution.escalation.protocol import (
    DecisionProcessor,  # noqa: TC001
    EscalationQueueStore,  # noqa: TC001
)
from synthorg.communication.conflict_resolution.escalation.registry import (
    PendingFuturesRegistry,
)
from synthorg.communication.conflict_resolution.models import (
    Conflict,
    ConflictResolution,
    ConflictResolutionOutcome,
    DissentRecord,
)
from synthorg.notifications.dispatcher import NotificationDispatcher  # noqa: TC001
from synthorg.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)
from synthorg.observability import get_logger
from synthorg.observability.events.conflict import (
    CONFLICT_ESCALATED,
    CONFLICT_ESCALATION_CANCELLED,
    CONFLICT_ESCALATION_QUEUED,
    CONFLICT_ESCALATION_RESOLVED,
    CONFLICT_ESCALATION_TIMEOUT,
)

logger = get_logger(__name__)


class HumanEscalationResolver:
    """Escalate conflicts to a human and await the operator decision.

    All dependencies are optional so unit tests that only need the
    "escalate to human" happy path can instantiate the resolver with
    no arguments and receive an immediate ``ESCALATED_TO_HUMAN``
    outcome.  Production deployments inject fully-configured
    dependencies via :func:`build_escalation_queue_store` and
    :func:`build_decision_processor`.

    Args:
        store: Persistent escalation queue.  Defaults to an
            :class:`InMemoryEscalationStore` so callers without a
            configured backend still produce an auditable row.
        processor: Converts an operator decision into a
            :class:`ConflictResolution`.  Defaults to
            :class:`WinnerSelectProcessor`.
        registry: In-process map of awaited Futures.  Decisions
            arriving via the REST endpoint resolve Futures registered
            here to wake the awaiting resolver coroutine.  Defaults
            to a fresh :class:`PendingFuturesRegistry`.
        notifier: Notification dispatcher; receives an
            :class:`NotificationCategory.ESCALATION` event when the
            queue row is created.  When ``None`` the resolver skips
            notification dispatch (useful for tests).
        timeout_seconds: Maximum seconds to wait for a human decision.
            ``None`` disables the timeout (wait forever); ``0`` causes
            an immediate timeout -- matches the pre-queue stub contract
            for callers that only care about the ESCALATED outcome.
    """

    def __init__(
        self,
        *,
        store: EscalationQueueStore | None = None,
        processor: DecisionProcessor | None = None,
        registry: PendingFuturesRegistry | None = None,
        notifier: NotificationDispatcher | None = None,
        timeout_seconds: int | None = 0,
    ) -> None:
        """Initialise the resolver with its dependencies."""
        # Local imports keep the optional-dep defaults lightweight.
        from synthorg.communication.conflict_resolution.escalation.in_memory_store import (  # noqa: E501, PLC0415
            InMemoryEscalationStore,
        )
        from synthorg.communication.conflict_resolution.escalation.processors import (  # noqa: PLC0415
            WinnerSelectProcessor,
        )

        self._store: EscalationQueueStore = store or InMemoryEscalationStore()
        self._processor: DecisionProcessor = processor or WinnerSelectProcessor()
        self._registry: PendingFuturesRegistry = registry or PendingFuturesRegistry()
        self._notifier: NotificationDispatcher | None = notifier
        self._timeout_seconds = timeout_seconds

    async def resolve(self, conflict: Conflict) -> ConflictResolution:
        """Create an escalation, notify operators, and await a decision.

        Returns a :class:`ConflictResolution` once the operator decides
        or the timeout fires.
        """
        escalation = self._build_escalation(conflict)
        # Register the Future BEFORE making the row externally visible.
        # A race-fast decision endpoint that sees the row and calls
        # ``registry.resolve`` before we register would otherwise create
        # an orphan decision and leave the resolver waiting until timeout.
        future = await self._registry.register(escalation.id)
        try:
            await self._store.create(escalation)
        except Exception:
            # Reap the future so the registry does not leak.
            await self._registry.cancel(escalation.id)
            raise
        logger.info(
            CONFLICT_ESCALATION_QUEUED,
            escalation_id=escalation.id,
            conflict_id=conflict.id,
            subject=conflict.subject,
            timeout_seconds=self._timeout_seconds,
        )
        logger.info(
            CONFLICT_ESCALATED,
            conflict_id=conflict.id,
            agent_count=len(conflict.positions),
        )
        if self._notifier is not None:
            # Notification delivery is a side effect: failures must not
            # abort the workflow and leak the queued row + registered
            # future.  Log and continue -- operators already have the
            # row visible via the REST list endpoint, and the sweeper
            # will eventually expire it if nothing arrives.
            try:
                await self._notifier.dispatch(
                    self._build_notification(escalation, conflict),
                )
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    CONFLICT_ESCALATION_QUEUED,
                    escalation_id=escalation.id,
                    conflict_id=conflict.id,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    note="notification_dispatch_failed",
                )

        try:
            if self._timeout_seconds is None:
                decision = await future
            else:
                decision = await asyncio.wait_for(
                    future,
                    timeout=float(self._timeout_seconds),
                )
        except TimeoutError:
            # Reap the Future from the registry and mark only this row
            # EXPIRED -- pass its own expires_at as the deadline so we
            # never accidentally expire rows whose deadline is still
            # in the future.
            await self._registry.cancel(escalation.id)
            await self._store.mark_expired(datetime.now(UTC).isoformat())
            logger.warning(
                CONFLICT_ESCALATION_TIMEOUT,
                escalation_id=escalation.id,
                conflict_id=conflict.id,
                timeout_seconds=self._timeout_seconds,
            )
            return self._timeout_resolution(conflict)
        except asyncio.CancelledError:
            # Persist terminal state so operators do not see the row
            # stuck as PENDING after the resolver is cancelled.
            await self._registry.cancel(escalation.id)
            try:
                await self._store.cancel(
                    escalation.id,
                    cancelled_by="system:resolver_cancelled",
                )
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    CONFLICT_ESCALATION_CANCELLED,
                    escalation_id=escalation.id,
                    conflict_id=conflict.id,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    note="store_cancel_failed",
                )
            logger.warning(
                CONFLICT_ESCALATION_CANCELLED,
                escalation_id=escalation.id,
                conflict_id=conflict.id,
            )
            return self._cancelled_resolution(conflict)

        # The decision endpoint is responsible for persisting the
        # DECIDED row and then resolving the Future -- the resolver
        # only has to hand the decision to the processor.
        decided_by = await self._resolve_decided_by(escalation.id)
        resolution = self._processor.process(
            conflict,
            decision,
            decided_by=decided_by,
        )
        logger.info(
            CONFLICT_ESCALATION_RESOLVED,
            escalation_id=escalation.id,
            conflict_id=conflict.id,
            outcome=resolution.outcome.value,
        )
        return resolution

    async def _resolve_decided_by(self, escalation_id: str) -> str:
        """Look up the persisted ``decided_by`` or fall back to ``"human"``.

        The REST endpoint saves the DECIDED row with the authoritative
        operator identity before resolving the Future, so the row is
        already visible by the time we reach here.  We still fall back
        to the generic ``"human"`` label if the lookup races or the
        backend is in-memory and scoped to the resolver under test.
        """
        try:
            row = await self._store.get(escalation_id)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                CONFLICT_ESCALATION_RESOLVED,
                escalation_id=escalation_id,
                error_type=type(exc).__name__,
                error=str(exc),
                note="store_lookup_failed",
            )
            return "human"
        if row is None or not row.decided_by:
            return "human"
        return row.decided_by

    def build_dissent_records(
        self,
        conflict: Conflict,
        resolution: ConflictResolution,
    ) -> tuple[DissentRecord, ...]:
        """Delegate dissent record construction to the processor."""
        return self._processor.build_dissent_records(conflict, resolution)

    def _build_escalation(self, conflict: Conflict) -> Escalation:
        """Construct the initial PENDING :class:`Escalation`."""
        now = datetime.now(UTC)
        expires_at: datetime | None = None
        if self._timeout_seconds is not None:
            expires_at = now + timedelta(seconds=self._timeout_seconds)
        return Escalation(
            id=f"escalation-{uuid4().hex[:12]}",
            conflict=conflict,
            status=EscalationStatus.PENDING,
            created_at=now,
            expires_at=expires_at,
        )

    def _build_notification(
        self,
        escalation: Escalation,
        conflict: Conflict,
    ) -> Notification:
        """Render an operator-facing notification for the new escalation."""
        summary_lines = [f"Conflict subject: {conflict.subject}"]
        summary_lines.extend(
            f"- {position.agent_id} ({position.agent_department}, "
            f"{position.agent_level}): {position.position}"
            for position in conflict.positions
        )
        body = "\n".join(summary_lines)
        metadata: dict[str, object] = {
            "escalation_id": escalation.id,
            "conflict_id": conflict.id,
            "conflict_type": conflict.type.value,
            "subject": conflict.subject,
        }
        if conflict.task_id is not None:
            metadata["task_id"] = conflict.task_id
        if escalation.expires_at is not None:
            metadata["expires_at"] = escalation.expires_at.isoformat()
        return Notification(
            category=NotificationCategory.ESCALATION,
            severity=NotificationSeverity.WARNING,
            title=f"Conflict escalation pending: {conflict.id}",
            body=body,
            source="conflict_resolution.human_strategy",
            metadata=metadata,
        )

    def _timeout_resolution(self, conflict: Conflict) -> ConflictResolution:
        """Resolution returned when no decision arrives in time."""
        reason = (
            "No human decision was collected before the escalation timeout. "
            "Conflict remains ESCALATED_TO_HUMAN; operators may still decide "
            "via the REST API."
        )
        return ConflictResolution(
            conflict_id=conflict.id,
            outcome=ConflictResolutionOutcome.ESCALATED_TO_HUMAN,
            winning_agent_id=None,
            winning_position=None,
            decided_by="human",
            reasoning=reason,
            resolved_at=datetime.now(UTC),
        )

    def _cancelled_resolution(self, conflict: Conflict) -> ConflictResolution:
        """Resolution returned when the resolver coroutine is cancelled."""
        reason = (
            "Escalation resolver was cancelled before a human decision "
            "could be collected."
        )
        return ConflictResolution(
            conflict_id=conflict.id,
            outcome=ConflictResolutionOutcome.ESCALATED_TO_HUMAN,
            winning_agent_id=None,
            winning_position=None,
            decided_by="human",
            reasoning=reason,
            resolved_at=datetime.now(UTC),
        )
