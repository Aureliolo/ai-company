"""Quota degradation resolution.

Implements FALLBACK, QUEUE, and ALERT degradation strategies for
provider quota exhaustion.  Called by
:class:`~synthorg.budget.enforcer.BudgetEnforcer` when a pre-flight
quota check fails and the provider has a non-default degradation
configuration.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from synthorg.budget.errors import QuotaExhaustedError
from synthorg.budget.quota import (
    DegradationAction,
    DegradationConfig,
    QuotaCheckResult,
)
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.degradation import (
    DEGRADATION_ALERT_RAISED,
    DEGRADATION_FALLBACK_EXHAUSTED,
    DEGRADATION_FALLBACK_PROVIDER_CHECKED,
    DEGRADATION_FALLBACK_RESOLVED,
    DEGRADATION_FALLBACK_STARTED,
    DEGRADATION_QUEUE_EXHAUSTED,
    DEGRADATION_QUEUE_RESUMED,
    DEGRADATION_QUEUE_STARTED,
    DEGRADATION_QUEUE_WAITING,
)

if TYPE_CHECKING:
    from synthorg.budget.quota import QuotaWindow
    from synthorg.budget.quota_tracker import QuotaTracker

logger = get_logger(__name__)

# Alias for testability (tests patch this to avoid real sleeps).
asyncio_sleep = asyncio.sleep


# ── Result models ─────────────────────────────────────────────────


class DegradationResult(BaseModel):
    """Result of quota degradation resolution.

    Attributes:
        original_provider: The provider whose quota was exhausted.
        effective_provider: The provider to actually use after
            degradation.
        action_taken: Which degradation action was applied.
        wait_seconds: Seconds the QUEUE strategy waited (0 for
            FALLBACK/ALERT).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    original_provider: NotBlankStr = Field(
        description="Provider that was quota-exhausted",
    )
    effective_provider: NotBlankStr = Field(
        description="Provider to use after degradation",
    )
    action_taken: DegradationAction = Field(
        description="Degradation action that was applied",
    )
    wait_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Seconds waited (QUEUE only)",
    )


