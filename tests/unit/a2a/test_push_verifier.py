"""Tests for A2A push notification signature verifier."""

import hashlib
import hmac
import time

import pytest

from synthorg.a2a.push_verifier import A2APushVerifier


def _sign(body: bytes, secret: str, *, timestamp: str = "") -> str:
    """Compute HMAC-SHA256 signature.

    When *timestamp* is provided, it is prepended to the body
    in the signed payload (matching the verifier behavior).
    """
    payload = timestamp.encode("utf-8") + body if timestamp else body
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


class TestA2APushVerifier:
    """Push notification signature verification."""

    @pytest.mark.unit
    async def test_valid_signature_with_timestamp(self) -> None:
        """Valid HMAC-SHA256 signature with timestamp passes."""
        verifier = A2APushVerifier(clock_skew_seconds=300)
        body = b'{"event": "task.updated"}'
        secret = "test-secret"
        ts = str(time.time())
        sig = _sign(body, secret, timestamp=ts)

        result = await verifier.verify(
            body=body,
            headers={
                "x-a2a-signature": sig,
                "x-a2a-timestamp": ts,
            },
            secret=secret,
        )
        assert result is True

    @pytest.mark.unit
    async def test_valid_signature_no_clock_skew(self) -> None:
        """Valid HMAC-SHA256 signature passes without clock skew."""
        verifier = A2APushVerifier(clock_skew_seconds=0)
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
        verifier = A2APushVerifier(clock_skew_seconds=0)
        result = await verifier.verify(
            body=b"data",
            headers={"x-a2a-signature": "bad-sig"},
            secret="test-secret",
        )
        assert result is False

    @pytest.mark.unit
    async def test_missing_signature_header(self) -> None:
        """Missing signature header fails."""
        verifier = A2APushVerifier(clock_skew_seconds=0)
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
        ts = str(time.time())
        sig = _sign(body, secret, timestamp=ts)

        result = await verifier.verify(
            body=body,
            headers={
                "x-a2a-signature": sig,
                "x-a2a-timestamp": ts,
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
        verifier = A2APushVerifier(clock_skew_seconds=300)
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
    async def test_missing_timestamp_rejected_when_skew_enabled(self) -> None:
        """Missing timestamp is rejected when clock skew is enabled."""
        verifier = A2APushVerifier(clock_skew_seconds=1)
        body = b"data"
        secret = "test-secret"
        sig = _sign(body, secret)

        result = await verifier.verify(
            body=body,
            headers={"x-a2a-signature": sig},
            secret=secret,
        )
        assert result is False

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

    @pytest.mark.unit
    async def test_expired_timestamp_with_signed_ts(self) -> None:
        """Expired timestamp is rejected even with valid HMAC."""
        verifier = A2APushVerifier(clock_skew_seconds=60)
        body = b"data"
        secret = "test-secret"
        ts = str(time.time() - 120)
        sig = _sign(body, secret, timestamp=ts)

        result = await verifier.verify(
            body=body,
            headers={
                "x-a2a-signature": sig,
                "x-a2a-timestamp": ts,
            },
            secret=secret,
        )
        assert result is False

    @pytest.mark.unit
    async def test_zero_clock_skew_skips_timestamp(self) -> None:
        """Clock skew of 0 accepts requests without timestamp."""
        verifier = A2APushVerifier(clock_skew_seconds=0)
        body = b"payload"
        secret = "test-secret"
        sig = _sign(body, secret)

        result = await verifier.verify(
            body=body,
            headers={"x-a2a-signature": sig},
            secret=secret,
        )
        assert result is True


class TestA2APushVerifierFactory:
    """Push verifier factory."""

    @pytest.mark.unit
    def test_negative_clock_skew_rejected(self) -> None:
        """Factory rejects negative clock_skew_seconds."""
        from synthorg.a2a.connection_types.a2a_peer import (
            get_a2a_push_verifier,
        )

        with pytest.raises(ValueError, match="clock_skew_seconds must be >= 0"):
            get_a2a_push_verifier(clock_skew_seconds=-1)

    @pytest.mark.unit
    def test_zero_clock_skew_accepted(self) -> None:
        """Factory accepts clock_skew_seconds=0."""
        from synthorg.a2a.connection_types.a2a_peer import (
            get_a2a_push_verifier,
        )

        verifier = get_a2a_push_verifier(clock_skew_seconds=0)
        assert isinstance(verifier, A2APushVerifier)
