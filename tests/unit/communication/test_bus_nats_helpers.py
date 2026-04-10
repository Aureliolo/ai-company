"""Unit tests for bus/nats.py top-level helpers.

These helpers are pure functions (subject encoding, URL redaction,
task cancellation) that can be exercised without a live NATS
connection. Importing the module requires ``nats-py`` to be
installed, so these tests assume the ``distributed`` extra is
present in the dev/test environment.
"""

import asyncio

import pytest

from synthorg.communication.bus.nats import (
    _cancel_if_pending,
    _decode_token,
    _encode_token,
    _redact_url,
)


class TestEncodeToken:
    """Round-trip base32 encoding of channel/subscriber names."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "original",
        [
            "#general",
            "#engineering",
            "agent-1",
        ],
    )
    def test_round_trip_simple(self, original: str) -> None:
        assert _decode_token(_encode_token(original)) == original

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "original",
        [
            "@agent-a:agent-b",
            "#code-review",
            "agent-1.instance.2",
            "channel with spaces",
        ],
    )
    def test_round_trip_with_special_characters(self, original: str) -> None:
        assert _decode_token(_encode_token(original)) == original

    @pytest.mark.unit
    def test_encoding_is_deterministic(self) -> None:
        first = _encode_token("#general")
        second = _encode_token("#general")
        assert first == second

    @pytest.mark.unit
    def test_encoding_uses_safe_chars(self) -> None:
        """Base32 output must contain only subject-safe characters.

        Lowercase base32 uses ``a-z`` plus digits ``2-7``, which are
        all safe NATS subject tokens.
        """
        token = _encode_token("#engineering")
        allowed = set("abcdefghijklmnopqrstuvwxyz234567")
        for char in token:
            assert char in allowed, f"unexpected char {char!r} in token"

    @pytest.mark.unit
    def test_encoding_distinguishes_channels(self) -> None:
        """Different channel names must encode to different tokens."""
        assert _encode_token("#a") != _encode_token("#b")
        assert _encode_token("@agent-a:agent-b") != _encode_token("@agent-b:agent-a")


class TestRedactUrl:
    """``_redact_url`` strips credentials before logging a NATS URL."""

    @pytest.mark.unit
    def test_passthrough_without_credentials(self) -> None:
        assert _redact_url("nats://localhost:4222") == "nats://localhost:4222"

    @pytest.mark.unit
    def test_strips_username_password(self) -> None:
        redacted = _redact_url("nats://admin:secret@nats-prod:4222")
        assert "secret" not in redacted
        assert "admin" not in redacted
        assert "***@nats-prod:4222" in redacted

    @pytest.mark.unit
    def test_strips_username_only(self) -> None:
        redacted = _redact_url("nats://admin@nats-prod:4222")
        assert "admin" not in redacted
        assert "***@nats-prod:4222" in redacted

    @pytest.mark.unit
    def test_preserves_scheme(self) -> None:
        assert _redact_url("tls://host:4222").startswith("tls://")

    @pytest.mark.unit
    def test_invalid_url_passes_through(self) -> None:
        # Non-URL strings shouldn't crash; return the input unchanged.
        assert _redact_url("not a url") == "not a url"


class TestCancelIfPending:
    """``_cancel_if_pending`` cancels a task and swallows cancellation."""

    @pytest.mark.unit
    async def test_noop_on_completed_task(self) -> None:
        async def noop() -> str:
            return "done"

        task = asyncio.create_task(noop())
        await task
        # Already done -- should return without touching the task.
        await _cancel_if_pending(task)
        assert task.done()

    @pytest.mark.unit
    async def test_cancels_pending_task(self) -> None:
        started = asyncio.Event()

        async def wait_forever() -> None:
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(wait_forever())
        # Deterministic handshake instead of asyncio.sleep(0): block
        # until the coroutine has actually started its forever-wait,
        # so the cancel is guaranteed to race a pending task rather
        # than one that is still queued in the event loop.
        await started.wait()
        await _cancel_if_pending(task)
        assert task.cancelled()

    @pytest.mark.unit
    async def test_does_not_reraise_cancellation(self) -> None:
        started = asyncio.Event()

        async def wait_forever() -> None:
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(wait_forever())
        await started.wait()
        # Should not raise.
        await _cancel_if_pending(task)
        assert task.cancelled()