class PreFlightResult(BaseModel):
    """Result of pre-flight budget enforcement.

    Attributes:
        effective_provider: Provider to use after degradation.
            ``None`` when no provider-level check was performed
            or the primary provider's quota was fine.
        degradation: Degradation result when degradation was triggered.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    effective_provider: NotBlankStr | None = Field(
        default=None,
        description="Effective provider after degradation",
    )
    degradation: DegradationResult | None = Field(
        default=None,
        description="Degradation result (None if not triggered)",
    )


# ── Helpers ───────────────────────────────────────────────────────


def always_allowed_result(provider_name: str) -> QuotaCheckResult:
    """Build an always-allowed QuotaCheckResult."""
    return QuotaCheckResult(
        allowed=True,
        provider_name=provider_name,
    )


# ── Public API ────────────────────────────────────────────────────


async def resolve_degradation(
    *,
    provider_name: str,
    quota_result: QuotaCheckResult,
    degradation_config: DegradationConfig,
    quota_tracker: QuotaTracker,
    estimated_tokens: int = 0,
) -> DegradationResult:
    """Resolve a quota exhaustion using the configured strategy.

    Dispatches to the appropriate strategy handler based on
    ``degradation_config.strategy``.

    Args:
        provider_name: The exhausted provider.
        quota_result: The denied quota check result.
        degradation_config: Degradation configuration for the provider.
        quota_tracker: Quota tracker for checking fallback providers.
        estimated_tokens: Estimated tokens for the upcoming request.

    Returns:
        Degradation result with the effective provider.

    Raises:
        QuotaExhaustedError: When the degradation strategy cannot
            resolve the exhaustion (all fallbacks exhausted, queue
            timeout exceeded, or ALERT strategy).
    """
    strategy = degradation_config.strategy

    if strategy == DegradationAction.FALLBACK:
        return await _resolve_fallback(
            provider_name=provider_name,
            degradation_config=degradation_config,
            quota_tracker=quota_tracker,
            estimated_tokens=estimated_tokens,
        )

    if strategy == DegradationAction.QUEUE:
        return await _resolve_queue(
            provider_name=provider_name,
            quota_result=quota_result,
            degradation_config=degradation_config,
            quota_tracker=quota_tracker,
            estimated_tokens=estimated_tokens,
        )

    # ALERT (default) -- raise immediately
    logger.warning(
        DEGRADATION_ALERT_RAISED,
        provider=provider_name,
        reason=quota_result.reason,
    )
    msg = f"Provider {provider_name!r} quota exhausted: {quota_result.reason}"
    raise QuotaExhaustedError(
        msg,
        provider_name=provider_name,
        degradation_action=DegradationAction.ALERT,
    )


# ── FALLBACK ──────────────────────────────────────────────────────


async def _resolve_fallback(
    *,
    provider_name: str,
    degradation_config: DegradationConfig,
    quota_tracker: QuotaTracker,
    estimated_tokens: int = 0,
) -> DegradationResult:
    """Walk the fallback provider list and return the first available.

    Raises:
        QuotaExhaustedError: When no fallback providers are configured
            or all are exhausted.
    """
    fallbacks = degradation_config.fallback_providers
    if not fallbacks:
        logger.warning(
            DEGRADATION_FALLBACK_EXHAUSTED,
            provider=provider_name,
            reason="no_fallback_providers_configured",
        )
        msg = f"No fallback providers configured for provider {provider_name!r}"
        raise QuotaExhaustedError(
            msg,
            provider_name=provider_name,
            degradation_action=DegradationAction.FALLBACK,
        )

    logger.info(
        DEGRADATION_FALLBACK_STARTED,
        provider=provider_name,
        fallback_count=len(fallbacks),
    )

    tried: list[str] = []
    for fallback_name in fallbacks:
        check = await quota_tracker.check_quota(
            fallback_name,
            estimated_tokens=estimated_tokens,
        )
        logger.debug(
            DEGRADATION_FALLBACK_PROVIDER_CHECKED,
            provider=fallback_name,
            allowed=check.allowed,
        )
        if check.allowed:
            logger.info(
                DEGRADATION_FALLBACK_RESOLVED,
                original_provider=provider_name,
                fallback_provider=fallback_name,
            )
            return DegradationResult(
                original_provider=provider_name,
                effective_provider=fallback_name,
                action_taken=DegradationAction.FALLBACK,
            )
        tried.append(fallback_name)

    logger.warning(
        DEGRADATION_FALLBACK_EXHAUSTED,
        provider=provider_name,
        tried=tried,
    )
    msg = (
        f"All fallback providers exhausted for "
        f"provider {provider_name!r}: tried {tried}"
    )
    raise QuotaExhaustedError(
        msg,
        provider_name=provider_name,
        degradation_action=DegradationAction.FALLBACK,
    )


# ── QUEUE ─────────────────────────────────────────────────────────


async def _resolve_queue(
    *,
    provider_name: str,
    quota_result: QuotaCheckResult,
    degradation_config: DegradationConfig,
    quota_tracker: QuotaTracker,
    estimated_tokens: int = 0,
) -> DegradationResult:
    """Wait for the shortest quota window to reset, then re-check.

    Raises:
        QuotaExhaustedError: When the wait would exceed
            ``queue_max_wait_seconds``, no reset time is available,
            or the quota is still exhausted after waiting.
    """
    max_wait = degradation_config.queue_max_wait_seconds

    logger.info(
        DEGRADATION_QUEUE_STARTED,
        provider=provider_name,
        max_wait_seconds=max_wait,
    )

    delay = await _compute_queue_delay(
        provider_name=provider_name,
        exhausted_windows=quota_result.exhausted_windows,
        quota_tracker=quota_tracker,
        max_wait=max_wait,
    )

    if delay > 0:
        logger.info(
            DEGRADATION_QUEUE_WAITING,
            provider=provider_name,
            delay_seconds=delay,
        )
        await asyncio_sleep(delay)

    # Re-check quota after waiting
    recheck = await quota_tracker.check_quota(
        provider_name,
        estimated_tokens=estimated_tokens,
    )
    if not recheck.allowed:
        logger.warning(
            DEGRADATION_QUEUE_EXHAUSTED,
            provider=provider_name,
            reason="still_exhausted_after_wait",
        )
        msg = f"Provider {provider_name!r} still exhausted after waiting {delay:.1f}s"
        raise QuotaExhaustedError(
            msg,
            provider_name=provider_name,
            degradation_action=DegradationAction.QUEUE,
        )

    logger.info(
        DEGRADATION_QUEUE_RESUMED,
        provider=provider_name,
        wait_seconds=delay,
    )
    return DegradationResult(
        original_provider=provider_name,
        effective_provider=provider_name,
        action_taken=DegradationAction.QUEUE,
        wait_seconds=delay,
    )


async def _compute_queue_delay(
    *,
    provider_name: str,
    exhausted_windows: tuple[QuotaWindow, ...],
    quota_tracker: QuotaTracker,
    max_wait: int,
) -> float:
    """Compute how long to wait for the soonest window reset.

    Returns 0.0 when the window has already rotated.

    Raises:
        QuotaExhaustedError: When no reset time is available or the
            shortest reset exceeds ``max_wait``.
    """
    snapshots = await quota_tracker.get_snapshot(provider_name)

    # Filter to exhausted windows that have a reset time
    reset_times: list[datetime] = [
        snap.window_resets_at
        for snap in snapshots
        if snap.window in exhausted_windows and snap.window_resets_at
    ]

    if not reset_times:
        msg = f"Provider {provider_name!r} quota exhausted but no reset time available"
        raise QuotaExhaustedError(
            msg,
            provider_name=provider_name,
            degradation_action=DegradationAction.QUEUE,
        )

    soonest = min(reset_times)
    now = datetime.now(UTC)
    delay = (soonest - now).total_seconds()

    if delay <= 0:
        return 0.0

    if delay > max_wait:
        msg = (
            f"Provider {provider_name!r} quota reset in "
            f"{delay:.0f}s exceeds max wait {max_wait}s"
        )
        raise QuotaExhaustedError(
            msg,
            provider_name=provider_name,
            degradation_action=DegradationAction.QUEUE,
        )

    return delay
