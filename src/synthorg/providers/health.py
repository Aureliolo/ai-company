"""Provider health tracking -- models and in-memory tracker.

Records individual provider call outcomes and aggregates them
into health summaries for the API layer.
"""

import asyncio
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger

logger = get_logger(__name__)

_HEALTH_WINDOW_HOURS = 24
_DEGRADED_THRESHOLD = 10.0  # error_rate >= 10% -> DEGRADED
_DOWN_THRESHOLD = 50.0  # error_rate >= 50% -> DOWN


class ProviderHealthStatus(StrEnum):
    """Provider health status derived from recent error rate."""

    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"


class ProviderHealthRecord(BaseModel):
    """Single provider call outcome.

    Attributes:
        provider_name: Name of the provider.
        timestamp: When the call occurred.
        success: Whether the call succeeded.
        response_time_ms: Call response time in milliseconds.
        error_message: Error description when ``success`` is False.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    provider_name: NotBlankStr = Field(description="Provider name")
    timestamp: AwareDatetime = Field(description="When the call occurred")
    success: bool = Field(description="Whether the call succeeded")
    response_time_ms: float = Field(
        ge=0.0,
        description="Response time in milliseconds",
    )
    error_message: str | None = Field(
        default=None,
        max_length=1024,
        description="Error description when success is False",
    )


class ProviderHealthSummary(BaseModel):
    """Aggregated provider health for API response.

    Attributes:
        health_status: Derived health status (up/degraded/down).
        last_check_timestamp: Most recent call timestamp.
        avg_response_time_ms: Average response time over the last 24h.
        error_rate_percent_24h: Error rate percentage over the last 24h.
        calls_last_24h: Total calls in the last 24h.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    last_check_timestamp: AwareDatetime | None = Field(
        default=None,
        description="Most recent call timestamp",
    )
    avg_response_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Average response time in ms (24h window)",
    )
    error_rate_percent_24h: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Error rate percentage (24h window)",
    )
    calls_last_24h: int = Field(
        default=0,
        ge=0,
        description="Total calls in the last 24h",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def health_status(self) -> ProviderHealthStatus:
        """Derive health status from error rate."""
        return _derive_health_status(self.error_rate_percent_24h)


def _derive_health_status(error_rate: float) -> ProviderHealthStatus:
    """Derive health status from error rate percentage."""
    if error_rate >= _DOWN_THRESHOLD:
        return ProviderHealthStatus.DOWN
    if error_rate >= _DEGRADED_THRESHOLD:
        return ProviderHealthStatus.DEGRADED
    return ProviderHealthStatus.UP


class ProviderHealthTracker:
    """In-memory, append-only tracker for provider call outcomes.

    Thread-safe via ``asyncio.Lock``.  Mirrors the
    :class:`~synthorg.budget.tracker.CostTracker` pattern.
    """

    __slots__ = ("_lock", "_records")

    def __init__(self) -> None:
        self._records: list[ProviderHealthRecord] = []
        self._lock = asyncio.Lock()

    async def record(self, record: ProviderHealthRecord) -> None:
        """Append a health record.

        Args:
            record: Immutable call outcome record.
        """
        async with self._lock:
            self._records.append(record)

    async def get_summary(
        self,
        provider_name: str,
        *,
        now: datetime | None = None,
    ) -> ProviderHealthSummary:
        """Build an aggregated health summary for a provider.

        Only considers records within the last 24 hours.

        Args:
            provider_name: Provider to summarise.
            now: Reference time for the 24h window.  Defaults to
                current UTC time.

        Returns:
            Aggregated health summary.
        """
        ref = now or datetime.now(UTC)
        cutoff = ref - timedelta(hours=_HEALTH_WINDOW_HOURS)

        snapshot = await self._snapshot()
        recent = [
            r
            for r in snapshot
            if r.provider_name == provider_name and r.timestamp >= cutoff
        ]

        if not recent:
            return ProviderHealthSummary()

        total = len(recent)
        errors = sum(1 for r in recent if not r.success)
        error_rate = round(errors / total * 100, 2)

        response_times = [r.response_time_ms for r in recent]
        avg_rt = round(math.fsum(response_times) / total, 2)

        last_ts = max(r.timestamp for r in recent)

        return ProviderHealthSummary(
            last_check_timestamp=last_ts,
            avg_response_time_ms=avg_rt,
            error_rate_percent_24h=error_rate,
            calls_last_24h=total,
        )

    async def get_all_summaries(
        self,
        *,
        now: datetime | None = None,
    ) -> dict[str, ProviderHealthSummary]:
        """Build summaries for all known providers.

        Args:
            now: Reference time for the 24h window.

        Returns:
            Mapping of provider name to health summary.
        """
        ref = now or datetime.now(UTC)
        cutoff = ref - timedelta(hours=_HEALTH_WINDOW_HOURS)

        snapshot = await self._snapshot()
        by_provider: dict[str, list[ProviderHealthRecord]] = defaultdict(list)
        for r in snapshot:
            if r.timestamp >= cutoff:
                by_provider[r.provider_name].append(r)

        result: dict[str, ProviderHealthSummary] = {}
        for name, records in sorted(by_provider.items()):
            total = len(records)
            errors = sum(1 for r in records if not r.success)
            error_rate = round(errors / total * 100, 2)
            response_times = [r.response_time_ms for r in records]
            avg_rt = round(math.fsum(response_times) / total, 2)
            last_ts = max(r.timestamp for r in records)
            result[name] = ProviderHealthSummary(
                last_check_timestamp=last_ts,
                avg_response_time_ms=avg_rt,
                error_rate_percent_24h=error_rate,
                calls_last_24h=total,
            )
        return result

    async def _snapshot(self) -> tuple[ProviderHealthRecord, ...]:
        """Return an immutable snapshot of all current records."""
        async with self._lock:
            return tuple(self._records)
