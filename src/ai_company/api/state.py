"""Application state container.

Holds typed references to core services, injected into
``app.state`` at startup and accessed by controllers via
``request.app.state``.
"""

from dataclasses import dataclass

from ai_company.budget.tracker import CostTracker  # noqa: TC001
from ai_company.communication.bus_protocol import MessageBus  # noqa: TC001
from ai_company.config.schema import RootConfig  # noqa: TC001
from ai_company.persistence.protocol import PersistenceBackend  # noqa: TC001


@dataclass(frozen=True, slots=True)
class AppState:
    """Typed application state container.

    Service fields are typed as non-optional to keep controller code
    clean.  ``create_app()`` may pass ``None`` in dev/test mode
    (with ``type: ignore``); controllers accessing missing services
    will raise ``AttributeError``, caught by the global exception
    handler and returned as a 500 response.

    Attributes:
        config: Root company configuration.
        persistence: Persistence backend for data access.
        message_bus: Internal message bus.
        cost_tracker: Cost tracking service.
        startup_time: ``time.monotonic()`` snapshot at app creation.
    """

    config: RootConfig
    persistence: PersistenceBackend
    message_bus: MessageBus
    cost_tracker: CostTracker
    startup_time: float = 0.0
