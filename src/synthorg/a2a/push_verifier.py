"""A2A push notification signature verifier.

Implements the ``SignatureVerifier`` protocol from
``synthorg.integrations.webhooks.verifiers.protocol`` for
A2A-specific HMAC-SHA256 push notification verification.
"""

import hashlib
import hmac
import time

from synthorg.observability import get_logger
from synthorg.observability.events.a2a import (
    A2A_PUSH_VERIFICATION_FAILED,
    A2A_PUSH_VERIFIED,
)

logger = get_logger(__name__)

_DEFAULT_CLOCK_SKEW_SECONDS = 300


class A2APushVerifier:
    """Verifies A2A push notification signatures.

    Implements HMAC-SHA256 signature verification with timestamp
    validation for clock skew tolerance.

    Args:
        clock_skew_seconds: Maximum allowed clock skew between
            the push sender and this receiver.
    """

    __slots__ = ("_clock_skew_seconds",)

    def __init__(
        self,
        clock_skew_seconds: int = _DEFAULT_CLOCK_SKEW_SECONDS,
    ) -> None:
        self._clock_skew_seconds = clock_skew_seconds

    @property
    def signature_header(self) -> str:
        """HTTP header name containing the A2A signature."""
        return "x-a2a-signature"

    async def verify(
        self,
        *,
        body: bytes,
        headers: dict[str, str],
        secret: str,
    ) -> bool:
        """Verify the push notification signature.

        Checks HMAC-SHA256 signature and optional timestamp
        for clock skew tolerance.

        Args:
            body: Raw request body bytes.
            headers: Request headers (lowercased keys).
            secret: Signing secret from the connection catalog.

        Returns:
            ``True`` if the signature is valid.
        """
        signature = headers.get(self.signature_header, "")
        if not signature:
            logger.warning(
                A2A_PUSH_VERIFICATION_FAILED,
                reason="missing signature header",
            )
            return False

        # Compute expected HMAC-SHA256
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            logger.warning(
                A2A_PUSH_VERIFICATION_FAILED,
                reason="signature mismatch",
            )
            return False

        # Validate timestamp if present
        timestamp_str = headers.get("x-a2a-timestamp", "")
        if timestamp_str and self._clock_skew_seconds > 0:
            try:
                timestamp = float(timestamp_str)
            except ValueError:
                logger.warning(
                    A2A_PUSH_VERIFICATION_FAILED,
                    reason="malformed timestamp",
                )
                return False
            now = time.time()
            if abs(now - timestamp) > self._clock_skew_seconds:
                logger.warning(
                    A2A_PUSH_VERIFICATION_FAILED,
                    reason="timestamp outside clock skew tolerance",
                    skew=abs(now - timestamp),
                    max_skew=self._clock_skew_seconds,
                )
                return False

        logger.debug(A2A_PUSH_VERIFIED)
        return True
