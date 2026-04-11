"""Fixtures for integration tests of the integrations subsystem."""

import pytest

from synthorg.communication.bus.memory import InMemoryMessageBus
from synthorg.communication.config import MessageBusConfig


@pytest.fixture
async def memory_bus() -> InMemoryMessageBus:
    """Create and start an InMemoryMessageBus with integration channels."""
    config = MessageBusConfig(
        channels=(
            "#webhooks",
            "#ratelimit",
        ),
    )
    bus = InMemoryMessageBus(config=config)
    await bus.start()
    yield bus
    await bus.stop()
