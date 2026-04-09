"""Intake engine domain models.

Defines the data structures for intake processing results.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class IntakeResult(BaseModel):
    """Outcome of processing a client request through intake.

    Attributes:
        request_id: ID of the processed request.
        accepted: Whether the request was accepted.
        task_id: ID of the created task (only when accepted).
        rejection_reason: Reason for rejection (only when rejected).
        processed_at: Timestamp of processing completion.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    request_id: NotBlankStr = Field(
        description="ID of the processed request",
    )
    accepted: bool = Field(
        description="Whether the request was accepted",
    )
    task_id: NotBlankStr | None = Field(
        default=None,
        description="ID of the created task (when accepted)",
    )
    rejection_reason: NotBlankStr | None = Field(
        default=None,
        description="Reason for rejection (when rejected)",
    )
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of processing completion",
    )

    @classmethod
    def accepted_result(
        cls,
        *,
        request_id: str,
        task_id: str,
    ) -> IntakeResult:
        """Create an accepted intake result.

        Args:
            request_id: ID of the processed request.
            task_id: ID of the created task.

        Returns:
            An accepted IntakeResult.
        """
        return cls(
            request_id=request_id,
            accepted=True,
            task_id=task_id,
        )

    @classmethod
    def rejected_result(
        cls,
        *,
        request_id: str,
        reason: str,
    ) -> IntakeResult:
        """Create a rejected intake result.

        Args:
            request_id: ID of the processed request.
            reason: Reason for rejection.

        Returns:
            A rejected IntakeResult.
        """
        return cls(
            request_id=request_id,
            accepted=False,
            rejection_reason=reason,
        )
