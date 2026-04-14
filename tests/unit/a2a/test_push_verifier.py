"""Tests for A2A push notification signature verifier."""

import hashlib
import hmac
import time

import pytest

from synthorg.a2a.push_verifier import A2APushVerifier


def _sign(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


class TestA2APushVerifier:
    """Push notification signature verification."""

    @pytest.mark.unit
    async def test_valid_signature(self) -> None:
        """Valid HMAC-SHA256 signature passes."""
        verifier = A2APushVerifier()
        body = b'{"event": "task.updated"}'
        secret = "test-secret"
        sig = _sign(body, secret)

        result = await verifier.verify(
            body=body,
            headers={"x-a2a-signature": sig},
            secret=secret,
        )
        assert result is True

    @pytest.mark.unit
    async def test_invalid_signature(self) -> None:
        """Invalid signature fails."""
        verifier = A2APushVerifier()
        result = await verifier.verify(
            body=b"data",
            headers={"x-a2a-signature": "bad-sig"},
            secret="test-secret",
        )
        assert result is False

    @pytest.mark.unit
    async def test_missing_signature_header(self) -> None:
        """Missing signature header fails."""
        verifier = A2APushVerifier()
        result = await verifier.verify(
            body=b"data",
            headers={},
            secret="test-secret",
        )
        assert result is False

    @pytest.mark.unit
    async def test_signature_header_name(self) -> None:
        """Verifier uses x-a2a-signature header."""
        verifier = A2APushVerifier()
        assert verifier.signature_header == "x-a2a-signature"

    @pytest.mark.unit
    async def test_valid_timestamp(self) -> None:
        """Valid timestamp within clock skew passes."""
        verifier = A2APushVerifier(clock_skew_seconds=300)
        body = b"data"
        secret = "test-secret"
        sig = _sign(body, secret)

        result = await verifier.verify(
            body=body,
            headers={
                "x-a2a-signature": sig,
                "x-a2a-timestamp": str(time.time()),
            },
            secret=secret,
        )
        assert result is True

    @pytest.mark.unit
    async def test_expired_timestamp(self) -> None:
        """Timestamp outside clock skew fails."""
        verifier = A2APushVerifier(clock_skew_seconds=60)
        body = b"data"
        secret = "test-secret"
        sig = _sign(body, secret)

        result = await verifier.verify(
            body=body,
            headers={
                "x-a2a-signature": sig,
                "x-a2a-timestamp": str(time.time() - 120),
            },
            secret=secret,
        )
        assert result is False

    @pytest.mark.unit
    async def test_malformed_timestamp(self) -> None:
        """Non-numeric timestamp fails."""
        verifier = A2APushVerifier()
        body = b"data"
        secret = "test-secret"
        sig = _sign(body, secret)

        result = await verifier.verify(
            body=body,
            headers={
                "x-a2a-signature": sig,
                "x-a2a-timestamp": "not-a-number",
            },
            secret=secret,
        )
        assert result is False

    @pytest.mark.unit
    async def test_no_timestamp_skips_check(self) -> None:
        """Missing timestamp skips the clock skew check."""
        verifier = A2APushVerifier(clock_skew_seconds=1)
        body = b"data"
        secret = "test-secret"
        sig = _sign(body, secret)

        result = await verifier.verify(
            body=body,
            headers={"x-a2a-signature": sig},
            secret=secret,
        )
        assert result is True

    @pytest.mark.unit
    async def test_implements_protocol(self) -> None:
        """A2APushVerifier is a SignatureVerifier."""
        from synthorg.integrations.webhooks.verifiers.protocol import (
            SignatureVerifier,
        )

        verifier = A2APushVerifier()
        assert isinstance(verifier, SignatureVerifier)

    @pytest.mark.unit
    def test_factory_returns_a2a_verifier(self) -> None:
        """Webhook verifier factory returns A2APushVerifier for A2A_PEER."""
        from synthorg.integrations.connections.models import (
            ConnectionType,
        )
        from synthorg.integrations.webhooks.verifiers.factory import (
            get_verifier,
        )

        verifier = get_verifier(ConnectionType.A2A_PEER)
        assert isinstance(verifier, A2APushVerifier)
