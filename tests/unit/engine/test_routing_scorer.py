"""Tests for agent-task scorer."""

from datetime import date
from uuid import uuid4

import pytest

from synthorg.core.agent import AgentIdentity, ModelConfig, SkillSet
from synthorg.core.enums import AgentStatus, Complexity, SeniorityLevel
from synthorg.core.role import Skill
from synthorg.engine.decomposition.models import SubtaskDefinition
from synthorg.engine.routing.scorer import AgentTaskScorer


def _as_skills(
    ids_or_skills: tuple[str | Skill, ...],
) -> tuple[Skill, ...]:
    """Accept bare IDs or Skill objects and return a tuple of Skills."""
    return tuple(
        s if isinstance(s, Skill) else Skill(id=s, name=s) for s in ids_or_skills
    )


def _make_agent(
    *,
    primary: tuple[str | Skill, ...] = (),
    secondary: tuple[str | Skill, ...] = (),
    role: str = "developer",
    level: SeniorityLevel = SeniorityLevel.MID,
    status: AgentStatus = AgentStatus.ACTIVE,
) -> AgentIdentity:
    """Helper to create an agent with specific skills."""
    return AgentIdentity(
        id=uuid4(),
        name="Test Agent",
        role=role,
        department="Engineering",
        level=level,
        skills=SkillSet(
            primary=_as_skills(primary),
            secondary=_as_skills(secondary),
        ),
        model=ModelConfig(provider="test-provider", model_id="test-model-001"),
        hiring_date=date(2026, 1, 1),
        status=status,
    )


def _make_subtask(
    *,
    required_skills: tuple[str, ...] = (),
    required_tags: tuple[str, ...] = (),
    required_role: str | None = None,
    complexity: Complexity = Complexity.MEDIUM,
) -> SubtaskDefinition:
    """Helper to create a subtask with requirements."""
    return SubtaskDefinition(
        id="sub-test",
        title="Test Subtask",
        description="A test subtask",
        required_skills=required_skills,
        required_tags=required_tags,
        required_role=required_role,
        estimated_complexity=complexity,
    )


