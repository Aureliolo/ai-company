"""Tests for skill signal source."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.signals.skill import SkillSignalSource

_AGENT_IDS = (NotBlankStr("a1"), NotBlankStr("a2"))


@pytest.mark.unit
class TestSkillSignalSource:
    """SkillSignalSource signal collection."""

    async def test_no_requirements_full_coverage(self) -> None:
        source = SkillSignalSource()
        signals = await source.collect(_AGENT_IDS, required_skills=())
        by_name = {s.name: s.value for s in signals}
        assert by_name["coverage_ratio"] == 1.0
        assert by_name["missing_skill_count"] == 0.0

    async def test_full_coverage(self) -> None:
        source = SkillSignalSource()
        signals = await source.collect(
            _AGENT_IDS,
            agent_skills={"a1": ("python", "litestar"), "a2": ("react",)},
            required_skills=("python", "react"),
        )
        by_name = {s.name: s.value for s in signals}
        assert by_name["coverage_ratio"] == 1.0
        assert by_name["missing_skill_count"] == 0.0

    async def test_partial_coverage(self) -> None:
        source = SkillSignalSource()
        signals = await source.collect(
            _AGENT_IDS,
            agent_skills={"a1": ("python",)},
            required_skills=("python", "react", "go"),
        )
        by_name = {s.name: s.value for s in signals}
        assert by_name["coverage_ratio"] == pytest.approx(1 / 3, rel=0.01)
        assert by_name["missing_skill_count"] == 2.0

    async def test_no_agents_no_skills(self) -> None:
        source = SkillSignalSource()
        signals = await source.collect(
            _AGENT_IDS,
            agent_skills={},
            required_skills=("python",),
        )
        by_name = {s.name: s.value for s in signals}
        assert by_name["coverage_ratio"] == 0.0
        assert by_name["missing_skill_count"] == 1.0

    async def test_source_name(self) -> None:
        source = SkillSignalSource()
        assert source.name == "skill"
