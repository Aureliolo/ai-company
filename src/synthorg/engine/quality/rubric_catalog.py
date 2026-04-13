"""Frozen registry of built-in verification rubrics."""

from types import MappingProxyType

from synthorg.engine.quality.verification import (
    FRONTEND_DESIGN_RUBRIC,
    RubricCriterion,
    VerificationRubric,
)

_DEFAULT_TASK_RUBRIC = VerificationRubric(
    name="default-task",
    criteria=(
        RubricCriterion(
            name="correctness",
            description="Output is factually and logically correct",
            weight=0.4,
            grade_type="score",
        ),
        RubricCriterion(
            name="completeness",
            description="All acceptance criteria are addressed",
            weight=0.35,
            grade_type="score",
        ),
        RubricCriterion(
            name="probe-adherence",
            description="Adherence to atomic acceptance probes",
            weight=0.25,
            grade_type="binary",
        ),
    ),
    calibration_examples=(),
    min_confidence=0.7,
)

BUILTIN_RUBRICS: MappingProxyType[str, VerificationRubric] = MappingProxyType(
    {
        FRONTEND_DESIGN_RUBRIC.name: FRONTEND_DESIGN_RUBRIC,
        _DEFAULT_TASK_RUBRIC.name: _DEFAULT_TASK_RUBRIC,
    }
)
"""Immutable registry of built-in rubrics keyed by name."""


def get_rubric(name: str) -> VerificationRubric:
    """Look up a rubric by name.

    Args:
        name: Rubric identifier.

    Returns:
        The matching rubric.

    Raises:
        KeyError: If no rubric with that name exists.
    """
    try:
        return BUILTIN_RUBRICS[name]
    except KeyError:
        available = sorted(BUILTIN_RUBRICS.keys())
        msg = f"Unknown rubric {name!r}, available: {available}"
        raise KeyError(msg) from None
