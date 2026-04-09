"""Shared fixtures for ontology unit tests."""

from datetime import UTC, datetime

import pytest

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

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_field() -> EntityField:
    """A minimal EntityField."""
    return EntityField(
        name="title",
        type_hint="str",
        description="Task title",
    )


@pytest.fixture
def sample_relation() -> EntityRelation:
    """A minimal EntityRelation."""
    return EntityRelation(
        target="AgentIdentity",
        relation="assigned_to",
        description="Agent assigned to this task",
    )


@pytest.fixture
def sample_entity(
    sample_field: EntityField,
    sample_relation: EntityRelation,
) -> EntityDefinition:
    """A fully populated EntityDefinition."""
    return EntityDefinition(
        name="Task",
        tier=EntityTier.CORE,
        source=EntitySource.AUTO,
        definition="A unit of work within the company.",
        fields=(
            sample_field,
            EntityField(name="status", type_hint="str", description="Task status"),
        ),
        constraints=("title must not be empty",),
        disambiguation="Not a calendar event or reminder.",
        relationships=(sample_relation,),
        created_by="system",
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.fixture
def sample_drift_report() -> DriftReport:
    """A sample DriftReport."""
    return DriftReport(
        entity_name="Task",
        divergence_score=0.35,
        divergent_agents=(
            AgentDrift(
                agent_id="agent-1",
                divergence_score=0.35,
                details="Uses 'assignment' instead of 'task'",
            ),
        ),
        canonical_version=3,
        recommendation=DriftAction.NOTIFY,
    )
