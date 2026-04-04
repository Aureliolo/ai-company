"""Risk budget check result model."""

from pydantic import BaseModel, ConfigDict, Field


class RiskCheckResult(BaseModel):
    """Result of a risk budget pre-flight check.

    Attributes:
        allowed: Whether the action is within risk budget.
        risk_units: Estimated risk units for the action.
        reason: Human-readable explanation when denied.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    allowed: bool = True
    risk_units: float = Field(default=0.0, ge=0.0)
    reason: str = ""
