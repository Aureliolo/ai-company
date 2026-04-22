"""Unit tests for the opaque pagination cursor helper."""

import base64
import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from synthorg.api.cursor import (
    CursorSecret,
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from synthorg.api.cursor_config import CursorConfig

pytestmark = pytest.mark.unit


@pytest.fixture
def stable_secret() -> CursorSecret:
    """Build a secret with a fixed key so tests are deterministic."""
    return CursorSecret.from_key("unit-test-fixed-key-32-bytes-pad00")


class TestEncodeDecode:
    """Round-trip semantics."""

    def test_round_trip_zero(self, stable_secret: CursorSecret) -> None:
        token = encode_cursor(0, secret=stable_secret)
        assert decode_cursor(token, secret=stable_secret) == 0

    def test_round_trip_positive(self, stable_secret: CursorSecret) -> None:
        token = encode_cursor(4242, secret=stable_secret)
        assert decode_cursor(token, secret=stable_secret) == 4242

    def test_token_is_urlsafe_base64(self, stable_secret: CursorSecret) -> None:
        token = encode_cursor(100, secret=stable_secret)
        # urlsafe_b64decode accepts the token back
        padded = token + "=" * (-len(token) % 4)
        base64.urlsafe_b64decode(padded.encode("ascii"))

    def test_stable_secret_produces_stable_token(
        self,
        stable_secret: CursorSecret,
    ) -> None:
        assert encode_cursor(7, secret=stable_secret) == encode_cursor(
            7,
            secret=stable_secret,
        )

    def test_different_secrets_produce_different_tokens(self) -> None:
        a = CursorSecret.from_key("secret-alpha-unit-test-key-pad0000")
        b = CursorSecret.from_key("secret-bravo-unit-test-key-pad0000")
        assert encode_cursor(1, secret=a) != encode_cursor(1, secret=b)


class TestTamperDetection:
    """HMAC must reject any tampered field."""

    def test_tampered_offset_rejected(self, stable_secret: CursorSecret) -> None:
        good = encode_cursor(50, secret=stable_secret)
        # Decode the outer payload, flip the offset, re-encode without re-signing.
        padded = good + "=" * (-len(good) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        payload["o"] = 999
        tampered_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        tampered = base64.urlsafe_b64encode(tampered_bytes).rstrip(b"=").decode("ascii")
        with pytest.raises(InvalidCursorError):
            decode_cursor(tampered, secret=stable_secret)

    def test_foreign_signature_rejected(self) -> None:
        signed_a = encode_cursor(
            10,
            secret=CursorSecret.from_key("secret-alpha-unit-test-key-pad0000"),
        )
        with pytest.raises(InvalidCursorError):
            decode_cursor(
                signed_a,
                secret=CursorSecret.from_key("secret-bravo-unit-test-key-pad0000"),
            )

    def test_malformed_base64_rejected(self, stable_secret: CursorSecret) -> None:
        with pytest.raises(InvalidCursorError):
            decode_cursor("not!!base64!!", secret=stable_secret)

    def test_non_json_payload_rejected(self, stable_secret: CursorSecret) -> None:
        # Valid base64 but not JSON.
        token = base64.urlsafe_b64encode(b"hello world").rstrip(b"=").decode("ascii")
        with pytest.raises(InvalidCursorError):
            decode_cursor(token, secret=stable_secret)

    def test_missing_fields_rejected(self, stable_secret: CursorSecret) -> None:
        token_bytes = json.dumps({"o": 10}, separators=(",", ":")).encode("utf-8")
        token = base64.urlsafe_b64encode(token_bytes).rstrip(b"=").decode("ascii")
        with pytest.raises(InvalidCursorError):
            decode_cursor(token, secret=stable_secret)

    def test_negative_offset_rejected(self, stable_secret: CursorSecret) -> None:
        # Server must never produce one, but the decoder is the last line.
        payload = {"o": -1, "s": "deadbeef"}
        token_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        token = base64.urlsafe_b64encode(token_bytes).rstrip(b"=").decode("ascii")
        with pytest.raises(InvalidCursorError):
            decode_cursor(token, secret=stable_secret)


class TestEphemeralSecret:
    """When no key is configured, a random per-process key is used."""

    def test_ephemeral_secret_round_trips(self) -> None:
        secret = CursorSecret.ephemeral()
        token = encode_cursor(123, secret=secret)
        assert decode_cursor(token, secret=secret) == 123

    def test_ephemeral_is_ephemeral(self) -> None:
        a = CursorSecret.ephemeral()
        b = CursorSecret.ephemeral()
        # Two ephemeral secrets are different -- tokens cross-decode fail.
        token = encode_cursor(1, secret=a)
        with pytest.raises(InvalidCursorError):
            decode_cursor(token, secret=b)


class TestFromConfig:
    """Building a secret from CursorConfig."""

    def test_explicit_secret_is_stable(self) -> None:
        config = CursorConfig(secret="explicit-key-32-bytes-padding0000")
        s1 = CursorSecret.from_config(config)
        s2 = CursorSecret.from_config(config)
        token = encode_cursor(5, secret=s1)
        assert decode_cursor(token, secret=s2) == 5

    def test_empty_secret_is_ephemeral(self) -> None:
        config = CursorConfig(secret=None)
        s = CursorSecret.from_config(config)
        assert s.is_ephemeral


@given(offset=st.integers(min_value=0, max_value=10**9))
def test_round_trip_property(offset: int) -> None:
    secret = CursorSecret.from_key("hypothesis-key-32-bytes-pad000000")
    assert decode_cursor(encode_cursor(offset, secret=secret), secret=secret) == offset