class TestAgentTaskScorer:
    """Tests for AgentTaskScorer."""

    @pytest.mark.unit
    def test_inactive_agent_scores_zero(self) -> None:
        """Inactive agent gets score 0.0."""
        scorer = AgentTaskScorer()
        agent = _make_agent(status=AgentStatus.TERMINATED)
        subtask = _make_subtask(required_skills=("python",))

        candidate = scorer.score(agent, subtask)
        assert candidate.score == 0.0

    @pytest.mark.unit
    def test_primary_skill_match(self) -> None:
        """Primary skill overlap contributes to score."""
        scorer = AgentTaskScorer()
        agent = _make_agent(primary=("python", "sql"))
        subtask = _make_subtask(required_skills=("python",))

        candidate = scorer.score(agent, subtask)
        assert candidate.score >= 0.4  # Full primary match
        assert "python" in candidate.matched_skills

    @pytest.mark.unit
    def test_secondary_skill_match(self) -> None:
        """Secondary skill overlap contributes to score."""
        scorer = AgentTaskScorer()
        agent = _make_agent(secondary=("python",))
        subtask = _make_subtask(required_skills=("python",))

        candidate = scorer.score(agent, subtask)
        assert candidate.score >= 0.2  # Full secondary match
        assert "python" in candidate.matched_skills

    @pytest.mark.unit
    def test_role_match(self) -> None:
        """Role match adds to score."""
        scorer = AgentTaskScorer()
        agent = _make_agent(role="backend-developer")
        subtask = _make_subtask(required_role="backend-developer")

        candidate = scorer.score(agent, subtask)
        assert candidate.score >= 0.2

    @pytest.mark.unit
    def test_role_match_case_insensitive(self) -> None:
        """Role comparison is case-insensitive."""
        scorer = AgentTaskScorer()
        agent = _make_agent(role="Backend-Developer")
        subtask = _make_subtask(required_role="backend-developer")

        candidate = scorer.score(agent, subtask)
        assert candidate.score >= 0.2

    @pytest.mark.unit
    def test_seniority_complexity_alignment(self) -> None:
        """Seniority-complexity alignment adds to score."""
        scorer = AgentTaskScorer()
        agent = _make_agent(level=SeniorityLevel.SENIOR)
        subtask = _make_subtask(complexity=Complexity.COMPLEX)

        candidate = scorer.score(agent, subtask)
        assert candidate.score >= 0.2

    @pytest.mark.unit
    def test_score_capped_at_one(self) -> None:
        """Score is capped at 1.0."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            primary=("python", "sql"),
            secondary=("testing",),
            role="developer",
            level=SeniorityLevel.MID,
        )
        subtask = _make_subtask(
            required_skills=("python",),
            required_role="developer",
            complexity=Complexity.MEDIUM,
        )

        candidate = scorer.score(agent, subtask)
        assert candidate.score <= 1.0

    @pytest.mark.unit
    def test_no_match(self) -> None:
        """No matching criteria gives low score."""
        scorer = AgentTaskScorer()
        agent = _make_agent(primary=("java",), role="frontend")
        subtask = _make_subtask(
            required_skills=("python",),
            required_role="backend",
            complexity=Complexity.EPIC,
        )

        candidate = scorer.score(agent, subtask)
        assert candidate.score == 0.0

    @pytest.mark.unit
    def test_min_score_property(self) -> None:
        """min_score is accessible."""
        scorer = AgentTaskScorer(min_score=0.3)
        assert scorer.min_score == 0.3

    @pytest.mark.unit
    def test_no_required_skills(self) -> None:
        """Agent with no required skills gets seniority + role scores."""
        scorer = AgentTaskScorer()
        agent = _make_agent(level=SeniorityLevel.MID, role="developer")
        subtask = _make_subtask(
            required_role="developer",
            complexity=Complexity.MEDIUM,
        )

        candidate = scorer.score(agent, subtask)
        # Role match (0.2) + seniority alignment (0.2) = 0.4
        assert candidate.score == pytest.approx(0.4)

    @pytest.mark.unit
    def test_on_leave_agent_scores_zero(self) -> None:
        """ON_LEAVE agent gets score 0.0."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            primary=("python",),
            status=AgentStatus.ON_LEAVE,
        )
        subtask = _make_subtask(required_skills=("python",))

        candidate = scorer.score(agent, subtask)
        assert candidate.score == 0.0

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("level", "complexity"),
        [
            (SeniorityLevel.JUNIOR, Complexity.SIMPLE),
            (SeniorityLevel.MID, Complexity.MEDIUM),
            (SeniorityLevel.SENIOR, Complexity.COMPLEX),
            (SeniorityLevel.LEAD, Complexity.EPIC),
            (SeniorityLevel.PRINCIPAL, Complexity.EPIC),
            (SeniorityLevel.DIRECTOR, Complexity.EPIC),
            (SeniorityLevel.VP, Complexity.EPIC),
            (SeniorityLevel.C_SUITE, Complexity.EPIC),
        ],
        ids=[
            "junior-simple",
            "mid-medium",
            "senior-complex",
            "lead-epic",
            "principal-epic",
            "director-epic",
            "vp-epic",
            "c_suite-epic",
        ],
    )
    def test_seniority_complexity_parametrized(
        self, level: SeniorityLevel, complexity: Complexity
    ) -> None:
        """Seniority-complexity alignment works for various levels."""
        scorer = AgentTaskScorer()
        agent = _make_agent(level=level)
        subtask = _make_subtask(complexity=complexity)

        candidate = scorer.score(agent, subtask)
        assert candidate.score >= 0.2

    @pytest.mark.unit
    def test_skill_in_both_primary_and_secondary(self) -> None:
        """Skill in both primary and secondary is not double-counted."""
        scorer = AgentTaskScorer()
        agent = _make_agent(primary=("python",), secondary=("python",))
        subtask = _make_subtask(required_skills=("python",))

        candidate = scorer.score(agent, subtask)
        # Primary match gives 0.4, secondary should not add 0.2
        # plus seniority alignment (MID + MEDIUM = 0.2) = 0.6
        assert candidate.score == pytest.approx(0.6)
        assert candidate.matched_skills.count("python") == 1

    @pytest.mark.unit
    def test_min_score_negative_rejected(self) -> None:
        """Negative min_score is rejected."""
        with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
            AgentTaskScorer(min_score=-0.5)

    @pytest.mark.unit
    def test_min_score_above_one_rejected(self) -> None:
        """min_score above 1.0 is rejected."""
        with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
            AgentTaskScorer(min_score=1.5)

    @pytest.mark.unit
    def test_proficiency_weighted_primary(self) -> None:
        """Primary skill proficiency linearly scales the tier contribution."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            primary=(Skill(id="python", name="Python", proficiency=0.5),),
            level=SeniorityLevel.JUNIOR,  # no seniority alignment for MEDIUM
        )
        subtask = _make_subtask(required_skills=("python",))

        candidate = scorer.score(agent, subtask)
        # primary contribution = 0.5 (proficiency) / 1 (required) * 0.4 = 0.2
        assert candidate.score == pytest.approx(0.2)
        assert "python" in candidate.matched_skills

    @pytest.mark.unit
    def test_proficiency_weighted_secondary(self) -> None:
        """Secondary skill proficiency linearly scales the tier contribution."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            secondary=(Skill(id="python", name="Python", proficiency=0.5),),
            level=SeniorityLevel.JUNIOR,
        )
        subtask = _make_subtask(required_skills=("python",))

        candidate = scorer.score(agent, subtask)
        # secondary contribution = 0.5 / 1 * 0.2 = 0.1
        assert candidate.score == pytest.approx(0.1)

    @pytest.mark.unit
    def test_default_proficiency_matches_legacy_score(self) -> None:
        """Default ``proficiency=1.0`` reproduces legacy boolean-match score."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            primary=("python",),
            level=SeniorityLevel.JUNIOR,
        )
        subtask = _make_subtask(required_skills=("python",))

        candidate = scorer.score(agent, subtask)
        # Full primary match at proficiency 1.0 = 0.4 (no other contributions)
        assert candidate.score == pytest.approx(0.4)

    @pytest.mark.unit
    def test_higher_proficiency_outranks_lower(self) -> None:
        """Quality-aware routing: higher proficiency wins ties."""
        scorer = AgentTaskScorer()
        high = _make_agent(
            primary=(Skill(id="python", name="Python", proficiency=0.9),),
            level=SeniorityLevel.JUNIOR,
        )
        low = _make_agent(
            primary=(Skill(id="python", name="Python", proficiency=0.3),),
            level=SeniorityLevel.JUNIOR,
        )
        subtask = _make_subtask(required_skills=("python",))

        assert scorer.score(high, subtask).score > scorer.score(low, subtask).score

    @pytest.mark.unit
    def test_tag_match_adds_bonus(self) -> None:
        """Tag match adds +0.1 when all required tags are covered."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            primary=(Skill(id="python", name="Python", tags=("backend", "async")),),
            level=SeniorityLevel.JUNIOR,
        )
        subtask = _make_subtask(
            required_skills=("python",),
            required_tags=("backend",),
        )
        candidate = scorer.score(agent, subtask)
        # primary (0.4) + tag (0.1) = 0.5
        assert candidate.score == pytest.approx(0.5)

    @pytest.mark.unit
    def test_tag_match_requires_full_coverage(self) -> None:
        """Tag match only fires when EVERY required tag is present."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            primary=(Skill(id="python", name="Python", tags=("backend",)),),
            level=SeniorityLevel.JUNIOR,
        )
        subtask = _make_subtask(
            required_skills=("python",),
            required_tags=("backend", "realtime"),
        )
        candidate = scorer.score(agent, subtask)
        # primary only, no tag bonus
        assert candidate.score == pytest.approx(0.4)

    @pytest.mark.unit
    def test_tag_match_skipped_without_required_tags(self) -> None:
        """Tag match tier is silent when required_tags is empty."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            primary=(Skill(id="python", name="Python", tags=("backend",)),),
            level=SeniorityLevel.JUNIOR,
        )
        subtask = _make_subtask(required_skills=("python",))
        candidate = scorer.score(agent, subtask)
        assert candidate.score == pytest.approx(0.4)

    @pytest.mark.unit
    def test_tag_match_skipped_without_matched_skills(self) -> None:
        """Tag match does not fire when no skills were matched."""
        scorer = AgentTaskScorer()
        agent = _make_agent(
            primary=(Skill(id="rust", name="Rust", tags=("backend",)),),
            level=SeniorityLevel.JUNIOR,
        )
        subtask = _make_subtask(
            required_skills=("python",),
            required_tags=("backend",),
        )
        candidate = scorer.score(agent, subtask)
        # No primary match (different id), so no tags to consider.
        assert candidate.score == 0.0
