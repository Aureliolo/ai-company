"""Timestamp providers for the audit chain.

Supports RFC 3161 TSA with local-clock fallback. The TSA client is
injected -- :class:`ResilientTimestampProvider` never constructs its
own HTTP client, so tests and factories can swap the transport
freely.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from synthorg.observability import get_logger
from synthorg.observability.audit_chain.tsa_client import (
    TsaError,
    TsaHashMismatchError,
    TsaNonceMismatchError,
    TsaSignatureError,
)
from synthorg.observability.events.security import (
    SECURITY_TIMESTAMP_FALLBACK,
    SECURITY_TIMESTAMP_INCIDENT,
)

if TYPE_CHECKING:
    from synthorg.observability.audit_chain.tsa_client import TsaClient

logger = get_logger(__name__)

# Exception classes that indicate an active security attack or
# cryptographic failure -- these must NEVER silently fall back to the
# local clock. Operators need to know immediately that the audit
# chain may be compromised.
_SECURITY_INCIDENT_EXCEPTIONS: tuple[type[TsaError], ...] = (
    TsaHashMismatchError,
    TsaNonceMismatchError,
    TsaSignatureError,
)


class TimestampProvider(Protocol):
    """Protocol for audit chain timestamp sources."""

    async def get_timestamp(self) -> datetime:
        """Get a trusted timestamp.

        Returns:
            UTC datetime from the timestamp source.
        """
        ...


class LocalClockProvider:
    """Timestamp provider using the local system clock."""

    async def get_timestamp(self) -> datetime:
        """Return current UTC time from the local clock."""
        return datetime.now(UTC)


class ResilientTimestampProvider:
    """Timestamp provider with RFC 3161 primary and local fallback.

    Tries the TSA first. On any :class:`TsaError` (or any other
    unexpected exception short of ``MemoryError`` / ``RecursionError``),
    falls back to the local clock and emits a
    :data:`SECURITY_TIMESTAMP_FALLBACK` warning that includes the
    precise failure class in ``reason``.

    Args:
        tsa_client: The TSA client. The provider does not own the
            client; shutdown is the caller's responsibility.
        binding_payload: Bytes that the TSA should timestamp. Pass a
            value tied to the audit chain's current head hash so the
            returned timestamp is cryptographically bound to the
            chain state at request time. Defaults to a fixed marker
            when callers only need a coarse-grained time anchor.
    """

    def __init__(
        self,
        tsa_client: TsaClient,
        *,
        binding_payload: bytes = b"synthorg.audit_chain.timestamp",
    ) -> None:
        self._client = tsa_client
        self._binding_payload = binding_payload

    @property
    def tsa_url(self) -> str:
        """Return the injected client's TSA endpoint."""
        return self._client.tsa_url

    async def get_timestamp(self) -> datetime:
        """Get timestamp from TSA, falling back to local clock.

        Security-incident exceptions -- hash mismatch, nonce
        mismatch, signature invalid -- propagate unchanged; they
        signal active tampering and must not be silently masked by
        the local-clock fallback. Transient failures (timeouts,
        transport errors, malformed responses) emit
        :data:`SECURITY_TIMESTAMP_FALLBACK` at WARNING and return the
        local clock so the audit chain keeps moving.

        Returns:
            UTC datetime from TSA or local clock on transient
            failure.

        Raises:
            TsaHashMismatchError: MessageImprint didn't match request.
            TsaNonceMismatchError: Response nonce didn't match request.
            TsaSignatureError: CMS signature didn't verify.
        """
        try:
            token = await self._client.request_timestamp(self._binding_payload)
        except _SECURITY_INCIDENT_EXCEPTIONS as exc:
            logger.exception(
                SECURITY_TIMESTAMP_INCIDENT,
                tsa_url=self._client.tsa_url,
                incident=type(exc).__name__,
            )
            raise
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                SECURITY_TIMESTAMP_FALLBACK,
                tsa_url=self._client.tsa_url,
                reason=type(exc).__name__,
                error=str(exc),
            )
            return datetime.now(UTC)
        return token.timestamp
