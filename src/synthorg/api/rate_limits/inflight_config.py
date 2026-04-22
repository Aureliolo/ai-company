"""Per-operation inflight-concurrency configuration (#1489, SEC-2)."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_APP_STARTUP

logger = get_logger(__name__)


class PerOpConcurrencyConfig(BaseModel):
    """Configuration for the per-operation inflight limiter.

    Attributes:
        enabled: Master switch.  When ``False`` the middleware becomes
            a no-op and never attempts to acquire permits.
        backend: Discriminator selecting the concrete
            :class:`InflightStore` strategy.
        overrides: Operator tuning knob.  Maps operation name to
            ``max_inflight`` (positive integer) that supersedes the
            decorator defaults.  Use ``0`` to explicitly disable an
            operation (the middleware short-circuits and lets every
            request through).  Negative values are invalid and rejected
            at startup.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = True
    backend: Literal["memory", "redis"] = "memory"
    overrides: dict[NotBlankStr, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_override_values(self) -> Self:
        """Reject negative override values.

        Zero is allowed and means "disable this operation" -- the
        middleware short-circuits when the override is ``0``.  Bad
        configs are logged at WARNING before the ValueError is raised
        so operator-facing config errors surface with context.
        """
        for operation, value in self.overrides.items():
            if value < 0:
                msg = (
                    f"overrides[{operation!r}]={value!r} has negative value; "
                    "use 0 to disable an operation"
                )
                logger.warning(
                    API_APP_STARTUP,
                    operation=operation,
                    override=value,
                    error=msg,
                )
                raise ValueError(msg)
        return self
