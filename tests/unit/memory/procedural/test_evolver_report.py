"""Tests for EvolverReport model."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.memory.procedural.evolver_report import EvolverReport


def _make_report(**overrides: object) -> EvolverReport:
    defaults: dict[str, object] = {
        "cycle_id": "cycle-1",
        "window_start": datetime(2026, 4, 13, tzinfo=UTC),
        "window_end": datetime(2026, 4, 14, tzinfo=UTC),
        "trajectories_analyzed": 100,
        "patterns_found": 5,
    }
    defaults.update(overrides)
    return EvolverReport(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestEvolverReport:
    def test_minimal(self) -> None:
        r = _make_report()
        assert r.cycle_id == "cycle-1"
        assert r.trajectories_analyzed == 100
        assert r.patterns_found == 5
        assert r.proposals_emitted == ()
        assert r.conflicts == ()
        assert r.supersessions == ()
        assert r.skipped_low_confidence == 0

    def test_frozen(self) -> None:
        r = _make_report()
        with pytest.raises(ValidationError):
            r.cycle_id = "other"  # type: ignore[misc]

    def test_negative_trajectories_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_report(trajectories_analyzed=-1)

    def test_negative_patterns_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_report(patterns_found=-1)

    def test_skipped_fields_default_zero(self) -> None:
        r = _make_report()
        assert r.skipped_low_confidence == 0
        assert r.skipped_below_agent_threshold == 0
