"""Tests for skill signal source."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.signals.skill import SkillSignalSource

_AGENT_IDS = (NotBlankStr("a1"), NotBlankStr("a2"))


@pytest.mark.unit
class TestSkillSignalSource:
    """SkillSignalSource signal collection."""

    @pytest.mark.parametrize(
        ("agent_skills", "required_skills", "expected_coverage", "expected_missing"),
        [
            ({}, (), 1.0, 0.0),
            (
                {"a1": ("python", "litestar"), "a2": ("react",)},
                ("python", "react"),
                1.0,
                0.0,
            ),
            (
                {"a1": ("python",)},
                ("python", "react", "go"),
                pytest.approx(1 / 3, rel=0.01),
                2.0,
            ),
            ({}, ("python",), 0.0, 1.0),
        ],
        ids=[
            "no-requirements-full-coverage",
            "full-coverage",
            "partial-coverage",
            "no-agents-no-skills",
        ],
    )
    async def test_coverage_scenarios(
        self,
        agent_skills: dict[str, tuple[str, ...]],
        required_skills: tuple[str, ...],
        expected_coverage: float,
        expected_missing: float,
    ) -> None:
        source = SkillSignalSource()
        signals = await source.collect(
            _AGENT_IDS,
            agent_skills=agent_skills,
            required_skills=required_skills,
        )
        by_name = {s.name: s.value for s in signals}
        assert by_name["coverage_ratio"] == expected_coverage
        assert by_name["missing_skill_count"] == expected_missing

    async def test_source_name(self) -> None:
        source = SkillSignalSource()
        assert source.name == "skill"
