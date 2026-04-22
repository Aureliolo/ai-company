"""Per-operation rate limit configuration (#1391)."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_APP_STARTUP

logger = get_logger(__name__)

_OVERRIDE_TUPLE_LEN = 2


class PerOpRateLimitConfig(BaseModel):
    """Configuration for the per-operation rate limiter.

    Attributes:
        enabled: Master switch.  When ``False`` the guard becomes a
            no-op and ``acquire`` is never called.
        backend: Discriminator selecting the concrete
            :class:`SlidingWindowStore` strategy.
        overrides: Operator tuning knob.  Maps operation name to
            ``(max_requests, window_seconds)`` tuples that supersede
            the decorator defaults.  Use ``0`` in either position to
            explicitly disable an operation (the guard short-circuits).
            Negative values are invalid and rejected at startup.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = True
    backend: Literal["memory"] = "memory"
    overrides: dict[NotBlankStr, tuple[int, int]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_override_tuples(self) -> Self:
        """Reject override tuples with malformed (non-integer, negative) values.

        Zero is allowed and means "disable this operation" -- the guard
        short-circuits when either component is ``0``.  Negative values
        are rejected because they express no meaningful intent.  Bad
        configs are logged at WARNING before the ValueError is raised
        so operator-facing config errors surface with context.
        """
        for operation, pair in self.overrides.items():
            if len(pair) != _OVERRIDE_TUPLE_LEN:
                msg = (
                    f"overrides[{operation!r}]={pair!r} must be a "
                    "(max_requests, window_seconds) 2-tuple"
                )
                logger.warning(
                    API_APP_STARTUP,
                    operation=operation,
                    override=str(pair),
                    error=msg,
                )
                raise ValueError(msg)
            max_req, window = pair
            if max_req < 0 or window < 0:
                msg = (
                    f"overrides[{operation!r}]={pair!r} has negative values; "
                    "use 0 to disable an operation"
                )
                logger.warning(
                    API_APP_STARTUP,
                    operation=operation,
                    override=str(pair),
                    error=msg,
                )
                raise ValueError(msg)
        return self
