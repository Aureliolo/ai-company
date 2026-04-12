"""Tests for hierarchical retriever domain models."""

import pytest
from pydantic import ValidationError

from synthorg.memory.retrieval.hierarchical.models import (
    RetrievalRetryCorrection,
    WorkerRoutingDecision,
)
from synthorg.memory.retrieval.models import RetrievalQuery


class TestWorkerRoutingDecision:
    """Tests for WorkerRoutingDecision model."""

    @pytest.mark.unit
    def test_construction(self) -> None:
        d = WorkerRoutingDecision(
            selected_workers=("semantic", "episodic"),
            reason="Query mentions past events and knowledge",
        )
        assert d.selected_workers == ("semantic", "episodic")
        assert "past events" in d.reason

    @pytest.mark.unit
    def test_frozen(self) -> None:
        d = WorkerRoutingDecision(
            selected_workers=("semantic",),
            reason="Simple query",
        )
        with pytest.raises(ValidationError, match="frozen"):
            d.reason = "changed"  # type: ignore[misc]

    @pytest.mark.unit
    def test_blank_reason_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least 1 character"):
            WorkerRoutingDecision(
                selected_workers=("semantic",),
                reason="",
            )

    @pytest.mark.unit
    def test_empty_workers_allowed(self) -> None:
        """Empty workers is structurally valid (supervisor may skip)."""
        d = WorkerRoutingDecision(
            selected_workers=(),
            reason="No relevant workers for this query",
        )
        assert d.selected_workers == ()


class TestRetrievalRetryCorrection:
    """Tests for RetrievalRetryCorrection model."""

    @pytest.mark.unit
    def test_minimal_correction(self) -> None:
        c = RetrievalRetryCorrection(reason="Results were empty")
        assert c.corrected_query is None
        assert c.alternative_strategy is None
        assert c.reason == "Results were empty"

    @pytest.mark.unit
    def test_with_corrected_query(self) -> None:
        q = RetrievalQuery(text="broader search", agent_id="agent-1")
        c = RetrievalRetryCorrection(
            corrected_query=q,
            reason="Original query too narrow",
        )
        assert c.corrected_query is not None
        assert c.corrected_query.text == "broader search"

    @pytest.mark.unit
    def test_with_alternative_strategy(self) -> None:
        c = RetrievalRetryCorrection(
            alternative_strategy="semantic_only",
            reason="Episodic worker timed out",
        )
        assert c.alternative_strategy == "semantic_only"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "strategy",
        ["semantic_only", "episodic_only", "skip"],
    )
    def test_valid_alternative_strategies(self, strategy: str) -> None:
        c = RetrievalRetryCorrection(
            alternative_strategy=strategy,
            reason="Testing strategy",
        )
        assert c.alternative_strategy == strategy

    @pytest.mark.unit
    def test_invalid_alternative_strategy_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Input should be"):
            RetrievalRetryCorrection(
                alternative_strategy="invalid_strategy",  # type: ignore[arg-type]
                reason="Testing",
            )
