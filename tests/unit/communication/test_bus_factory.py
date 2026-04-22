"""Unit tests for the message bus backend factory.

Covers dispatch logic in :func:`build_message_bus` and the
``MessageBusConfig`` validator that requires a ``nats`` sub-block
when ``backend == NATS``. Does not require a live NATS server.
"""

import pytest

from synthorg.communication.bus import build_message_bus
from synthorg.communication.bus.memory import InMemoryMessageBus
from synthorg.communication.bus.nats import JetStreamMessageBus
from synthorg.communication.config import MessageBusConfig, NatsConfig
from synthorg.communication.enums import MessageBusBackend


@pytest.mark.unit
def test_factory_returns_in_memory_for_internal_backend() -> None:
    config = MessageBusConfig(backend=MessageBusBackend.INTERNAL)
    bus = build_message_bus(config)
    assert isinstance(bus, InMemoryMessageBus)


@pytest.mark.unit
def test_factory_returns_jetstream_for_nats_backend() -> None:
    config = MessageBusConfig(
        backend=MessageBusBackend.NATS,
        nats=NatsConfig(url="nats://localhost:4222"),
    )
    bus = build_message_bus(config)
    assert isinstance(bus, JetStreamMessageBus)


@pytest.mark.unit
def test_nats_backend_requires_nats_config() -> None:
    """MessageBusConfig validator rejects backend=nats without nats block."""
    with pytest.raises(ValueError, match="nats must be provided"):
        MessageBusConfig(backend=MessageBusBackend.NATS)


@pytest.mark.unit
def test_nats_config_ignored_when_backend_is_internal() -> None:
    """A NatsConfig is allowed but ignored when backend=internal."""
    config = MessageBusConfig(
        backend=MessageBusBackend.INTERNAL,
        nats=NatsConfig(url="nats://localhost:4222"),
    )
    bus = build_message_bus(config)
    assert isinstance(bus, InMemoryMessageBus)


@pytest.mark.unit
def test_jetstream_constructor_requires_nats_config() -> None:
    """JetStreamMessageBus raises ValueError if nats config missing.

    The MessageBusConfig validator usually catches this first, but
    the direct-constructor path is still defensive against misuse.
    """
    # Bypass the validator by constructing with model_construct (skips
    # validation) so we can exercise the constructor's own check.
    bare = MessageBusConfig.model_construct(
        backend=MessageBusBackend.NATS,
        channels=("#general",),
        nats=None,
    )
    with pytest.raises(ValueError, match=r"requires config\.nats"):
        JetStreamMessageBus(config=bare)
