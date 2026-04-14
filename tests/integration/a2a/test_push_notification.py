"""Integration test: Push notification verification flow."""

import hashlib
import hmac
import time

import pytest

from synthorg.a2a.push_verifier import A2APushVerifier
from synthorg.integrations.connections.models import ConnectionType
from synthorg.integrations.webhooks.verifiers.factory import get_verifier


@pytest.mark.integration
async def test_a2a_push_verified_end_to_end() -> None:
    """Push notification: sign, verify, accept."""
    secret = "integration-test-secret"
    body = b'{"event":"task.state_changed","task_id":"t-123"}'
    timestamp = str(time.time())

    # Timestamp is included in the signed payload when clock_skew > 0.
    sig = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()

    verifier = A2APushVerifier(clock_skew_seconds=300)
    result = await verifier.verify(
        body=body,
        headers={
            "x-a2a-signature": sig,
            "x-a2a-timestamp": timestamp,
        },
        secret=secret,
    )
    assert result is True


@pytest.mark.integration
async def test_a2a_push_tampered_body_rejected() -> None:
    """Push notification with tampered body is rejected."""
    secret = "integration-test-secret"
    original_body = b'{"event":"task.state_changed"}'
    sig = hmac.new(
        secret.encode("utf-8"),
        original_body,
        hashlib.sha256,
    ).hexdigest()

    tampered_body = b'{"event":"task.deleted"}'
    verifier = A2APushVerifier(clock_skew_seconds=0)
    result = await verifier.verify(
        body=tampered_body,
        headers={"x-a2a-signature": sig},
        secret=secret,
    )
    assert result is False


@pytest.mark.integration
def test_factory_wiring() -> None:
    """Webhook verifier factory returns A2APushVerifier for A2A_PEER."""
    verifier = get_verifier(ConnectionType.A2A_PEER)
    assert isinstance(verifier, A2APushVerifier)
