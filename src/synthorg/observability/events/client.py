"""Client simulation event constants."""

from typing import Final

CLIENT_REQUEST_SUBMITTED: Final[str] = "client.request.submitted"
CLIENT_REQUEST_TRIAGING: Final[str] = "client.request.triaging"
CLIENT_REQUEST_SCOPED: Final[str] = "client.request.scoped"
CLIENT_REQUEST_APPROVED: Final[str] = "client.request.approved"
CLIENT_REQUEST_REJECTED: Final[str] = "client.request.rejected"
CLIENT_REVIEW_STARTED: Final[str] = "client.review.started"
CLIENT_REVIEW_COMPLETED: Final[str] = "client.review.completed"
CLIENT_FEEDBACK_RECORDED: Final[str] = "client.feedback.recorded"
CLIENT_REQUIREMENT_GENERATED: Final[str] = "client.requirement.generated"
SIMULATION_RUN_STARTED: Final[str] = "simulation.run.started"
SIMULATION_RUN_COMPLETED: Final[str] = "simulation.run.completed"
SIMULATION_ROUND_COMPLETED: Final[str] = "simulation.round.completed"
