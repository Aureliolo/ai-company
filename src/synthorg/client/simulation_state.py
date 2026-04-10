"""Consolidated runtime state for client simulation.

Wraps the in-memory pool, request store, simulation store,
intake engine, and review pipeline in a single object so the API
layer has a stable attachment point on ``AppState``.
"""

from dataclasses import dataclass, field

from synthorg.client.pool import ClientPool
from synthorg.client.store import FeedbackStore, RequestStore, SimulationStore
from synthorg.engine.intake.engine import IntakeEngine  # noqa: TC001
from synthorg.engine.review.pipeline import ReviewPipeline  # noqa: TC001


@dataclass
class ClientSimulationState:
    """Runtime container for the client simulation subsystem.

    Attributes:
        pool: Mutable client pool shared by controllers and runner.
        request_store: In-memory request lifecycle store.
        simulation_store: In-memory simulation run records.
        feedback_store: Per-client review history for satisfaction.
        intake_engine: Intake engine used by ``/requests/{id}/approve``.
        review_pipeline: Review pipeline surfaced to ``/reviews/...``.
    """

    pool: ClientPool = field(default_factory=ClientPool)
    request_store: RequestStore = field(default_factory=RequestStore)
    simulation_store: SimulationStore = field(default_factory=SimulationStore)
    feedback_store: FeedbackStore = field(default_factory=FeedbackStore)
    intake_engine: IntakeEngine | None = None
    review_pipeline: ReviewPipeline | None = None
