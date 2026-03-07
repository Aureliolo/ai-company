"""Loop prevention check outcome model."""

from pydantic import BaseModel, ConfigDict, Field

from ai_company.core.types import NotBlankStr  # noqa: TC001


class GuardCheckOutcome(BaseModel):
    """Result of a single loop prevention check.

    Attributes:
        passed: Whether the check passed (delegation allowed).
        mechanism: Name of the mechanism that produced this outcome.
        message: Human-readable detail (empty on success).
    """

    model_config = ConfigDict(frozen=True)

    passed: bool = Field(description="Whether the check passed")
    mechanism: NotBlankStr = Field(
        description="Mechanism name (e.g. 'max_depth', 'ancestry')",
    )
    message: str = Field(
        default="",
        description="Human-readable detail",
    )
