"""Unit tests for system prompt construction."""

from datetime import date
from typing import TYPE_CHECKING

import pytest
import structlog.testing
from pydantic import ValidationError

from ai_company.core.agent import AgentIdentity, ModelConfig, PersonalityConfig
from ai_company.core.enums import (
    CreativityLevel,
    RiskTolerance,
    SeniorityLevel,
)
from ai_company.engine.prompt import (
    DefaultTokenEstimator,
    SystemPrompt,
    build_system_prompt,
)
from ai_company.engine.prompt_template import (
    AUTONOMY_INSTRUCTIONS,
    PROMPT_TEMPLATE_VERSION,
)

if TYPE_CHECKING:
    from ai_company.core.company import Company
    from ai_company.core.role import Role
    from ai_company.core.task import Task
    from ai_company.providers.models import ToolDefinition


# ── TestBuildSystemPrompt ────────────────────────────────────────


class TestBuildSystemPrompt:
    """Tests for the build_system_prompt() public API."""

    @pytest.mark.unit
    def test_minimal_agent_produces_valid_prompt(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """Minimal call with only agent produces a prompt with identity."""
        result = build_system_prompt(agent=sample_agent_with_personality)

        assert isinstance(result, SystemPrompt)
        assert sample_agent_with_personality.name in result.content
        assert sample_agent_with_personality.role in result.content
        assert sample_agent_with_personality.department in result.content
        assert result.estimated_tokens > 0
        assert result.content.strip()

    @pytest.mark.unit
    def test_personality_traits_in_prompt(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """All personality dimensions appear in the rendered prompt."""
        result = build_system_prompt(agent=sample_agent_with_personality)
        p = sample_agent_with_personality.personality

        assert p.communication_style in result.content
        assert p.risk_tolerance.value in result.content
        assert p.creativity.value in result.content
        for trait in p.traits:
            assert trait in result.content

    @pytest.mark.unit
    def test_different_personalities_produce_different_prompts(
        self,
    ) -> None:
        """Two agents with different personality configs get different prompts."""
        model_cfg = ModelConfig(provider="test", model_id="test-001")
        hiring = date(2026, 1, 1)

        agent_a = AgentIdentity(
            name="Agent A",
            role="Developer",
            department="Engineering",
            model=model_cfg,
            hiring_date=hiring,
            personality=PersonalityConfig(
                communication_style="verbose and friendly",
                risk_tolerance=RiskTolerance.HIGH,
                creativity=CreativityLevel.HIGH,
            ),
        )
        agent_b = AgentIdentity(
            name="Agent B",
            role="Developer",
            department="Engineering",
            model=model_cfg,
            hiring_date=hiring,
            personality=PersonalityConfig(
                communication_style="terse and formal",
                risk_tolerance=RiskTolerance.LOW,
                creativity=CreativityLevel.LOW,
            ),
        )

        prompt_a = build_system_prompt(agent=agent_a)
        prompt_b = build_system_prompt(agent=agent_b)

        assert prompt_a.content != prompt_b.content
        assert "verbose and friendly" in prompt_a.content
        assert "terse and formal" in prompt_b.content

    @pytest.mark.unit
    def test_role_description_included(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_role_with_description: Role,
    ) -> None:
        """Role description appears in prompt when role is provided."""
        result = build_system_prompt(
            agent=sample_agent_with_personality,
            role=sample_role_with_description,
        )

        assert sample_role_with_description.description in result.content

    @pytest.mark.unit
    def test_custom_template_overrides_default(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """Custom template string is used instead of the default."""
        custom = "Hello, I am {{ agent_name }} working as {{ agent_role }}."
        result = build_system_prompt(
            agent=sample_agent_with_personality,
            custom_template=custom,
        )

        assert result.content == (
            f"Hello, I am {sample_agent_with_personality.name} "
            f"working as {sample_agent_with_personality.role}."
        )

    @pytest.mark.unit
    def test_authority_boundaries_in_prompt(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """Authority fields (can_approve, reports_to, etc.) appear in prompt."""
        result = build_system_prompt(agent=sample_agent_with_personality)
        auth = sample_agent_with_personality.authority

        for approval in auth.can_approve:
            assert approval in result.content
        assert auth.reports_to is not None
        assert auth.reports_to in result.content
        for delegate in auth.can_delegate_to:
            assert delegate in result.content
        assert "10.00" in result.content  # budget_limit

    @pytest.mark.unit
    def test_company_context_injected(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_company: Company,
    ) -> None:
        """Company name appears when company context is provided."""
        result = build_system_prompt(
            agent=sample_agent_with_personality,
            company=sample_company,
        )

        assert sample_company.name in result.content

    @pytest.mark.unit
    def test_tool_availability_in_prompt(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_tool_definitions: tuple[ToolDefinition, ...],
    ) -> None:
        """Tool names and descriptions appear in prompt."""
        result = build_system_prompt(
            agent=sample_agent_with_personality,
            available_tools=sample_tool_definitions,
        )

        for tool in sample_tool_definitions:
            assert tool.name in result.content
            assert tool.description in result.content

    @pytest.mark.unit
    def test_task_context_in_prompt(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
    ) -> None:
        """Task title, description, and acceptance criteria appear."""
        result = build_system_prompt(
            agent=sample_agent_with_personality,
            task=sample_task_with_criteria,
        )

        assert sample_task_with_criteria.title in result.content
        assert sample_task_with_criteria.description in result.content
        for criterion in sample_task_with_criteria.acceptance_criteria:
            assert criterion.description in result.content

    @pytest.mark.unit
    def test_task_budget_in_prompt(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
    ) -> None:
        """Task budget appears in prompt when > 0."""
        result = build_system_prompt(
            agent=sample_agent_with_personality,
            task=sample_task_with_criteria,
        )

        assert "5.00" in result.content

    @pytest.mark.unit
    def test_no_task_section_when_task_is_none(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """No 'Current Task' section when task is None."""
        result = build_system_prompt(agent=sample_agent_with_personality)

        assert "Current Task" not in result.content
        assert "task" not in result.sections

    @pytest.mark.unit
    def test_no_tools_section_when_no_tools(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """No 'Available Tools' section when no tools are provided."""
        result = build_system_prompt(agent=sample_agent_with_personality)

        assert "Available Tools" not in result.content
        assert "tools" not in result.sections

    @pytest.mark.unit
    def test_no_company_section_when_company_is_none(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """No 'Company Context' section when company is None."""
        result = build_system_prompt(agent=sample_agent_with_personality)

        assert "Company Context" not in result.content
        assert "company" not in result.sections


# ── TestSeniorityAutonomy ────────────────────────────────────────


class TestSeniorityAutonomy:
    """Tests for seniority-based autonomy instructions."""

    @pytest.mark.unit
    def test_junior_gets_guidance_instructions(self) -> None:
        """Junior agents get step-by-step guidance language."""
        model_cfg = ModelConfig(provider="test", model_id="test-001")
        agent = AgentIdentity(
            name="Junior Dev",
            role="Developer",
            department="Engineering",
            level=SeniorityLevel.JUNIOR,
            model=model_cfg,
            hiring_date=date(2026, 1, 1),
        )
        result = build_system_prompt(agent=agent)

        assert "Follow instructions carefully" in result.content
        assert "seek approval" in result.content.lower()

    @pytest.mark.unit
    def test_senior_gets_ownership_instructions(self) -> None:
        """Senior agents get ownership-focused language."""
        model_cfg = ModelConfig(provider="test", model_id="test-001")
        agent = AgentIdentity(
            name="Senior Dev",
            role="Developer",
            department="Engineering",
            level=SeniorityLevel.SENIOR,
            model=model_cfg,
            hiring_date=date(2026, 1, 1),
        )
        result = build_system_prompt(agent=agent)

        assert "Take ownership" in result.content

    @pytest.mark.unit
    def test_c_suite_gets_strategic_scope(self) -> None:
        """C-suite agents get strategic language."""
        model_cfg = ModelConfig(provider="test", model_id="test-001")
        agent = AgentIdentity(
            name="CEO",
            role="Chief Executive",
            department="Executive",
            level=SeniorityLevel.C_SUITE,
            model=model_cfg,
            hiring_date=date(2026, 1, 1),
        )
        result = build_system_prompt(agent=agent)

        assert "company-wide authority" in result.content.lower()
        assert "vision" in result.content.lower()

    @pytest.mark.unit
    def test_all_levels_produce_unique_instructions(self) -> None:
        """Each seniority level maps to distinct autonomy text."""
        instructions = set(AUTONOMY_INSTRUCTIONS.values())
        assert len(instructions) == len(SeniorityLevel)


# ── TestTokenEstimation ──────────────────────────────────────────


class TestTokenEstimation:
    """Tests for token estimation and budget trimming."""

    @pytest.mark.unit
    def test_default_estimator_positive(self) -> None:
        """Non-empty text produces positive token estimate."""
        estimator = DefaultTokenEstimator()
        assert estimator.estimate_tokens("Hello world, this is a test.") > 0

    @pytest.mark.unit
    def test_default_estimator_empty(self) -> None:
        """Empty text produces zero tokens."""
        estimator = DefaultTokenEstimator()
        assert estimator.estimate_tokens("") == 0

    @pytest.mark.unit
    def test_estimated_tokens_populated(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """SystemPrompt.estimated_tokens is set and positive."""
        result = build_system_prompt(agent=sample_agent_with_personality)
        assert result.estimated_tokens > 0

    @pytest.mark.unit
    def test_max_tokens_triggers_trimming(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
        sample_tool_definitions: tuple[ToolDefinition, ...],
        sample_company: Company,
    ) -> None:
        """Very low max_tokens causes optional sections to be removed."""
        # First build without limit to know the full size.
        full = build_system_prompt(
            agent=sample_agent_with_personality,
            task=sample_task_with_criteria,
            available_tools=sample_tool_definitions,
            company=sample_company,
        )
        assert "task" in full.sections
        assert "tools" in full.sections
        assert "company" in full.sections

        # Now build with a tight token budget to force trimming.
        trimmed = build_system_prompt(
            agent=sample_agent_with_personality,
            task=sample_task_with_criteria,
            available_tools=sample_tool_definitions,
            company=sample_company,
            max_tokens=10,
        )

        # At least some optional sections should have been removed.
        assert "company" not in trimmed.sections

    @pytest.mark.unit
    def test_custom_estimator_used(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """Custom token estimator is called during prompt construction."""
        call_count = 0

        class CountingEstimator:
            def estimate_tokens(self, text: str) -> int:
                nonlocal call_count
                call_count += 1
                return len(text) // 4

        result = build_system_prompt(
            agent=sample_agent_with_personality,
            token_estimator=CountingEstimator(),
        )

        assert call_count > 0
        assert result.estimated_tokens > 0


# ── TestPromptVersioning ─────────────────────────────────────────


class TestPromptVersioning:
    """Tests for prompt versioning and section tracking."""

    @pytest.mark.unit
    def test_template_version_in_result(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """SystemPrompt.template_version matches the constant."""
        result = build_system_prompt(agent=sample_agent_with_personality)
        assert result.template_version == PROMPT_TEMPLATE_VERSION

    @pytest.mark.unit
    def test_sections_tracked(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
        sample_tool_definitions: tuple[ToolDefinition, ...],
        sample_company: Company,
    ) -> None:
        """Sections tuple lists all included sections."""
        result = build_system_prompt(
            agent=sample_agent_with_personality,
            task=sample_task_with_criteria,
            available_tools=sample_tool_definitions,
            company=sample_company,
        )

        assert "identity" in result.sections
        assert "personality" in result.sections
        assert "skills" in result.sections
        assert "authority" in result.sections
        assert "autonomy" in result.sections
        assert "task" in result.sections
        assert "tools" in result.sections
        assert "company" in result.sections


# ── TestSystemPromptModel ────────────────────────────────────────


class TestSystemPromptModel:
    """Tests for the SystemPrompt Pydantic model."""

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """SystemPrompt instances are immutable."""
        prompt = SystemPrompt(
            content="test content",
            template_version="1.0.0",
            estimated_tokens=3,
            sections=("identity",),
            metadata={"agent_id": "abc"},
        )
        with pytest.raises(ValidationError):
            prompt.content = "modified"  # type: ignore[misc]

    @pytest.mark.unit
    def test_metadata_contains_agent_info(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """Metadata contains agent_id and role keys."""
        result = build_system_prompt(agent=sample_agent_with_personality)

        assert "agent_id" in result.metadata
        assert "role" in result.metadata
        assert result.metadata["agent_id"] == str(sample_agent_with_personality.id)
        assert result.metadata["role"] == sample_agent_with_personality.role


# ── TestPromptLogging ────────────────────────────────────────────


class TestPromptLogging:
    """Tests for structured logging during prompt construction."""

    @pytest.mark.unit
    def test_build_logs_start_and_success(
        self,
        sample_agent_with_personality: AgentIdentity,
    ) -> None:
        """Build logs prompt.build.start and prompt.build.success events."""
        with structlog.testing.capture_logs() as logs:
            build_system_prompt(agent=sample_agent_with_personality)

        events = [entry["event"] for entry in logs]
        assert "prompt.build.start" in events
        assert "prompt.build.success" in events

    @pytest.mark.unit
    def test_trim_logs_warning(
        self,
        sample_agent_with_personality: AgentIdentity,
        sample_task_with_criteria: Task,
        sample_company: Company,
    ) -> None:
        """Token trimming logs a warning with the trimmed section names."""
        with structlog.testing.capture_logs() as logs:
            build_system_prompt(
                agent=sample_agent_with_personality,
                task=sample_task_with_criteria,
                company=sample_company,
                max_tokens=10,
            )

        events = [entry["event"] for entry in logs]
        assert "prompt.build.token_trimmed" in events
