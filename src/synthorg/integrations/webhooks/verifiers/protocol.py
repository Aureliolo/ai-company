"""Signature verifier protocol for webhook payloads."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SignatureVerifier(Protocol):
    """Verifies the cryptographic signature of an incoming webhook.

    Each external service uses a different signing scheme.
    Implementations handle the specifics (HMAC-SHA256, Slack's
    v0 timestamp scheme, etc.).
    """

    @property
    def signature_header(self) -> str:
        """HTTP header name containing the signature."""
        ...

    async def verify(
        self,
        *,
        body: bytes,
        headers: dict[str, str],
        secret: str,
    ) -> bool:
        """Verify the webhook signature.

        Args:
            body: Raw request body bytes.
            headers: Request headers (lowercased keys).
            secret: Signing secret from the connection catalog.

        Returns:
            ``True`` if the signature is valid.
        """
        ...
