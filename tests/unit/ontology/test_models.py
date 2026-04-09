"""Tests for ontology domain models."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from synthorg.ontology.models import (
    AgentDrift,
    DriftAction,
    DriftReport,
    EntityDefinition,
    EntityField,
    EntityRelation,
    EntitySource,
    EntityTier,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


# ── EntityTier ──────────────────────────────────────────────────


class TestEntityTier:
    def test_values(self) -> None:
        assert EntityTier.CORE.value == "core"
        assert EntityTier.USER.value == "user"

    def test_all_members(self) -> None:
        assert set(EntityTier) == {EntityTier.CORE, EntityTier.USER}


# ── EntitySource ────────────────────────────────────────────────


class TestEntitySource:
    def test_values(self) -> None:
        assert EntitySource.AUTO.value == "auto"
        assert EntitySource.CONFIG.value == "config"
        assert EntitySource.API.value == "api"

    def test_all_members(self) -> None:
        assert set(EntitySource) == {
            EntitySource.AUTO,
            EntitySource.CONFIG,
            EntitySource.API,
        }


# ── EntityField ─────────────────────────────────────────────────


class TestEntityField:
    def test_valid_construction(self) -> None:
        f = EntityField(name="title", type_hint="str", description="The title")
        assert f.name == "title"
        assert f.type_hint == "str"
        assert f.description == "The title"

    def test_frozen(self) -> None:
        f = EntityField(name="title", type_hint="str")
        with pytest.raises(ValidationError):
            f.name = "other"  # type: ignore[misc]

    def test_blank_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            EntityField(name="", type_hint="str")

    def test_whitespace_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            EntityField(name="   ", type_hint="str")

    def test_blank_type_hint_rejected(self) -> None:
        with pytest.raises(ValidationError, match="type_hint"):
            EntityField(name="title", type_hint="")

    def test_description_defaults_empty(self) -> None:
        f = EntityField(name="x", type_hint="int")
        assert f.description == ""


# ── EntityRelation ──────────────────────────────────────────────


class TestEntityRelation:
    def test_valid_construction(self) -> None:
        r = EntityRelation(
            target="Agent",
            relation="assigned_to",
            description="The assignee",
        )
        assert r.target == "Agent"
        assert r.relation == "assigned_to"
        assert r.description == "The assignee"

    def test_frozen(self) -> None:
        r = EntityRelation(target="Agent", relation="owns")
        with pytest.raises(ValidationError):
            r.target = "other"  # type: ignore[misc]

    def test_blank_target_rejected(self) -> None:
        with pytest.raises(ValidationError, match="target"):
            EntityRelation(target="", relation="owns")

    def test_blank_relation_rejected(self) -> None:
        with pytest.raises(ValidationError, match="relation"):
            EntityRelation(target="Agent", relation="")

    def test_description_defaults_empty(self) -> None:
        r = EntityRelation(target="Agent", relation="owns")
        assert r.description == ""


# ── EntityDefinition ────────────────────────────────────────────


class TestEntityDefinition:
    def test_valid_construction(
        self,
        sample_entity: EntityDefinition,
    ) -> None:
        assert sample_entity.name == "Task"
        assert sample_entity.tier == EntityTier.CORE
        assert sample_entity.source == EntitySource.AUTO
        assert len(sample_entity.fields) == 2
        assert len(sample_entity.relationships) == 1

    def test_frozen(self, sample_entity: EntityDefinition) -> None:
        with pytest.raises(ValidationError):
            sample_entity.name = "other"  # type: ignore[misc]

    def test_blank_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            EntityDefinition(
                name="",
                tier=EntityTier.CORE,
                source=EntitySource.AUTO,
                created_by="system",
                created_at=_NOW,
                updated_at=_NOW,
            )

    def test_blank_created_by_rejected(self) -> None:
        with pytest.raises(ValidationError, match="created_by"):
            EntityDefinition(
                name="Task",
                tier=EntityTier.CORE,
                source=EntitySource.AUTO,
                created_by="",
                created_at=_NOW,
                updated_at=_NOW,
            )

    def test_non_utc_created_at_rejected(self) -> None:
        eastern = timezone(timedelta(hours=-5))
        with pytest.raises(ValidationError, match="must be UTC"):
            EntityDefinition(
                name="Task",
                tier=EntityTier.CORE,
                source=EntitySource.AUTO,
                created_by="system",
                created_at=datetime(2026, 1, 1, tzinfo=eastern),
                updated_at=_NOW,
            )

    def test_non_utc_updated_at_rejected(self) -> None:
        eastern = timezone(timedelta(hours=-5))
        with pytest.raises(ValidationError, match="must be UTC"):
            EntityDefinition(
                name="Task",
                tier=EntityTier.CORE,
                source=EntitySource.AUTO,
                created_by="system",
                created_at=_NOW,
                updated_at=datetime(2026, 1, 1, tzinfo=eastern),
            )

    def test_duplicate_field_names_rejected(self) -> None:
        dup_fields = (
            EntityField(name="title", type_hint="str"),
            EntityField(name="title", type_hint="int"),
        )
        with pytest.raises(ValidationError, match="Duplicate"):
            EntityDefinition(
                name="Task",
                tier=EntityTier.CORE,
                source=EntitySource.AUTO,
                fields=dup_fields,
                created_by="system",
                created_at=_NOW,
                updated_at=_NOW,
            )

    def test_duplicate_relationships_rejected(self) -> None:
        dup_rels = (
            EntityRelation(target="Agent", relation="owns"),
            EntityRelation(target="Agent", relation="owns"),
        )
        with pytest.raises(ValidationError, match="Duplicate relationship"):
            EntityDefinition(
                name="Task",
                tier=EntityTier.CORE,
                source=EntitySource.AUTO,
                relationships=dup_rels,
                created_by="system",
                created_at=_NOW,
                updated_at=_NOW,
            )

    def test_defaults(self) -> None:
        e = EntityDefinition(
            name="Minimal",
            tier=EntityTier.USER,
            source=EntitySource.CONFIG,
            created_by="user",
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert e.definition == ""
        assert e.fields == ()
        assert e.constraints == ()
        assert e.disambiguation == ""
        assert e.relationships == ()

    def test_model_dump_roundtrip(
        self,
        sample_entity: EntityDefinition,
    ) -> None:
        dumped = sample_entity.model_dump(mode="json")
        restored = EntityDefinition.model_validate(dumped)
        assert restored == sample_entity


# ── DriftAction ─────────────────────────────────────────────────


class TestDriftAction:
    def test_values(self) -> None:
        assert DriftAction.NO_ACTION.value == "no_action"
        assert DriftAction.NOTIFY.value == "notify"
        assert DriftAction.RETRAIN.value == "retrain"
        assert DriftAction.ESCALATE.value == "escalate"

    def test_all_members(self) -> None:
        assert len(DriftAction) == 4


# ── AgentDrift ──────────────────────────────────────────────────


class TestAgentDrift:
    def test_valid_construction(self) -> None:
        d = AgentDrift(agent_id="a1", divergence_score=0.5, details="drifted")
        assert d.agent_id == "a1"
        assert d.divergence_score == 0.5

    def test_frozen(self) -> None:
        d = AgentDrift(agent_id="a1", divergence_score=0.0)
        with pytest.raises(ValidationError):
            d.agent_id = "other"  # type: ignore[misc]

    def test_blank_agent_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="agent_id"):
            AgentDrift(agent_id="", divergence_score=0.5)

    def test_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentDrift(agent_id="a1", divergence_score=-0.1)

    def test_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentDrift(agent_id="a1", divergence_score=1.1)

    def test_score_boundaries(self) -> None:
        assert AgentDrift(agent_id="a", divergence_score=0.0).divergence_score == 0.0
        assert AgentDrift(agent_id="a", divergence_score=1.0).divergence_score == 1.0

    def test_details_defaults_empty(self) -> None:
        d = AgentDrift(agent_id="a1", divergence_score=0.5)
        assert d.details == ""


# ── DriftReport ─────────────────────────────────────────────────


class TestDriftReport:
    def test_valid_construction(
        self,
        sample_drift_report: DriftReport,
    ) -> None:
        assert sample_drift_report.entity_name == "Task"
        assert sample_drift_report.divergence_score == 0.35
        assert len(sample_drift_report.divergent_agents) == 1
        assert sample_drift_report.canonical_version == 3
        assert sample_drift_report.recommendation == DriftAction.NOTIFY

    def test_frozen(self, sample_drift_report: DriftReport) -> None:
        with pytest.raises(ValidationError):
            sample_drift_report.entity_name = "other"  # type: ignore[misc]

    def test_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DriftReport(
                entity_name="Task",
                divergence_score=-0.1,
                canonical_version=1,
                recommendation=DriftAction.NO_ACTION,
            )

    def test_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DriftReport(
                entity_name="Task",
                divergence_score=1.1,
                canonical_version=1,
                recommendation=DriftAction.NO_ACTION,
            )

    def test_canonical_version_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            DriftReport(
                entity_name="Task",
                divergence_score=0.5,
                canonical_version=0,
                recommendation=DriftAction.NO_ACTION,
            )

    def test_blank_entity_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="entity_name"):
            DriftReport(
                entity_name="",
                divergence_score=0.5,
                canonical_version=1,
                recommendation=DriftAction.NO_ACTION,
            )

    def test_nan_divergence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DriftReport(
                entity_name="Task",
                divergence_score=float("nan"),
                canonical_version=1,
                recommendation=DriftAction.NO_ACTION,
            )

    def test_inf_divergence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DriftReport(
                entity_name="Task",
                divergence_score=float("inf"),
                canonical_version=1,
                recommendation=DriftAction.NO_ACTION,
            )
