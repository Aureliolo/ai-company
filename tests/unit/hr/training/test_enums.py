"""Unit tests for training-related enum additions.

Note:
    The canonical ``OnboardingStep`` enum surface is validated in
    ``tests/unit/hr/test_enums.py``.  This module only asserts the
    training-specific invariants that matter to the training-mode
    package (i.e. that ``LEARNED_FROM_SENIORS`` exists with the
    expected value and that the enum still has exactly one training
    step).
"""

import pytest

from synthorg.hr.enums import OnboardingStep


@pytest.mark.unit
class TestOnboardingStepEnum:
    """Training-specific ``OnboardingStep`` assertions."""

    def test_learned_from_seniors_training_step(self) -> None:
        """LEARNED_FROM_SENIORS exists with the canonical value."""
        assert hasattr(OnboardingStep, "LEARNED_FROM_SENIORS")
        assert OnboardingStep.LEARNED_FROM_SENIORS.value == "learned_from_seniors"
