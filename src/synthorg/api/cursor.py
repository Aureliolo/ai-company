"""Opaque pagination cursor with HMAC signing.

Clients treat cursors as opaque strings. The server encodes an integer
offset into a base64url-encoded JSON payload ``{"o": offset, "s": hmac}``
where ``hmac`` is computed over ``str(offset)`` using the configured
secret. Tampering with either field flips the signature, and
:func:`decode_cursor` raises :class:`InvalidCursorError`.

The opaque shape lets the server evolve internal pagination (offset
today, seek-based composite keys later) without breaking clients. The
HMAC makes cursors unforgeable -- a client cannot craft a token to
skip to an arbitrary page.
"""

import base64
import hashlib
import hmac
import json
import secrets
from typing import Self

from synthorg.api.cursor_config import CursorConfig  # noqa: TC001


class InvalidCursorError(ValueError):
    """Raised when a cursor token is malformed, tampered, or unsigned.

    Controllers should translate this to HTTP 400 with a structured
    ``ErrorDetail`` (``error_category=validation``).
    """


# Minimum key length (bytes) enforced on HMAC secrets. 16 bytes = 128
# bits of entropy; below this the signing strength falls off fast.
_MIN_KEY_BYTES = 16


class CursorSecret:
    """HMAC key wrapper.

    Use one of the classmethod constructors -- never pass the raw key
    around directly so a future audit can trace key lifecycle.

    Attributes:
        is_ephemeral: ``True`` when the key was generated at process
            start (no persistence). Caller-facing code can surface a
            boot-time WARNING.
    """

    __slots__ = ("_ephemeral", "_key")

    def __init__(self, *, key: bytes, ephemeral: bool) -> None:
        if len(key) < _MIN_KEY_BYTES:
            msg = (
                f"Cursor HMAC key must be at least {_MIN_KEY_BYTES} bytes; "
                f"got {len(key)}"
            )
            raise ValueError(msg)
        self._key = key
        self._ephemeral = ephemeral

    @classmethod
    def from_key(cls, key: str) -> Self:
        """Build a stable secret from an explicit key string.

        The key is UTF-8 encoded. For env-var driven configuration
        callers may pass a base64-encoded string; this helper accepts
        any printable key so operators can choose their own format.

        Raises:
            ValueError: If the encoded key is shorter than 16 bytes.
        """
        return cls(key=key.encode("utf-8"), ephemeral=False)

    @classmethod
    def ephemeral(cls) -> Self:
        """Build a secret from a random per-process key.

        Tokens signed with an ephemeral secret are invalidated on
        restart -- suitable for local dev and test only.
        """
        return cls(key=secrets.token_bytes(32), ephemeral=True)

    @classmethod
    def from_config(cls, config: CursorConfig) -> Self:
        """Build from :class:`CursorConfig`, falling back to ephemeral.

        If ``config.secret`` is ``None`` or blank, the secret is
        ephemeral and :attr:`is_ephemeral` is ``True`` so callers can
        surface a single boot-time warning.
        """
        if config.secret and config.secret.strip():
            return cls.from_key(config.secret)
        return cls.ephemeral()

    @property
    def is_ephemeral(self) -> bool:
        """Whether this secret was randomly generated (not configured)."""
        return self._ephemeral

    def sign(self, payload: bytes) -> str:
        """Return the hex HMAC-SHA256 of ``payload``."""
        return hmac.new(self._key, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        """Constant-time compare ``signature`` against the HMAC of ``payload``."""
        expected = self.sign(payload)
        return hmac.compare_digest(expected, signature)


def encode_cursor(offset: int, *, secret: CursorSecret) -> str:
    """Encode ``offset`` as an opaque signed cursor token.

    Args:
        offset: Zero-based page offset. Must be ``>= 0``.
        secret: HMAC signing secret.

    Returns:
        URL-safe base64 token without padding.

    Raises:
        ValueError: If ``offset`` is negative.
    """
    if offset < 0:
        msg = f"cursor offset must be >= 0, got {offset}"
        raise ValueError(msg)
    signature = secret.sign(str(offset).encode("utf-8"))
    payload = json.dumps({"o": offset, "s": signature}, separators=(",", ":"))
    return (
        base64.urlsafe_b64encode(payload.encode("utf-8")).rstrip(b"=").decode("ascii")
    )


def decode_cursor(token: str, *, secret: CursorSecret) -> int:
    """Decode an opaque signed cursor and return the offset.

    Args:
        token: The cursor string previously produced by :func:`encode_cursor`.
        secret: HMAC secret matching the one used to sign.

    Returns:
        The zero-based offset.

    Raises:
        InvalidCursorError: If the token is malformed, has been
            tampered with, or was signed by a different secret.
    """
    if not token:
        msg = "cursor token is empty"
        raise InvalidCursorError(msg)

    try:
        # Re-pad: base64 decoding tolerates missing padding only when
        # the string length is already a multiple of 4.
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, TypeError) as exc:
        msg = "cursor token is not valid base64"
        raise InvalidCursorError(msg) from exc

    try:
        payload = json.loads(decoded)
    except (ValueError, UnicodeDecodeError) as exc:
        msg = "cursor token payload is not valid JSON"
        raise InvalidCursorError(msg) from exc

    if not isinstance(payload, dict):
        msg = "cursor token payload must be a JSON object"
        raise InvalidCursorError(msg)

    offset = payload.get("o")
    signature = payload.get("s")
    if not isinstance(offset, int) or isinstance(offset, bool):
        msg = "cursor token is missing a valid 'o' integer field"
        raise InvalidCursorError(msg)
    if not isinstance(signature, str):
        msg = "cursor token is missing a valid 's' signature field"
        raise InvalidCursorError(msg)
    if offset < 0:
        msg = "cursor token offset must be >= 0"
        raise InvalidCursorError(msg)
    if not secret.verify(str(offset).encode("utf-8"), signature):
        msg = "cursor signature is invalid"
        raise InvalidCursorError(msg)
    return offset
