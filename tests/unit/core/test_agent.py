"""Tests for agent identity and configuration models."""

from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError

from ai_company.core.agent import (
    AgentIdentity,
    MemoryConfig,
    ModelConfig,
    PersonalityConfig,
    SkillSet,
    ToolPermissions,
)
from ai_company.core.enums import (
    AgentStatus,
    CreativityLevel,
    MemoryType,
    RiskTolerance,
    SeniorityLevel,
)
from ai_company.core.role import Authority

from .conftest import (
    AgentIdentityFactory,
    MemoryConfigFactory,
    ModelConfigFactory,
    PersonalityConfigFactory,
    SkillSetFactory,
    ToolPermissionsFactory,
)

# ── PersonalityConfig ──────────────────────────────────────────────


@pytest.mark.unit
class TestPersonalityConfig:
    def test_defaults(self):
        p = PersonalityConfig()
        assert p.traits == ()
        assert p.communication_style == "neutral"
        assert p.risk_tolerance is RiskTolerance.MEDIUM
        assert p.creativity is CreativityLevel.MEDIUM
        assert p.description == ""

    def test_custom_values(self):
        p = PersonalityConfig(
            traits=("analytical", "pragmatic"),
            communication_style="concise and technical",
            risk_tolerance=RiskTolerance.LOW,
            creativity=CreativityLevel.HIGH,
            description="A detail-oriented engineer.",
        )
        assert len(p.traits) == 2
        assert p.communication_style == "concise and technical"

    def test_empty_communication_style_rejected(self):
        with pytest.raises(ValidationError):
            PersonalityConfig(communication_style="")

    def test_frozen(self):
        p = PersonalityConfig()
        with pytest.raises(ValidationError):
            p.creativity = CreativityLevel.LOW  # type: ignore[misc]

    def test_factory(self):
        p = PersonalityConfigFactory.build()
        assert isinstance(p, PersonalityConfig)


# ── SkillSet ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestSkillSet:
    def test_defaults(self):
        s = SkillSet()
        assert s.primary == ()
        assert s.secondary == ()

    def test_custom_values(self):
        s = SkillSet(
            primary=("python", "fastapi"),
            secondary=("docker", "redis"),
        )
        assert "python" in s.primary
        assert "docker" in s.secondary

    def test_frozen(self):
        s = SkillSet()
        with pytest.raises(ValidationError):
            s.primary = ("new",)  # type: ignore[misc]

    def test_factory(self):
        s = SkillSetFactory.build()
        assert isinstance(s, SkillSet)


# ── ModelConfig ────────────────────────────────────────────────────


@pytest.mark.unit
class TestModelConfig:
    def test_valid_config(self, sample_model_config: ModelConfig):
        assert sample_model_config.provider == "anthropic"
        assert sample_model_config.model_id == "claude-sonnet-4-6"
        assert sample_model_config.temperature == 0.3
        assert sample_model_config.max_tokens == 8192

    def test_defaults(self):
        m = ModelConfig(provider="test", model_id="test-model")
        assert m.temperature == 0.7
        assert m.max_tokens == 4096
        assert m.fallback_model is None

    def test_empty_provider_rejected(self):
        with pytest.raises(ValidationError):
            ModelConfig(provider="", model_id="test")

    def test_empty_model_id_rejected(self):
        with pytest.raises(ValidationError):
            ModelConfig(provider="test", model_id="")

    def test_temperature_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            ModelConfig(provider="test", model_id="m", temperature=-0.1)

    def test_temperature_above_two_rejected(self):
        with pytest.raises(ValidationError):
            ModelConfig(provider="test", model_id="m", temperature=2.1)

    def test_temperature_boundary_zero(self):
        m = ModelConfig(provider="test", model_id="m", temperature=0.0)
        assert m.temperature == 0.0

    def test_temperature_boundary_two(self):
        m = ModelConfig(provider="test", model_id="m", temperature=2.0)
        assert m.temperature == 2.0

    def test_max_tokens_zero_rejected(self):
        with pytest.raises(ValidationError):
            ModelConfig(provider="test", model_id="m", max_tokens=0)

    def test_max_tokens_negative_rejected(self):
        with pytest.raises(ValidationError):
            ModelConfig(provider="test", model_id="m", max_tokens=-1)

    def test_frozen(self, sample_model_config: ModelConfig):
        with pytest.raises(ValidationError):
            sample_model_config.temperature = 1.0  # type: ignore[misc]

    def test_factory(self):
        m = ModelConfigFactory.build()
        assert isinstance(m, ModelConfig)
        assert 0.0 <= m.temperature <= 2.0


# ── MemoryConfig ───────────────────────────────────────────────────


