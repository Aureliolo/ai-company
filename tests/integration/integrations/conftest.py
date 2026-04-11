"""Fixtures for integration tests of the integrations subsystem."""

from collections.abc import AsyncGenerator, Generator

import pytest

from synthorg.communication.bus.memory import InMemoryMessageBus
from synthorg.communication.config import MessageBusConfig

# Fixed valid Fernet key so PKCE verifier encrypt/decrypt works in
# every integration test that exercises the authorization code flow.
_TEST_MASTER_KEY = "lKzZcMznksIF8A_2HFFUnKxhxhz9_bxTvVJoZ6mvZrk="


@pytest.fixture(autouse=True)
def _set_master_key(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    """Set ``SYNTHORG_MASTER_KEY`` so the PKCE verifier cipher can init.

    The OAuth authorization code flow now encrypts the PKCE verifier
    at rest using Fernet, keyed by ``SYNTHORG_MASTER_KEY``. Tests that
    do not explicitly set the env var would otherwise fail during
    the token exchange with ``MasterKeyError``. Also reset the cached
    cipher between tests so a stale holder from a previous run does
    not leak into the current one.
    """
    from synthorg.integrations.oauth.pkce import _reset_cipher_for_tests

    monkeypatch.setenv("SYNTHORG_MASTER_KEY", _TEST_MASTER_KEY)
    _reset_cipher_for_tests()
    yield
    _reset_cipher_for_tests()


@pytest.fixture
async def memory_bus() -> AsyncGenerator[InMemoryMessageBus]:
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
