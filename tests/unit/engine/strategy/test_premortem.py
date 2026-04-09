"""Unit tests for premortem analysis."""

import pytest
from pydantic import ValidationError

from synthorg.communication.meeting.models import AgentResponse
from synthorg.engine.strategy.models import (
    PremortemConfig,
    PremortemParticipation,
    RiskCard,
)
from synthorg.engine.strategy.premortem import (
    DefaultPremortermExecutor,
    FailureMode,
    PremortermExecutor,
    PremortermOutput,
)


class TestFailureMode:
    """Tests for FailureMode model."""

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """FailureMode should be frozen."""
        mode = FailureMode(description="System overload")
        with pytest.raises(ValidationError):
            mode.description = "Different"  # type: ignore[misc]

    @pytest.mark.unit
    def test_defaults(self) -> None:
        """Default values for likelihood, impact, mitigation."""
        mode = FailureMode(description="Something fails")
        assert mode.likelihood == "medium"
        assert mode.impact == "medium"
        assert mode.mitigation == "No mitigation identified"

    @pytest.mark.unit
    def test_valid_likelihood_values(self) -> None:
        """likelihood must be low/medium/high."""
        for likelihood in ["low", "medium", "high"]:
            mode = FailureMode(
                description="Test",
                likelihood=likelihood,  # type: ignore[arg-type]
            )
            assert mode.likelihood == likelihood

        with pytest.raises(ValidationError):
            FailureMode(description="Test", likelihood="very_high")  # type: ignore[arg-type]

    @pytest.mark.unit
    def test_valid_impact_values(self) -> None:
        """impact must be low/medium/high."""
        for impact in ["low", "medium", "high"]:
            mode = FailureMode(
                description="Test",
                impact=impact,  # type: ignore[arg-type]
            )
            assert mode.impact == impact

        with pytest.raises(ValidationError):
            FailureMode(description="Test", impact="severe")  # type: ignore[arg-type]

    @pytest.mark.unit
    def test_custom_mitigation(self) -> None:
        """Custom mitigation can be provided."""
        mode = FailureMode(
            description="Database failure",
            mitigation="Implement connection pooling",
        )
        assert mode.mitigation == "Implement connection pooling"


class TestPremortermOutput:
    """Tests for PremortermOutput model."""

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """PremortermOutput should be frozen."""
        output = PremortermOutput()
        with pytest.raises(ValidationError):
            output.failure_modes = ()  # type: ignore[misc]

    @pytest.mark.unit
    def test_empty_output(self) -> None:
        """Empty output is valid."""
        output = PremortermOutput()
        assert output.failure_modes == ()
        assert output.assumptions == ()
        assert output.risk_card is None

    @pytest.mark.unit
    def test_with_failure_modes(self) -> None:
        """Output can contain failure modes."""
        modes = (
            FailureMode(description="Failure 1"),
            FailureMode(description="Failure 2"),
        )
        output = PremortermOutput(failure_modes=modes)
        assert len(output.failure_modes) == 2

    @pytest.mark.unit
    def test_with_assumptions(self) -> None:
        """Output can contain assumptions."""
        assumptions = ("Users will adopt it", "Team has bandwidth")
        output = PremortermOutput(assumptions=assumptions)
        assert output.assumptions == assumptions

    @pytest.mark.unit
    def test_with_risk_card(self) -> None:
        """Output can include risk card."""
        risk_card = RiskCard(
            decision_type="infrastructure_change",
        )
        output = PremortermOutput(risk_card=risk_card)
        assert output.risk_card is not None
        assert output.risk_card.decision_type == "infrastructure_change"

    @pytest.mark.unit
    def test_full_output(self) -> None:
        """Output can have all fields populated."""
        modes = (FailureMode(description="Failure 1"),)
        assumptions = ("Assumption 1",)
        risk_card = RiskCard(decision_type="budget")
        output = PremortermOutput(
            failure_modes=modes,
            assumptions=assumptions,
            risk_card=risk_card,
        )
        assert len(output.failure_modes) == 1
        assert len(output.assumptions) == 1
        assert output.risk_card is not None


class TestPremortermExecutor:
    """Tests for PremortermExecutor protocol."""

    @pytest.mark.unit
    def test_is_runtime_checkable(self) -> None:
        """PremortermExecutor is a runtime_checkable protocol."""
        executor = DefaultPremortermExecutor()
        assert isinstance(executor, PremortermExecutor)


