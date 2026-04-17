"""Per-operation rate limit configuration (#1391)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class PerOpRateLimitConfig(BaseModel):
    """Configuration for the per-operation rate limiter.

    Attributes:
        enabled: Master switch.  When ``False`` the guard becomes a
            no-op and ``acquire`` is never called.
        backend: Discriminator selecting the concrete
            :class:`SlidingWindowStore` strategy.
        overrides: Operator tuning knob.  Maps operation name to
            ``(max_requests, window_seconds)`` tuples that supersede
            the decorator defaults.  Use for zero-deploy limit changes
            during incidents.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = True
    backend: Literal["memory", "redis"] = "memory"
    overrides: dict[NotBlankStr, tuple[int, int]] = Field(default_factory=dict)