@pytest.mark.unit
class TestMemoryConfig:
    def test_defaults(self):
        m = MemoryConfig()
        assert m.type is MemoryType.SESSION
        assert m.retention_days is None

    def test_custom_values(self):
        m = MemoryConfig(type=MemoryType.PERSISTENT, retention_days=30)
        assert m.type is MemoryType.PERSISTENT
        assert m.retention_days == 30

    def test_retention_days_zero_rejected(self):
        with pytest.raises(ValidationError):
            MemoryConfig(retention_days=0)

    def test_retention_days_negative_rejected(self):
        with pytest.raises(ValidationError):
            MemoryConfig(retention_days=-1)

    def test_frozen(self):
        m = MemoryConfig()
        with pytest.raises(ValidationError):
            m.type = MemoryType.PERSISTENT  # type: ignore[misc]

    def test_factory(self):
        m = MemoryConfigFactory.build()
        assert isinstance(m, MemoryConfig)


# ── ToolPermissions ────────────────────────────────────────────────


@pytest.mark.unit
class TestToolPermissions:
    def test_defaults(self):
        t = ToolPermissions()
        assert t.allowed == ()
        assert t.denied == ()

    def test_custom_values(self):
        t = ToolPermissions(
            allowed=("file_system", "git"),
            denied=("deployment",),
        )
        assert "file_system" in t.allowed
        assert "deployment" in t.denied

    def test_frozen(self):
        t = ToolPermissions()
        with pytest.raises(ValidationError):
            t.allowed = ("new",)  # type: ignore[misc]

    def test_factory(self):
        t = ToolPermissionsFactory.build()
        assert isinstance(t, ToolPermissions)


# ── AgentIdentity ──────────────────────────────────────────────────


@pytest.mark.unit
class TestAgentIdentity:
    def test_valid_agent(self, sample_agent: AgentIdentity):
        assert sample_agent.name == "Sarah Chen"
        assert sample_agent.role == "Senior Backend Developer"
        assert sample_agent.department == "Engineering"
        assert sample_agent.level is SeniorityLevel.SENIOR
        assert isinstance(sample_agent.id, UUID)

    def test_auto_generated_id(self, sample_model_config: ModelConfig):
        agent = AgentIdentity(
            name="Test Agent",
            role="Developer",
            department="Engineering",
            model=sample_model_config,
            hiring_date=date(2026, 1, 1),
        )
        assert isinstance(agent.id, UUID)

    def test_defaults(self, sample_model_config: ModelConfig):
        agent = AgentIdentity(
            name="Test",
            role="Dev",
            department="Eng",
            model=sample_model_config,
            hiring_date=date(2026, 1, 1),
        )
        assert agent.level is SeniorityLevel.MID
        assert agent.status is AgentStatus.ACTIVE
        assert isinstance(agent.personality, PersonalityConfig)
        assert isinstance(agent.skills, SkillSet)
        assert isinstance(agent.memory, MemoryConfig)
        assert isinstance(agent.tools, ToolPermissions)
        assert isinstance(agent.authority, Authority)

    def test_model_is_required(self):
        with pytest.raises(ValidationError):
            AgentIdentity(
                name="Test",
                role="Dev",
                department="Eng",
                hiring_date=date(2026, 1, 1),
            )  # type: ignore[call-arg]

    def test_hiring_date_is_required(self, sample_model_config: ModelConfig):
        with pytest.raises(ValidationError):
            AgentIdentity(
                name="Test",
                role="Dev",
                department="Eng",
                model=sample_model_config,
            )  # type: ignore[call-arg]

    def test_empty_name_rejected(self, sample_model_config: ModelConfig):
        with pytest.raises(ValidationError):
            AgentIdentity(
                name="",
                role="Dev",
                department="Eng",
                model=sample_model_config,
                hiring_date=date(2026, 1, 1),
            )

    def test_frozen(self, sample_agent: AgentIdentity):
        with pytest.raises(ValidationError):
            sample_agent.name = "Changed"  # type: ignore[misc]

    def test_model_copy_update(self, sample_agent: AgentIdentity):
        updated = sample_agent.model_copy(
            update={"status": AgentStatus.TERMINATED},
        )
        assert updated.status is AgentStatus.TERMINATED
        assert sample_agent.status is AgentStatus.ACTIVE

    def test_json_roundtrip(self, sample_agent: AgentIdentity):
        json_str = sample_agent.model_dump_json()
        restored = AgentIdentity.model_validate_json(json_str)
        assert restored.name == sample_agent.name
        assert restored.id == sample_agent.id
        assert restored.model.provider == sample_agent.model.provider

    def test_factory(self):
        agent = AgentIdentityFactory.build()
        assert isinstance(agent, AgentIdentity)
        assert isinstance(agent.id, UUID)
        assert isinstance(agent.model, ModelConfig)
