"""Tests for AgentCardBuilder safe-subset projection."""

from datetime import date
from uuid import uuid4

import pytest

from synthorg.a2a.agent_card import AgentCardBuilder, _identity_to_skills
from synthorg.a2a.models import A2AAuthSchemeInfo
from synthorg.core.agent import (
    AgentIdentity,
    ModelConfig,
    PersonalityConfig,
    SkillSet,
)


def _make_identity(
    *,
    name: str = "test-agent",
    role: str = "developer",
    department: str = "engineering",
    primary_skills: tuple[str, ...] = ("python", "testing"),
    secondary_skills: tuple[str, ...] = ("sql",),
) -> AgentIdentity:
    """Create a minimal AgentIdentity for testing."""
    return AgentIdentity(
        id=uuid4(),
        name=name,
        role=role,
        department=department,
        model=ModelConfig(
            provider="test-provider",
            model_id="test-medium-001",
        ),
        personality=PersonalityConfig(
            traits=("detail-oriented",),
            communication_style="formal",
        ),
        skills=SkillSet(
            primary=primary_skills,
            secondary=secondary_skills,
        ),
        hiring_date=date(2026, 1, 1),
    )


class TestIdentityToSkills:
    """Skill extraction from AgentIdentity."""

    @pytest.mark.unit
    def test_primary_and_secondary_mapped(self) -> None:
        """Both primary and secondary skills are extracted."""
        identity = _make_identity()
        skills = _identity_to_skills(identity)
        assert len(skills) == 3
        names = {s.name for s in skills}
        assert names == {"python", "testing", "sql"}

    @pytest.mark.unit
    def test_primary_tagged(self) -> None:
        """Primary skills have the 'primary' tag."""
        identity = _make_identity()
        skills = _identity_to_skills(identity)
        primary = [s for s in skills if "primary" in s.tags]
        assert len(primary) == 2

    @pytest.mark.unit
    def test_secondary_tagged(self) -> None:
        """Secondary skills have the 'secondary' tag."""
        identity = _make_identity()
        skills = _identity_to_skills(identity)
        secondary = [s for s in skills if "secondary" in s.tags]
        assert len(secondary) == 1

    @pytest.mark.unit
    def test_empty_skills(self) -> None:
        """Agent with no skills produces empty tuple."""
        identity = _make_identity(
            primary_skills=(),
            secondary_skills=(),
        )
        skills = _identity_to_skills(identity)
        assert skills == ()


class TestAgentCardBuilder:
    """AgentCardBuilder safe-subset projection."""

    @pytest.mark.unit
    def test_build_includes_safe_fields(self) -> None:
        """Card includes name, role, department, skills."""
        builder = AgentCardBuilder()
        identity = _make_identity()
        card = builder.build(identity, "https://example.com/a2a")

        assert card.name == "test-agent"
        assert "developer" in card.description
        assert "engineering" in card.description
        assert card.url == "https://example.com/a2a"
        assert len(card.skills) == 3

    @pytest.mark.unit
    def test_build_excludes_sensitive_fields(self) -> None:
        """Card does NOT contain personality, model, memory, etc."""
        builder = AgentCardBuilder()
        identity = _make_identity()
        card = builder.build(identity, "https://example.com/a2a")
        card_data = card.model_dump()
        card_json = str(card_data)

        # These should NOT appear anywhere in the serialized card
        assert "detail-oriented" not in card_json
        assert "formal" not in card_json
        assert "test-provider" not in card_json
        assert "test-medium-001" not in card_json

    @pytest.mark.unit
    def test_build_with_auth_schemes(self) -> None:
        """Builder passes through configured auth schemes."""
        auth = (A2AAuthSchemeInfo(scheme="api_key"),)
        builder = AgentCardBuilder(default_auth_schemes=auth)
        identity = _make_identity()
        card = builder.build(identity, "https://example.com/a2a")

        assert len(card.auth_schemes) == 1
        assert card.auth_schemes[0].scheme == "api_key"

    @pytest.mark.unit
    def test_build_company_card(self) -> None:
        """Company card aggregates skills from all agents."""
        builder = AgentCardBuilder()
        agents = [
            _make_identity(
                name="agent-a",
                primary_skills=("python",),
                secondary_skills=(),
            ),
            _make_identity(
                name="agent-b",
                primary_skills=("go",),
                secondary_skills=("docker",),
            ),
        ]
        card = builder.build_company_card(
            agents,
            "https://example.com/a2a",
            "Test Corp",
        )

        assert card.name == "Test Corp"
        assert "2 agents" in card.description
        assert card.provider is not None
        assert card.provider.organization == "Test Corp"
        # 1 from agent-a + 2 from agent-b = 3 total
        assert len(card.skills) == 3

    @pytest.mark.unit
    def test_company_card_deduplicates_skills(self) -> None:
        """Company card deduplicates skills by ID."""
        builder = AgentCardBuilder()
        # Same agent listed twice
        agent = _make_identity(
            primary_skills=("python",),
            secondary_skills=(),
        )
        card = builder.build_company_card(
            [agent, agent],
            "https://example.com/a2a",
            "Test Corp",
        )
        # Same agent id -> same skill ids -> deduplicated
        assert len(card.skills) == 1

    @pytest.mark.unit
    def test_company_card_empty_agents(self) -> None:
        """Company card with no agents has no skills."""
        builder = AgentCardBuilder()
        card = builder.build_company_card(
            [],
            "https://example.com/a2a",
            "Empty Corp",
        )
        assert card.skills == ()
        assert "0 agents" in card.description
