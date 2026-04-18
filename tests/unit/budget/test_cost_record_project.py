"""Unit tests for CostRecord project_id field."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.budget.cost_record import CostRecord

from .conftest import make_cost_record


@pytest.mark.unit
class TestCostRecordProjectId:
    """Tests for the optional project_id field on CostRecord."""

    def test_default_project_id_is_none(self) -> None:
        rec = make_cost_record()
        assert rec.project_id is None

    def test_explicit_project_id(self) -> None:
        rec = CostRecord(
            agent_id="agent-1",
            task_id="task-1",
            project_id="proj-100",
            provider="test-provider",
            model="test-model-001",
            input_tokens=100,
            output_tokens=50,
            cost=0.01,
            currency="EUR",
            timestamp=datetime(2026, 3, 1, tzinfo=UTC),
        )
        assert rec.project_id == "proj-100"

    def test_project_id_rejects_blank(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            CostRecord(
                agent_id="agent-1",
                task_id="task-1",
                project_id="   ",
                provider="test-provider",
                model="test-model-001",
                input_tokens=100,
                output_tokens=50,
                cost=0.01,
                currency="EUR",
                timestamp=datetime(2026, 3, 1, tzinfo=UTC),
            )

    def test_project_id_frozen(self) -> None:
        rec = make_cost_record()
        with pytest.raises(ValidationError):
            rec.project_id = "proj-999"  # type: ignore[misc]
