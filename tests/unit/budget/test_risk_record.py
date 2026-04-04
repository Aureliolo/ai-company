"""Tests for the RiskRecord model."""

from datetime import UTC, datetime

import pytest

from synthorg.budget.risk_record import RiskRecord
from synthorg.security.risk_scorer import RiskScore


def _make_risk_score(
    *,
    reversibility: float = 0.5,
    blast_radius: float = 0.3,
    data_sensitivity: float = 0.2,
    external_visibility: float = 0.1,
) -> RiskScore:
    return RiskScore(
        reversibility=reversibility,
        blast_radius=blast_radius,
        data_sensitivity=data_sensitivity,
        external_visibility=external_visibility,
    )


@pytest.mark.unit
class TestRiskRecord:
    """Tests for the RiskRecord frozen model."""

    def test_construction_valid(self) -> None:
        score = _make_risk_score()
        record = RiskRecord(
            agent_id="agent-1",
            task_id="task-1",
            action_type="code:write",
            risk_score=score,
            risk_units=score.risk_units,
            timestamp=datetime.now(UTC),
        )
        assert record.agent_id == "agent-1"
        assert record.task_id == "task-1"
        assert record.action_type == "code:write"
        assert record.risk_score is score
        assert record.risk_units == score.risk_units

    def test_frozen(self) -> None:
        score = _make_risk_score()
        record = RiskRecord(
            agent_id="agent-1",
            task_id="task-1",
            action_type="code:write",
            risk_score=score,
            risk_units=score.risk_units,
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(Exception):  # noqa: B017, PT011
            record.agent_id = "agent-2"  # type: ignore[misc]

    def test_action_type_must_contain_colon(self) -> None:
        score = _make_risk_score()
        with pytest.raises(ValueError, match=r"[Cc]olon|category:action"):
            RiskRecord(
                agent_id="agent-1",
                task_id="task-1",
                action_type="invalid",
                risk_score=score,
                risk_units=0.5,
                timestamp=datetime.now(UTC),
            )

    def test_blank_agent_id_rejected(self) -> None:
        score = _make_risk_score()
        with pytest.raises(ValueError, match=r"whitespace"):
            RiskRecord(
                agent_id="   ",
                task_id="task-1",
                action_type="code:write",
                risk_score=score,
                risk_units=0.5,
                timestamp=datetime.now(UTC),
            )

    def test_blank_task_id_rejected(self) -> None:
        score = _make_risk_score()
        with pytest.raises(
            ValueError, match=r"String should have at least 1 character"
        ):
            RiskRecord(
                agent_id="agent-1",
                task_id="",
                action_type="code:write",
                risk_score=score,
                risk_units=0.5,
                timestamp=datetime.now(UTC),
            )

    def test_negative_risk_units_rejected(self) -> None:
        score = _make_risk_score()
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            RiskRecord(
                agent_id="agent-1",
                task_id="task-1",
                action_type="code:write",
                risk_score=score,
                risk_units=-0.1,
                timestamp=datetime.now(UTC),
            )

    def test_timestamp_must_be_aware(self) -> None:
        score = _make_risk_score()
        with pytest.raises(ValueError, match=r"timezone"):
            RiskRecord(
                agent_id="agent-1",
                task_id="task-1",
                action_type="code:write",
                risk_score=score,
                risk_units=0.5,
                timestamp=datetime(2026, 1, 1),  # naive  # noqa: DTZ001
            )

    def test_rejects_nan(self) -> None:
        score = _make_risk_score()
        with pytest.raises(ValueError, match=r"finite"):
            RiskRecord(
                agent_id="agent-1",
                task_id="task-1",
                action_type="code:write",
                risk_score=score,
                risk_units=float("nan"),
                timestamp=datetime.now(UTC),
            )
