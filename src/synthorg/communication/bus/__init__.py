"""Message bus backend package.

Exposes the concrete backends and a :func:`build_message_bus` factory
that picks the right implementation based on
``MessageBusConfig.backend``. Callers that need a specific backend
can import it directly.

See ``docs/design/distributed-runtime.md`` for the overall design.
"""

from synthorg.communication.bus.memory import InMemoryMessageBus
from synthorg.communication.bus_protocol import MessageBus
from synthorg.communication.config import MessageBusConfig  # noqa: TC001
from synthorg.communication.enums import MessageBusBackend
from synthorg.observability import get_logger
from synthorg.observability.events.config import CONFIG_VALIDATION_FAILED

logger = get_logger(__name__)

__all__ = (
    "InMemoryMessageBus",
    "MessageBus",
    "build_message_bus",
)


def build_message_bus(config: MessageBusConfig) -> MessageBus:
    """Build the concrete ``MessageBus`` for the given configuration.

    The factory pattern-matches on ``config.backend`` and returns the
    matching implementation. Optional dependencies for distributed
    backends are imported lazily so a default (internal) deployment
    does not need them installed.

    Args:
        config: Message bus configuration.

    Returns:
        A concrete ``MessageBus`` instance (not started).

    Raises:
        ValueError: If ``config.backend`` names an implementation
            that is documented but not yet implemented (Redis,
            RabbitMQ, Kafka).
        ImportError: If the selected backend requires an optional
            dependency that is not installed (e.g. ``nats-py`` for
            the NATS backend).
    """
    match config.backend:
        case MessageBusBackend.INTERNAL:
            return InMemoryMessageBus(config=config)
        case MessageBusBackend.NATS:
            from synthorg.communication.bus.nats import (  # noqa: PLC0415
                JetStreamMessageBus,
            )

            return JetStreamMessageBus(config=config)
        case (
            MessageBusBackend.REDIS
            | MessageBusBackend.RABBITMQ
            | MessageBusBackend.KAFKA
        ):
            msg = (
                f"MessageBus backend '{config.backend.value}' is documented "
                f"as a future backend but not yet implemented. See "
                f"docs/design/distributed-runtime.md. Supported backends: "
                f"'internal', 'nats'."
            )
            logger.error(
                CONFIG_VALIDATION_FAILED,
                model="MessageBusConfig",
                backend=config.backend.value,
                reason="future_backend_not_implemented",
            )
            raise ValueError(msg)
        case _:
            # Defensive catch-all: any future MessageBusBackend member
            # that is not wired up above should fail loudly at startup
            # rather than silently skipping auto-wire. Mypy sees this
            # branch as unreachable because the preceding cases exhaust
            # the enum, but the catch-all intentionally guards against
            # forgetting to update this factory when a new member is
            # added to MessageBusBackend.
            msg = (  # type: ignore[unreachable]
                f"Unknown MessageBus backend {config.backend!r}. "
                "The factory has not been updated for this enum member; "
                "add a new case to build_message_bus()."
            )
            logger.error(
                CONFIG_VALIDATION_FAILED,
                model="MessageBusConfig",
                backend=repr(config.backend),
                reason="unknown_backend_factory_not_updated",
            )
            raise ValueError(msg)
