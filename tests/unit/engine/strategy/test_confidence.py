"""Unit tests for confidence formatters."""

import pytest

from synthorg.engine.strategy.confidence import (
    BothFormatter,
    NarrativeFormatter,
    ProbabilityFormatter,
    StructuredFormatter,
    get_formatter,
)
from synthorg.engine.strategy.models import (
    ConfidenceConfig,
    ConfidenceFormat,
    ConfidenceMetadata,
)


class TestStructuredFormatter:
    """Tests for StructuredFormatter."""

    @pytest.mark.unit
    def test_output_contains_confidence(
        self,
        confidence_metadata: ConfidenceMetadata,
    ) -> None:
        fmt = StructuredFormatter()
        result = fmt.format(metadata=confidence_metadata)
        assert "75%" in result
        assert "60%" in result
        assert "90%" in result

    @pytest.mark.unit
    def test_output_contains_assumptions(
        self,
        confidence_metadata: ConfidenceMetadata,
    ) -> None:
        fmt = StructuredFormatter()
        result = fmt.format(metadata=confidence_metadata)
        assert "Market conditions" in result

    @pytest.mark.unit
    def test_output_contains_uncertainty(
        self,
        confidence_metadata: ConfidenceMetadata,
    ) -> None:
        fmt = StructuredFormatter()
        result = fmt.format(metadata=confidence_metadata)
        assert "Competitor response" in result


class TestNarrativeFormatter:
    """Tests for NarrativeFormatter."""

    @pytest.mark.unit
    def test_output_is_prose(
        self,
        confidence_metadata: ConfidenceMetadata,
    ) -> None:
        fmt = NarrativeFormatter()
        result = fmt.format(metadata=confidence_metadata)
        assert "confident" in result.lower()
        assert "75%" in result


class TestBothFormatter:
    """Tests for BothFormatter."""

    @pytest.mark.unit
    def test_contains_both_formats(
        self,
        confidence_metadata: ConfidenceMetadata,
    ) -> None:
        fmt = BothFormatter()
        result = fmt.format(metadata=confidence_metadata)
        assert "**Confidence**" in result
        assert "confident" in result.lower()


class TestProbabilityFormatter:
    """Tests for ProbabilityFormatter."""

    @pytest.mark.unit
    def test_output_contains_probability(
        self,
        confidence_metadata: ConfidenceMetadata,
    ) -> None:
        fmt = ProbabilityFormatter()
        result = fmt.format(metadata=confidence_metadata)
        assert "Probability" in result
        assert "75%" in result


class TestFormattersWithEmptyMetadata:
    """Tests for formatters with empty assumptions/uncertainty."""

    @pytest.mark.unit
    def test_structured_with_empty_fields(self) -> None:
        meta = ConfidenceMetadata(level=0.5, range_lower=0.3, range_upper=0.7)
        fmt = StructuredFormatter()
        result = fmt.format(metadata=meta)
        assert "50%" in result
        assert "assumptions" not in result.lower()
        assert "uncertainty" not in result.lower()

    @pytest.mark.unit
    def test_narrative_with_empty_fields(self) -> None:
        meta = ConfidenceMetadata(level=0.5, range_lower=0.3, range_upper=0.7)
        fmt = NarrativeFormatter()
        result = fmt.format(metadata=meta)
        assert "50%" in result
        assert len(result) > 10

    @pytest.mark.unit
    def test_probability_with_empty_fields(self) -> None:
        meta = ConfidenceMetadata(level=0.5, range_lower=0.3, range_upper=0.7)
        fmt = ProbabilityFormatter()
        result = fmt.format(metadata=meta)
        assert "50%" in result
        assert "Conditional on" not in result


class TestGetFormatter:
    """Tests for the get_formatter factory."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("fmt", "expected_type"),
        [
            (ConfidenceFormat.STRUCTURED, StructuredFormatter),
            (ConfidenceFormat.NARRATIVE, NarrativeFormatter),
            (ConfidenceFormat.BOTH, BothFormatter),
            (ConfidenceFormat.PROBABILITY, ProbabilityFormatter),
        ],
    )
    def test_returns_correct_formatter(
        self,
        fmt: ConfidenceFormat,
        expected_type: type,
    ) -> None:
        config = ConfidenceConfig(format=fmt)
        formatter = get_formatter(config)
        assert isinstance(formatter, expected_type)
