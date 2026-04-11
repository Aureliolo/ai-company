"""Unit tests for training-related enum additions."""

import pytest

from synthorg.hr.enums import OnboardingStep


@pytest.mark.unit
class TestOnboardingStepEnum:
    """Tests for LEARNED_FROM_SENIORS enum value."""

    def test_learned_from_seniors_exists(self) -> None:
        assert hasattr(OnboardingStep, "LEARNED_FROM_SENIORS")

    def test_learned_from_seniors_value(self) -> None:
        assert OnboardingStep.LEARNED_FROM_SENIORS.value == "learned_from_seniors"

    def test_has_four_members(self) -> None:
        assert len(OnboardingStep) == 4

    def test_all_values(self) -> None:
        values = {step.value for step in OnboardingStep}
        assert values == {
            "company_context",
            "project_briefing",
            "team_introductions",
            "learned_from_seniors",
        }
