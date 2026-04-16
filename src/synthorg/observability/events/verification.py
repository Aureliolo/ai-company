"""Observability event constants for the verification subsystem."""

from typing import Final

VERIFICATION_NODE_STARTED: Final[str] = "verification.node.started"
VERIFICATION_CRITERIA_DECOMPOSED: Final[str] = "verification.criteria.decomposed"
VERIFICATION_HANDOFF_BUILT: Final[str] = "verification.handoff.built"
VERIFICATION_GRADING_STARTED: Final[str] = "verification.grading.started"
VERIFICATION_GRADING_COMPLETED: Final[str] = "verification.grading.completed"
VERIFICATION_SELF_EVAL_REJECTED: Final[str] = "verification.self_eval.rejected"
VERIFICATION_RUBRIC_NOT_FOUND: Final[str] = "verification.rubric.not_found"
VERIFICATION_GRADER_FAILED: Final[str] = "verification.grader.failed"
VERIFICATION_PROBE_FAILED: Final[str] = "verification.probe.failed"
VERIFICATION_VERDICT_ROUTED: Final[str] = "verification.verdict.routed"
VERIFICATION_VERDICT_OVERRIDDEN_TO_REFER: Final[str] = (
    "verification.verdict.overridden_to_refer"
)
VERIFICATION_FACTORY_UNKNOWN_DECOMPOSER: Final[str] = (
    "verification.factory.unknown_decomposer"
)
VERIFICATION_FACTORY_UNKNOWN_GRADER: Final[str] = "verification.factory.unknown_grader"
VERIFICATION_FACTORY_MISSING_PROVIDER: Final[str] = (
    "verification.factory.missing_provider"
)
VERIFICATION_DECOMPOSER_RESPONSE_INVALID: Final[str] = (
    "verification.decomposer.response_invalid"
)
VERIFICATION_GRADER_RESPONSE_INVALID: Final[str] = (
    "verification.grader.response_invalid"
)
VERIFICATION_DECOMPOSER_PROBE_REJECTED: Final[str] = (
    "verification.decomposer.probe_rejected"
)
VERIFICATION_GRADER_PAYLOAD_TRUNCATED: Final[str] = (
    "verification.grader.payload_truncated"
)
VERIFICATION_DECOMPOSER_CRITERIA_TRUNCATED: Final[str] = (
    "verification.decomposer.criteria_truncated"
)
VERIFICATION_GRADER_CONFIG_INVALID: Final[str] = "verification.grader.config_invalid"
