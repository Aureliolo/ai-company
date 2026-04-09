"""Review pipeline and intake engine event constants."""

from typing import Final

REVIEW_PIPELINE_STARTED: Final[str] = "review.pipeline.started"
REVIEW_PIPELINE_STAGE_COMPLETED: Final[str] = "review.pipeline.stage.completed"
REVIEW_PIPELINE_COMPLETED: Final[str] = "review.pipeline.completed"
INTAKE_REQUEST_RECEIVED: Final[str] = "intake.request.received"
INTAKE_REQUEST_ACCEPTED: Final[str] = "intake.request.accepted"
INTAKE_REQUEST_REJECTED: Final[str] = "intake.request.rejected"