class TestDefaultPremortermExecutor:
    """Tests for DefaultPremortermExecutor."""

    @pytest.mark.unit
    async def test_none_participation_returns_empty(self) -> None:
        """NONE participation returns empty output."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.NONE)

        async def dummy_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            return AgentResponse(agent_id=agent_id, content="response")

        output = await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1",),
            agent_caller=dummy_caller,
            config=config,
            token_budget=1000,
        )

        assert output.failure_modes == ()
        assert output.assumptions == ()
        assert output.risk_card is None

    @pytest.mark.unit
    async def test_empty_participants_returns_empty(self) -> None:
        """Empty participants returns empty output."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        async def dummy_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            return AgentResponse(agent_id=agent_id, content="response")

        output = await executor.execute(
            synthesis_text="Test decision",
            participant_ids=(),
            agent_caller=dummy_caller,
            config=config,
            token_budget=1000,
        )

        assert output == PremortermOutput()

    @pytest.mark.unit
    async def test_all_participation_calls_all(self) -> None:
        """ALL participation invokes all participants."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        called_agents = []

        async def tracking_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            called_agents.append(agent_id)
            return AgentResponse(agent_id=agent_id, content="response")

        await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1", "agent_2", "agent_3"),
            agent_caller=tracking_caller,
            config=config,
            token_budget=1000,
        )

        assert len(called_agents) == 3
        assert set(called_agents) == {"agent_1", "agent_2", "agent_3"}

    @pytest.mark.unit
    async def test_strategic_participation_calls_subset(self) -> None:
        """STRATEGIC participation invokes approximately half."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.STRATEGIC)

        called_agents = []

        async def tracking_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            called_agents.append(agent_id)
            return AgentResponse(agent_id=agent_id, content="response")

        await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1", "agent_2", "agent_3", "agent_4"),
            agent_caller=tracking_caller,
            config=config,
            token_budget=1000,
        )

        # Should call approximately half: 4 // 2 = 2
        assert len(called_agents) == 2
        assert called_agents == ["agent_1", "agent_2"]

    @pytest.mark.unit
    async def test_token_distribution(self) -> None:
        """Tokens are distributed evenly across participants."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        token_allocations = []

        async def tracking_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            token_allocations.append(tokens)
            return AgentResponse(agent_id=agent_id, content="response")

        await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1", "agent_2", "agent_3"),
            agent_caller=tracking_caller,
            config=config,
            token_budget=1500,
        )

        # Each of 3 agents should get 1500 // 3 = 500 tokens
        assert all(t == 500 for t in token_allocations)

    @pytest.mark.unit
    async def test_prompt_contains_decision_summary(self) -> None:
        """Prompt includes the synthesis text."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        captured_prompts = []

        async def tracking_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            captured_prompts.append(prompt)
            return AgentResponse(agent_id=agent_id, content="response")

        synthesis = "We will launch product X"
        await executor.execute(
            synthesis_text=synthesis,
            participant_ids=("agent_1",),
            agent_caller=tracking_caller,
            config=config,
            token_budget=1000,
        )

        assert len(captured_prompts) == 1
        assert synthesis in captured_prompts[0]

    @pytest.mark.unit
    async def test_prompt_asks_for_failure_modes(self) -> None:
        """Prompt asks agents to imagine failure."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        captured_prompts = []

        async def tracking_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            captured_prompts.append(prompt)
            return AgentResponse(agent_id=agent_id, content="response")

        await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1",),
            agent_caller=tracking_caller,
            config=config,
            token_budget=1000,
        )

        prompt = captured_prompts[0]
        assert "fail" in prompt.lower() or "failed" in prompt.lower()
        assert "risk" in prompt.lower() or "assumption" in prompt.lower()

    @pytest.mark.unit
    async def test_parses_failure_responses(self) -> None:
        """Extracts failure modes from responses."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        async def failure_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            return AgentResponse(
                agent_id=agent_id,
                content="This could fail if the database goes down",
            )

        output = await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1",),
            agent_caller=failure_caller,
            config=config,
            token_budget=1000,
        )

        # Should extract at least one failure mode
        assert len(output.failure_modes) > 0

    @pytest.mark.unit
    async def test_parses_assumption_responses(self) -> None:
        """Extracts assumptions from responses."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        async def assumption_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            return AgentResponse(
                agent_id=agent_id,
                content="Key assumption: our users will adopt this immediately",
            )

        output = await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1",),
            agent_caller=assumption_caller,
            config=config,
            token_budget=1000,
        )

        # Should extract at least one assumption
        assert len(output.assumptions) > 0

    @pytest.mark.unit
    async def test_multiple_responses_aggregated(self) -> None:
        """Multiple agent responses are aggregated."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        response_count = 0

        async def counting_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            nonlocal response_count
            response_count += 1
            return AgentResponse(
                agent_id=agent_id,
                content=(
                    "Risk: system might fail under load. Assumption: team has skills."
                ),
            )

        output = await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1", "agent_2"),
            agent_caller=counting_caller,
            config=config,
            token_budget=2000,
        )

        assert response_count == 2
        # Both responses contribute to aggregation
        assert len(output.failure_modes) + len(output.assumptions) > 0

    @pytest.mark.unit
    async def test_returns_valid_premortem_output(self) -> None:
        """Result is always a valid PremortermOutput."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.ALL)

        async def dummy_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            return AgentResponse(agent_id=agent_id, content="response")

        output = await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1",),
            agent_caller=dummy_caller,
            config=config,
            token_budget=1000,
        )

        assert isinstance(output, PremortermOutput)
        assert isinstance(output.failure_modes, tuple)
        assert isinstance(output.assumptions, tuple)
        assert output.risk_card is None or isinstance(output.risk_card, RiskCard)

    @pytest.mark.unit
    async def test_strategic_odd_number_participants(self) -> None:
        """STRATEGIC with odd number rounds down."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.STRATEGIC)

        called_agents = []

        async def tracking_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            called_agents.append(agent_id)
            return AgentResponse(agent_id=agent_id, content="response")

        # 5 participants: 5 // 2 = 2
        await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("a1", "a2", "a3", "a4", "a5"),
            agent_caller=tracking_caller,
            config=config,
            token_budget=2000,
        )

        assert len(called_agents) == 2

    @pytest.mark.unit
    async def test_strategic_single_participant(self) -> None:
        """STRATEGIC with single participant calls that one."""
        executor = DefaultPremortermExecutor()
        config = PremortemConfig(participants=PremortemParticipation.STRATEGIC)

        called_agents = []

        async def tracking_caller(
            agent_id: str, prompt: str, tokens: int
        ) -> AgentResponse:
            called_agents.append(agent_id)
            return AgentResponse(agent_id=agent_id, content="response")

        # 1 participant: max(1, 1 // 2) = 1
        await executor.execute(
            synthesis_text="Test decision",
            participant_ids=("agent_1",),
            agent_caller=tracking_caller,
            config=config,
            token_budget=1000,
        )

        assert len(called_agents) == 1
        assert called_agents[0] == "agent_1"
