"""Unit tests for webhook signature verifiers."""

import hashlib
import hmac

import pytest

from synthorg.integrations.webhooks.verifiers.generic_hmac import (
    GenericHmacVerifier,
)
from synthorg.integrations.webhooks.verifiers.github_hmac import (
    GitHubHmacVerifier,
)
from synthorg.integrations.webhooks.verifiers.slack_signing import (
    SlackSigningVerifier,
)


@pytest.mark.unit
class TestGitHubHmacVerifier:
    """Tests for GitHub HMAC-SHA256 signature verification."""

    async def test_valid_signature_accepted(self) -> None:
        verifier = GitHubHmacVerifier()
        body = b'{"action": "push"}'
        secret = "test-secret"
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        result = await verifier.verify(
            body=body,
            headers={"x-hub-signature-256": sig},
            secret=secret,
        )
        assert result is True

    async def test_invalid_signature_rejected(self) -> None:
        verifier = GitHubHmacVerifier()
        result = await verifier.verify(
            body=b"payload",
            headers={"x-hub-signature-256": "sha256=bad"},
            secret="secret",
        )
        assert result is False

    async def test_missing_prefix_rejected(self) -> None:
        verifier = GitHubHmacVerifier()
        result = await verifier.verify(
            body=b"payload",
            headers={"x-hub-signature-256": "noprefixhere"},
            secret="secret",
        )
        assert result is False

    async def test_missing_header_rejected(self) -> None:
        verifier = GitHubHmacVerifier()
        result = await verifier.verify(
            body=b"payload",
            headers={},
            secret="secret",
        )
        assert result is False


@pytest.mark.unit
class TestSlackSigningVerifier:
    """Tests for Slack signing verification."""

    async def test_valid_signature_accepted(self) -> None:
        import time

        verifier = SlackSigningVerifier()
        body = b"token=xxx&command=/test"
        secret = "slack-signing-secret"
        timestamp = str(int(time.time()))

        base = f"v0:{timestamp}:".encode() + body
        sig = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()

        result = await verifier.verify(
            body=body,
            headers={
                "x-slack-request-timestamp": timestamp,
                "x-slack-signature": sig,
            },
            secret=secret,
        )
        assert result is True

    async def test_old_timestamp_rejected(self) -> None:
        verifier = SlackSigningVerifier()
        result = await verifier.verify(
            body=b"payload",
            headers={
                "x-slack-request-timestamp": "1000000000",
                "x-slack-signature": "v0=bad",
            },
            secret="secret",
        )
        assert result is False

    async def test_missing_headers_rejected(self) -> None:
        verifier = SlackSigningVerifier()
        result = await verifier.verify(
            body=b"payload",
            headers={},
            secret="secret",
        )
        assert result is False


@pytest.mark.unit
class TestGenericHmacVerifier:
    """Tests for configurable generic HMAC verification."""

    async def test_valid_signature_accepted(self) -> None:
        verifier = GenericHmacVerifier(
            header_name="x-signature",
            prefix="sha256=",
        )
        body = b"test-payload"
        secret = "my-secret"
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        result = await verifier.verify(
            body=body,
            headers={"x-signature": sig},
            secret=secret,
        )
        assert result is True

    async def test_no_prefix_mode(self) -> None:
        verifier = GenericHmacVerifier(
            header_name="x-hmac",
            prefix="",
        )
        body = b"test"
        secret = "sec"
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        result = await verifier.verify(
            body=body,
            headers={"x-hmac": sig},
            secret=secret,
        )
        assert result is True

    async def test_empty_signature_rejected(self) -> None:
        verifier = GenericHmacVerifier()
        result = await verifier.verify(
            body=b"test",
            headers={"x-signature": ""},
            secret="secret",
        )
        assert result is False
