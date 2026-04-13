"""Tests for handoff artifact data model."""

import copy
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from synthorg.engine.quality.verification import AtomicProbe
from synthorg.engine.workflow.handoff import HandoffArtifact


def _ts() -> datetime:
    return datetime.now(UTC)


def _minimal_handoff(**overrides: object) -> HandoffArtifact:
    defaults: dict[str, object] = {
        "from_agent_id": "gen-agent",
        "to_agent_id": "eval-agent",
        "from_stage": "generator",
        "to_stage": "evaluator",
        "payload": {"output": "some artifact data"},
        "created_at": _ts(),
    }
    defaults.update(overrides)
    return HandoffArtifact.model_validate(defaults)


@pytest.mark.unit
class TestHandoffArtifact:
    def test_valid_handoff(self) -> None:
        h = _minimal_handoff()
        assert h.from_agent_id == "gen-agent"
        assert h.to_agent_id == "eval-agent"
        assert h.rubric is None
        assert h.acceptance_probes == ()
        assert h.artifact_refs == ()

    def test_frozen(self) -> None:
        h = _minimal_handoff()
        with pytest.raises(ValidationError, match="frozen"):
            h.from_stage = "changed"  # type: ignore[misc]

    def test_rejects_self_handoff(self) -> None:
        with pytest.raises(ValidationError, match="Self-handoff rejected"):
            _minimal_handoff(from_agent_id="same-agent", to_agent_id="same-agent")

    def test_rejects_blank_from_agent_id(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_handoff(from_agent_id="")

    def test_rejects_blank_to_agent_id(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_handoff(to_agent_id="")

    def test_with_probes(self) -> None:
        probes = (
            AtomicProbe(id="p1", probe_text="Is it done?", source_criterion="Done"),
        )
        h = _minimal_handoff(acceptance_probes=probes)
        assert len(h.acceptance_probes) == 1

    def test_with_artifact_refs(self) -> None:
        h = _minimal_handoff(artifact_refs=("art-1", "art-2"))
        assert len(h.artifact_refs) == 2

    def test_json_roundtrip(self) -> None:
        h = _minimal_handoff(
            payload={"key": "value"},
            artifact_refs=("ref-1",),
        )
        restored = HandoffArtifact.model_validate_json(h.model_dump_json())
        assert restored.from_agent_id == h.from_agent_id
        assert restored.to_agent_id == h.to_agent_id
        assert dict(restored.payload) == dict(h.payload)

    def test_deepcopy_preserves_equality_distinct_identity(self) -> None:
        h = _minimal_handoff(payload={"nested": {"data": [1, 2, 3]}})
        h_copy = copy.deepcopy(h)
        assert h == h_copy
        assert h.payload is not h_copy.payload

    @given(
        agent_name=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
    )
    def test_self_handoff_always_rejected_property(self, agent_name: str) -> None:
        with pytest.raises(ValidationError, match="Self-handoff"):
            _minimal_handoff(from_agent_id=agent_name, to_agent_id=agent_name)
