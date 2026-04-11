"""Slack request signing verifier."""

import hashlib
import hmac
import time

from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    WEBHOOK_SIGNATURE_INVALID,
    WEBHOOK_SIGNATURE_VERIFIED,
)

logger = get_logger(__name__)

_MAX_CLOCK_SKEW = 300  # 5 minutes


class SlackSigningVerifier:
    """Verifies Slack webhook signatures.

    Slack signs requests with HMAC-SHA256 of ``v0:{timestamp}:{body}``
    using the signing secret.  The signature is sent in
    ``X-Slack-Signature`` and the timestamp in
    ``X-Slack-Request-Timestamp``.
    """

    @property
    def signature_header(self) -> str:
        """HTTP header name containing the signature."""
        return "x-slack-signature"

    async def verify(
        self,
        *,
        body: bytes,
        headers: dict[str, str],
        secret: str,
    ) -> bool:
        """Verify a Slack webhook signature."""
        timestamp_str = headers.get("x-slack-request-timestamp", "")
        signature = headers.get(self.signature_header, "")

        if not timestamp_str or not signature:
            logger.warning(
                WEBHOOK_SIGNATURE_INVALID,
                reason="missing timestamp or signature header",
            )
            return False

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            logger.warning(
                WEBHOOK_SIGNATURE_INVALID,
                reason="non-integer timestamp",
            )
            return False

        if abs(time.time() - timestamp) > _MAX_CLOCK_SKEW:
            logger.warning(
                WEBHOOK_SIGNATURE_INVALID,
                reason="timestamp too old or too far in future",
            )
            return False

        base_string = f"v0:{timestamp}:".encode() + body
        expected = (
            "v0="
            + hmac.new(
                secret.encode("utf-8"),
                base_string,
                hashlib.sha256,
            ).hexdigest()
        )

        valid = hmac.compare_digest(expected, signature)
        if valid:
            logger.debug(WEBHOOK_SIGNATURE_VERIFIED, provider="slack")
        else:
            logger.warning(
                WEBHOOK_SIGNATURE_INVALID,
                provider="slack",
                reason="digest mismatch",
            )
        return valid
