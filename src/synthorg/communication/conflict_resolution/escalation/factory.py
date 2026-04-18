"""Factories for the escalation queue backend and decision processor (#1418)."""

from typing import TYPE_CHECKING

from synthorg.communication.conflict_resolution.escalation.config import (
    EscalationQueueConfig,  # noqa: TC001
)
from synthorg.communication.conflict_resolution.escalation.in_memory_store import (
    InMemoryEscalationStore,
)
from synthorg.communication.conflict_resolution.escalation.notify import (
    EscalationNotifySubscriber,
    NoopEscalationNotifySubscriber,
)
from synthorg.communication.conflict_resolution.escalation.processors import (
    HybridDecisionProcessor,
    WinnerSelectProcessor,
)
from synthorg.communication.conflict_resolution.escalation.protocol import (
    DecisionProcessor,  # noqa: TC001
    EscalationQueueStore,  # noqa: TC001
)

if TYPE_CHECKING:
    from synthorg.communication.conflict_resolution.escalation.registry import (
        PendingFuturesRegistry,
    )
    from synthorg.persistence.protocol import PersistenceBackend


def build_escalation_queue_store(
    config: EscalationQueueConfig,
    persistence: PersistenceBackend | None = None,
) -> EscalationQueueStore:
    """Construct the configured :class:`EscalationQueueStore`.

    Args:
        config: Queue backend selection and tuning.
        persistence: Live persistence backend.  Required when
            ``config.backend`` is ``sqlite`` or ``postgres``.

    Returns:
        A concrete :class:`EscalationQueueStore` implementation.

    Raises:
        ValueError: ``backend`` is ``sqlite`` or ``postgres`` but the
            persistence backend is not compatible / not provided.
    """
    if config.backend == "memory":
        return InMemoryEscalationStore()
    if config.backend == "sqlite":
        if persistence is None:
            msg = "sqlite backend requires a connected persistence backend"
            raise ValueError(msg)
        return persistence.build_escalations()
    if config.backend == "postgres":
        if persistence is None:
            msg = "postgres backend requires a connected persistence backend"
            raise ValueError(msg)
        # Pass the notify channel only when cross-instance notify is
        # enabled so the repo's NOTIFY publishing is a true no-op for
        # single-worker deployments.
        notify_channel: str | None = None
        if config.cross_instance_notify in {"auto", "on"}:
            notify_channel = config.notify_channel
        return persistence.build_escalations(notify_channel=notify_channel)
    # Defensive: the Literal union is exhaustive today.
    msg = f"Unknown escalation queue backend: {config.backend!r}"  # type: ignore[unreachable]
    raise ValueError(msg)


def build_escalation_notify_subscriber(
    config: EscalationQueueConfig,
    store: EscalationQueueStore,
    registry: PendingFuturesRegistry,
) -> EscalationNotifySubscriber:
    """Construct the cross-instance notify subscriber for the queue.

    Returns a no-op subscriber unless the backend is Postgres and
    ``cross_instance_notify`` is enabled (``auto`` or ``on``).  The
    subscriber forwards state-transition NOTIFY payloads to the local
    :class:`PendingFuturesRegistry` so resolvers on other workers
    wake immediately instead of waiting for their timeout.

    Args:
        config: Queue configuration.
        store: The store built by :func:`build_escalation_queue_store`.
            When it is a ``PostgresEscalationRepository`` and
            ``cross_instance_notify`` is enabled, the subscriber reuses
            its pool for LISTEN.
        registry: Process-local future registry to signal.

    Returns:
        A concrete :class:`EscalationNotifySubscriber`.  Callers must
        ``await subscriber.start()`` during app startup and
        ``await subscriber.stop()`` during shutdown.

    Raises:
        ValueError: ``cross_instance_notify="on"`` but the backend is
            not Postgres -- surfaces misconfiguration at startup.
    """
    mode = config.cross_instance_notify
    if mode == "off":
        return NoopEscalationNotifySubscriber()
    if config.backend != "postgres":
        if mode == "on":
            msg = (
                "cross_instance_notify='on' requires backend='postgres'; "
                f"got backend={config.backend!r}."
            )
            raise ValueError(msg)
        return NoopEscalationNotifySubscriber()
    # Local import to avoid a hard dependency on psycopg when the
    # backend is not actually Postgres.
    from synthorg.communication.conflict_resolution.escalation.notify import (  # noqa: PLC0415
        PostgresEscalationNotifySubscriber,
    )
    from synthorg.persistence.postgres.escalation_repo import (  # noqa: PLC0415
        PostgresEscalationRepository,
    )

    if not isinstance(store, PostgresEscalationRepository):
        # Defensive: in principle factory-built stores and the backend
        # discriminator match; a mismatch means someone hand-injected
        # the store.
        return NoopEscalationNotifySubscriber()
    return PostgresEscalationNotifySubscriber(
        store,
        registry,
        channel=config.notify_channel,
    )


def build_decision_processor(
    config: EscalationQueueConfig,
) -> DecisionProcessor:
    """Construct the configured :class:`DecisionProcessor`.

    Args:
        config: Queue configuration.

    Returns:
        The concrete decision processor selected by
        ``config.decision_strategy``.
    """
    if config.decision_strategy == "winner":
        return WinnerSelectProcessor()
    if config.decision_strategy == "hybrid":
        return HybridDecisionProcessor()
    # Defensive: the Literal union is exhaustive today.
    msg = f"Unknown decision_strategy: {config.decision_strategy!r}"  # type: ignore[unreachable]
    raise ValueError(msg)
