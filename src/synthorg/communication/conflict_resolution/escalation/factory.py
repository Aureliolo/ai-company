"""Factories for the escalation queue backend and decision processor (#1418)."""

from typing import TYPE_CHECKING

from synthorg.communication.conflict_resolution.escalation.config import (
    EscalationQueueConfig,  # noqa: TC001
)
from synthorg.communication.conflict_resolution.escalation.in_memory_store import (
    InMemoryEscalationStore,
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
            msg = "sqlite backend requires a SQLite persistence backend"
            raise ValueError(msg)
        db = getattr(persistence, "_db", None)
        if db is None:
            msg = (
                "sqlite backend requires an active aiosqlite.Connection "
                "on the persistence backend (is it connected?)"
            )
            raise ValueError(msg)
        from synthorg.persistence.sqlite.escalation_repo import (  # noqa: PLC0415
            SQLiteEscalationRepository,
        )

        return SQLiteEscalationRepository(db)
    if config.backend == "postgres":
        if persistence is None:
            msg = "postgres backend requires a Postgres persistence backend"
            raise ValueError(msg)
        pool = getattr(persistence, "_pool", None)
        if pool is None:
            msg = (
                "postgres backend requires an active psycopg_pool on the "
                "persistence backend (is it connected?)"
            )
            raise ValueError(msg)
        from synthorg.persistence.postgres.escalation_repo import (  # noqa: PLC0415
            PostgresEscalationRepository,
        )

        return PostgresEscalationRepository(pool)
    # Defensive: the Literal union is exhaustive today.
    msg = f"Unknown escalation queue backend: {config.backend!r}"  # type: ignore[unreachable]
    raise ValueError(msg)


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
