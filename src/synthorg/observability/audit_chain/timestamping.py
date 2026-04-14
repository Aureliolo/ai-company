"""Timestamp providers for the audit chain.

Supports RFC 3161 TSA with local-clock fallback.
"""

from datetime import UTC, datetime
from typing import Protocol

from synthorg.observability import get_logger
from synthorg.observability.events.security import (
    SECURITY_TIMESTAMP_FALLBACK,
)

logger = get_logger(__name__)


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

    Tries the TSA first.  On any failure, falls back to the local
    clock and emits a ``SECURITY_TIMESTAMP_FALLBACK`` event.

    Args:
        tsa_url: RFC 3161 TSA endpoint URL.
    """

    def __init__(self, tsa_url: str) -> None:
        self._tsa_url = tsa_url

    async def get_timestamp(self) -> datetime:
        """Get timestamp from TSA, falling back to local clock.

        Returns:
            UTC datetime from TSA or local clock on failure.
        """
        try:
            return await self._fetch_tsa_timestamp()
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                SECURITY_TIMESTAMP_FALLBACK,
                tsa_url=self._tsa_url,
                reason="TSA request failed, using local clock",
                exc_info=True,
            )
            return datetime.now(UTC)

    async def _fetch_tsa_timestamp(self) -> datetime:
        """Fetch timestamp from RFC 3161 TSA.

        This is a stub -- real implementation would use httpx
        to POST to the TSA endpoint and parse the response.

        Raises:
            NotImplementedError: TSA client not yet implemented.
        """
        msg = "RFC 3161 TSA client not yet implemented"
        raise NotImplementedError(msg)
