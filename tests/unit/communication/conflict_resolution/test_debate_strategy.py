"""Tests for the structured debate + judge resolution strategy."""

import pytest

from ai_company.communication.conflict_resolution.config import DebateConfig
from ai_company.communication.conflict_resolution.debate_strategy import (
    DebateResolver,
)
from ai_company.communication.conflict_resolution.models import (
    Conflict,
    ConflictResolutionOutcome,
)
from ai_company.communication.delegation.hierarchy import (
    HierarchyResolver,  # noqa: TC001
)
from ai_company.communication.enums import ConflictResolutionStrategy
from ai_company.communication.errors import (
    ConflictHierarchyError,
    ConflictStrategyError,
)
from ai_company.core.enums import SeniorityLevel

from .conftest import make_conflict, make_position

pytestmark = pytest.mark.timeout(30)


class FakeJudgeEvaluator:
    """Fake judge evaluator for testing."""

    def __init__(self, winner_id: str, reasoning: str = "Judge decided") -> None:
        self._winner_id = winner_id
        self._reasoning = reasoning
        self.calls: list[tuple[Conflict, str]] = []

    async def evaluate(
        self,
        conflict: Conflict,
        judge_agent_id: str,
    ) -> tuple[str, str]:
        self.calls.append((conflict, judge_agent_id))
        return self._winner_id, self._reasoning


@pytest.mark.unit
class TestDebateResolverWithJudge:
    async def test_judge_evaluator_picks_winner(
        self,
        hierarchy: HierarchyResolver,
    ) -> None:
        judge = FakeJudgeEvaluator(winner_id="sr_dev")
        resolver = DebateResolver(
            hierarchy=hierarchy,
            config=DebateConfig(judge="shared_manager"),
            judge_evaluator=judge,
        )
        conflict = make_conflict(
            positions=(
                make_position(agent_id="sr_dev", level=SeniorityLevel.SENIOR),
                make_position(
                    agent_id="jr_dev",
                    level=SeniorityLevel.JUNIOR,
                    position="Other",
                ),
            ),
        )
        resolution = await resolver.resolve(conflict)
        assert resolution.winning_agent_id == "sr_dev"
        assert resolution.outcome == ConflictResolutionOutcome.RESOLVED_BY_DEBATE
        assert len(judge.calls) == 1

    async def test_judge_receives_correct_agent_id(
        self,
        hierarchy: HierarchyResolver,
    ) -> None:
        judge = FakeJudgeEvaluator(winner_id="sr_dev")
        resolver = DebateResolver(
            hierarchy=hierarchy,
            config=DebateConfig(judge="shared_manager"),
            judge_evaluator=judge,
        )
        conflict = make_conflict(
            positions=(
                make_position(agent_id="sr_dev", level=SeniorityLevel.SENIOR),
                make_position(
                    agent_id="jr_dev",
                    level=SeniorityLevel.JUNIOR,
                    position="Other",
                ),
            ),
        )
        await resolver.resolve(conflict)
        # shared_manager of sr_dev and jr_dev is backend_lead
        _, judge_id = judge.calls[0]
        assert judge_id == "backend_lead"


@pytest.mark.unit
class TestDebateResolverFallback:
    async def test_no_evaluator_falls_back_to_authority(
        self,
        hierarchy: HierarchyResolver,
    ) -> None:
        resolver = DebateResolver(
            hierarchy=hierarchy,
            config=DebateConfig(),
            judge_evaluator=None,
        )
        conflict = make_conflict(
            positions=(
                make_position(
                    agent_id="sr_dev",
                    level=SeniorityLevel.SENIOR,
                    position="Approach A",
                ),
                make_position(
                    agent_id="jr_dev",
                    level=SeniorityLevel.JUNIOR,
                    position="Approach B",
                ),
            ),
        )
        resolution = await resolver.resolve(conflict)
        assert resolution.winning_agent_id == "sr_dev"
        assert "fallback" in resolution.reasoning.lower()


