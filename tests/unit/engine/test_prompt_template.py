"""Tests for prompt template constants and autonomy instructions."""

import pytest

from synthorg.core.enums import SeniorityLevel
from synthorg.engine.prompt_template import (
    AUTONOMY_INSTRUCTIONS,
    AUTONOMY_MINIMAL,
    AUTONOMY_SUMMARY,
    DEFAULT_TEMPLATE,
)


@pytest.mark.unit
class TestAutonomyInstructions:
    """Tests for AUTONOMY_INSTRUCTIONS coverage and content."""

    def test_all_seniority_levels_covered(self) -> None:
        assert set(SeniorityLevel) == set(AUTONOMY_INSTRUCTIONS)

    def test_all_values_are_non_empty_strings(self) -> None:
        for level, instruction in AUTONOMY_INSTRUCTIONS.items():
            assert isinstance(instruction, str), f"{level} value is not a string"
            assert instruction.strip(), f"{level} has empty instruction text"

    def test_each_level_produces_different_text(self) -> None:
        values = list(AUTONOMY_INSTRUCTIONS.values())
        assert len(values) == len(set(values))


@pytest.mark.unit
class TestDefaultTemplate:
    """Tests for the default Jinja2 system prompt template."""

    def test_default_template_is_non_empty(self) -> None:
        assert isinstance(DEFAULT_TEMPLATE, str)
        assert DEFAULT_TEMPLATE.strip()


@pytest.mark.unit
class TestAutonomySummary:
    """Tests for AUTONOMY_SUMMARY coverage and content."""

    def test_all_seniority_levels_covered(self) -> None:
        assert set(SeniorityLevel) == set(AUTONOMY_SUMMARY)

    def test_all_values_are_non_empty_strings(self) -> None:
        for level, instruction in AUTONOMY_SUMMARY.items():
            assert isinstance(instruction, str), f"{level} value is not a string"
            assert instruction.strip(), f"{level} has empty instruction text"

    def test_each_level_produces_different_text(self) -> None:
        values = list(AUTONOMY_SUMMARY.values())
        assert len(values) == len(set(values))

    def test_summary_shorter_than_full(self) -> None:
        """Summary instructions are shorter than full instructions."""
        for level in SeniorityLevel:
            assert len(AUTONOMY_SUMMARY[level]) <= len(
                AUTONOMY_INSTRUCTIONS[level],
            )


@pytest.mark.unit
class TestAutonomyMinimal:
    """Tests for AUTONOMY_MINIMAL coverage and content."""

    def test_all_seniority_levels_covered(self) -> None:
        assert set(SeniorityLevel) == set(AUTONOMY_MINIMAL)

    def test_all_values_are_non_empty_strings(self) -> None:
        for level, instruction in AUTONOMY_MINIMAL.items():
            assert isinstance(instruction, str), f"{level} value is not a string"
            assert instruction.strip(), f"{level} has empty instruction text"

    def test_each_level_produces_different_text(self) -> None:
        values = list(AUTONOMY_MINIMAL.values())
        assert len(values) == len(set(values))

    def test_minimal_shorter_than_summary(self) -> None:
        """Minimal instructions are shorter than summary instructions."""
        for level in SeniorityLevel:
            assert len(AUTONOMY_MINIMAL[level]) <= len(
                AUTONOMY_SUMMARY[level],
            )


@pytest.mark.unit
class TestAutonomyInstructionsGuard:
    """Tests for the module-level guard that detects missing levels."""

    def test_guard_detects_missing_level(self) -> None:
        incomplete = dict(AUTONOMY_INSTRUCTIONS)
        removed_key = next(iter(incomplete))
        del incomplete[removed_key]

        missing = set(SeniorityLevel) - set(incomplete)
        assert removed_key in missing