@pytest.mark.unit
class TestDebateJudgeSelection:
    async def test_ceo_judge(
        self,
        hierarchy: HierarchyResolver,
    ) -> None:
        judge = FakeJudgeEvaluator(winner_id="sr_dev")
        resolver = DebateResolver(
            hierarchy=hierarchy,
            config=DebateConfig(judge="ceo"),
            judge_evaluator=judge,
        )
        conflict = make_conflict(
            positions=(
                make_position(agent_id="sr_dev", level=SeniorityLevel.SENIOR),
                make_position(
                    agent_id="jr_dev",
                    level=SeniorityLevel.JUNIOR,
                    position="Other",
                ),
            ),
        )
        await resolver.resolve(conflict)
        _, judge_id = judge.calls[0]
        # Root of sr_dev's hierarchy is cto
        assert judge_id == "cto"

    async def test_named_judge(
        self,
        hierarchy: HierarchyResolver,
    ) -> None:
        judge = FakeJudgeEvaluator(winner_id="sr_dev")
        resolver = DebateResolver(
            hierarchy=hierarchy,
            config=DebateConfig(judge="external_reviewer"),
            judge_evaluator=judge,
        )
        conflict = make_conflict(
            positions=(
                make_position(agent_id="sr_dev", level=SeniorityLevel.SENIOR),
                make_position(
                    agent_id="jr_dev",
                    level=SeniorityLevel.JUNIOR,
                    position="Other",
                ),
            ),
        )
        await resolver.resolve(conflict)
        _, judge_id = judge.calls[0]
        assert judge_id == "external_reviewer"

    async def test_shared_manager_no_lcm_raises(
        self,
        hierarchy: HierarchyResolver,
    ) -> None:
        resolver = DebateResolver(
            hierarchy=hierarchy,
            config=DebateConfig(judge="shared_manager"),
        )
        conflict = make_conflict(
            positions=(
                make_position(
                    agent_id="cto",
                    level=SeniorityLevel.C_SUITE,
                ),
                make_position(
                    agent_id="qa_head",
                    level=SeniorityLevel.C_SUITE,
                    position="Other",
                    department="qa",
                ),
            ),
        )
        with pytest.raises(ConflictHierarchyError):
            await resolver.resolve(conflict)


@pytest.mark.unit
class TestDebateResolverDissentRecord:
    async def test_dissent_record_includes_judge(
        self,
        hierarchy: HierarchyResolver,
    ) -> None:
        judge = FakeJudgeEvaluator(winner_id="sr_dev")
        resolver = DebateResolver(
            hierarchy=hierarchy,
            config=DebateConfig(judge="shared_manager"),
            judge_evaluator=judge,
        )
        conflict = make_conflict(
            positions=(
                make_position(agent_id="sr_dev", level=SeniorityLevel.SENIOR),
                make_position(
                    agent_id="jr_dev",
                    level=SeniorityLevel.JUNIOR,
                    position="Other approach",
                ),
            ),
        )
        resolution = await resolver.resolve(conflict)
        record = resolver.build_dissent_record(conflict, resolution)
        assert record.dissenting_agent_id == "jr_dev"
        assert record.strategy_used == ConflictResolutionStrategy.DEBATE
        assert ("judge", resolution.decided_by) in record.metadata


@pytest.mark.unit
class TestDebateResolverInvalidWinner:
    async def test_judge_returns_unknown_agent_raises(
        self,
        hierarchy: HierarchyResolver,
    ) -> None:
        judge = FakeJudgeEvaluator(winner_id="nonexistent_agent")
        resolver = DebateResolver(
            hierarchy=hierarchy,
            config=DebateConfig(judge="shared_manager"),
            judge_evaluator=judge,
        )
        conflict = make_conflict(
            positions=(
                make_position(agent_id="sr_dev", level=SeniorityLevel.SENIOR),
                make_position(
                    agent_id="jr_dev",
                    level=SeniorityLevel.JUNIOR,
                    position="Other",
                ),
            ),
        )
        with pytest.raises(ConflictStrategyError, match="not found"):
            await resolver.resolve(conflict)
