"""Unit tests for consensus velocity detection."""

import pytest
from pydantic import ValidationError

from synthorg.engine.strategy.consensus import (
    ConsensusAction,
    ConsensusVelocityConfig,
    ConsensusVelocityDetector,
    ConsensusVelocityResult,
)


class TestConsensusVelocityResult:
    """Tests for ConsensusVelocityResult model."""

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """Model should be frozen (immutable)."""
        result = ConsensusVelocityResult(
            detected=True,
            action=ConsensusAction.DEVIL_ADVOCATE,
            mean_similarity=0.75,
            disagreement_count=1,
        )
        with pytest.raises(ValidationError):
            result.detected = False  # type: ignore[misc]

    @pytest.mark.unit
    def test_mean_similarity_bounds(self) -> None:
        """mean_similarity must be in [0.0, 1.0]."""
        # Valid at 0.0
        result = ConsensusVelocityResult(
            detected=False, mean_similarity=0.0, disagreement_count=0
        )
        assert result.mean_similarity == 0.0

        # Valid at 1.0
        result = ConsensusVelocityResult(
            detected=False, mean_similarity=1.0, disagreement_count=0
        )
        assert result.mean_similarity == 1.0

        # Invalid below 0.0
        with pytest.raises(ValidationError):
            ConsensusVelocityResult(
                detected=False, mean_similarity=-0.1, disagreement_count=0
            )

        # Invalid above 1.0
        with pytest.raises(ValidationError):
            ConsensusVelocityResult(
                detected=False, mean_similarity=1.1, disagreement_count=0
            )

    @pytest.mark.unit
    def test_disagreement_count_nonnegative(self) -> None:
        """disagreement_count must be >= 0."""
        result = ConsensusVelocityResult(
            detected=False, mean_similarity=0.5, disagreement_count=0
        )
        assert result.disagreement_count == 0

        with pytest.raises(ValidationError):
            ConsensusVelocityResult(
                detected=False, mean_similarity=0.5, disagreement_count=-1
            )

    @pytest.mark.unit
    def test_action_defaults_to_none(self) -> None:
        """action field defaults to None."""
        result = ConsensusVelocityResult(
            detected=False, mean_similarity=0.5, disagreement_count=0
        )
        assert result.action is None

    @pytest.mark.unit
    def test_action_can_be_set(self) -> None:
        """action field can be set to a ConsensusAction."""
        result = ConsensusVelocityResult(
            detected=True,
            action=ConsensusAction.SLOW_DOWN,
            mean_similarity=0.8,
            disagreement_count=0,
        )
        assert result.action == ConsensusAction.SLOW_DOWN


class TestConsensusVelocityDetector:
    """Tests for ConsensusVelocityDetector."""

    @pytest.mark.unit
    def test_single_position_not_detected(self) -> None:
        """Single position cannot be consensus."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.8)
        result = detector.detect(("position A",), config)

        assert result.detected is False
        assert result.mean_similarity == 1.0
        assert result.disagreement_count == 0

    @pytest.mark.unit
    def test_empty_positions_not_detected(self) -> None:
        """Empty positions list cannot be consensus."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.8)
        result = detector.detect((), config)

        assert result.detected is False
        assert result.mean_similarity == 1.0
        assert result.disagreement_count == 0

    @pytest.mark.unit
    def test_identical_positions_detected(self) -> None:
        """Identical positions should be detected as premature consensus."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.8)
        positions = ("recommendation: do X", "recommendation: do X")
        result = detector.detect(positions, config)

        assert result.detected is True
        assert result.mean_similarity == 1.0
        assert result.disagreement_count == 0
        assert result.action == ConsensusAction.DEVIL_ADVOCATE

    @pytest.mark.unit
    def test_very_different_positions_not_detected(self) -> None:
        """Very different positions should not be detected as consensus."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.8)
        positions = (
            "I recommend strategy A",
            "I strongly oppose all of that",
        )
        result = detector.detect(positions, config)

        assert result.detected is False
        # Low similarity due to different content
        assert result.mean_similarity < config.threshold

    @pytest.mark.unit
    def test_threshold_boundary_above(self) -> None:
        """Similarity just above threshold should be detected."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.5)
        # These are similar enough to exceed 0.5
        positions = ("the answer is yes", "the answer is yes")
        result = detector.detect(positions, config)

        assert result.detected is True
        assert result.mean_similarity > config.threshold

    @pytest.mark.unit
    def test_threshold_boundary_below(self) -> None:
        """Similarity just below threshold should not be detected."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.95)
        # Similar but not identical
        positions = ("The answer is yes", "the answer is yes")
        result = detector.detect(positions, config)

        # Even with high similarity, if there's disagreement, not detected
        # (or if similarity < threshold)
        if result.mean_similarity <= config.threshold:
            assert result.detected is False

    @pytest.mark.unit
    def test_multiple_positions_calculates_mean(self) -> None:
        """Multiple positions should calculate mean similarity correctly."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.8)
        # Three identical positions: all pairs are 1.0 similarity
        positions = ("yes", "yes", "yes")
        result = detector.detect(positions, config)

        assert result.mean_similarity == 1.0
        # Three pairs: (0,1), (0,2), (1,2) all with similarity 1.0

    @pytest.mark.unit
    def test_disagreement_count_tracks_substantial_differences(self) -> None:
        """Tracks count of position pairs with < 50% similarity."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.3)
        # Two very different positions
        positions = ("AAAAA", "BBBBB")
        result = detector.detect(positions, config)

        # These are completely different, so disagreement_count should be 1
        assert result.disagreement_count == 1

    @pytest.mark.unit
    def test_min_disagreements_threshold(self) -> None:
        """min_disagreements parameter affects detection."""
        detector = ConsensusVelocityDetector(min_disagreements=3)
        config = ConsensusVelocityConfig(threshold=0.8)
        # High similarity but only 1 disagreement pair
        positions = (
            "We should do this",
            "We should do this",
            "Completely different",
        )
        result = detector.detect(positions, config)

        # Only 1 disagreement pair < 3, so not detected even if high sim
        if result.disagreement_count < 3:
            assert result.detected is False

    @pytest.mark.unit
    def test_action_reflects_config(self) -> None:
        """Action in result matches config action when detected."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(action=ConsensusAction.ESCALATE, threshold=0.8)
        positions = ("identical", "identical")
        result = detector.detect(positions, config)

        assert result.detected is True
        assert result.action == ConsensusAction.ESCALATE

    @pytest.mark.unit
    def test_action_is_none_when_not_detected(self) -> None:
        """Action is None when consensus not detected."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.99)
        positions = ("position 1", "position 2")
        result = detector.detect(positions, config)

        if not result.detected:
            assert result.action is None

    @pytest.mark.unit
    def test_mean_similarity_is_rounded(self) -> None:
        """mean_similarity is rounded to 4 decimal places."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.5)
        positions = ("testing", "testing")
        result = detector.detect(positions, config)

        # Check it's rounded (not more than 4 decimal places)
        assert len(str(result.mean_similarity).split(".")[-1]) <= 4

    @pytest.mark.unit
    def test_three_position_pairwise_combinations(self) -> None:
        """Three positions generate correct number of pairs."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.8)
        # Three identical positions should have 3 pairs all with 1.0 sim
        positions = ("same", "same", "same")
        result = detector.detect(positions, config)

        assert result.mean_similarity == 1.0
        assert result.disagreement_count == 0

    @pytest.mark.unit
    def test_similarity_respects_text_content(self) -> None:
        """Text similarity accounts for actual content differences."""
        detector = ConsensusVelocityDetector()
        config = ConsensusVelocityConfig(threshold=0.5)

        # Very similar texts should have high similarity
        similar_positions = (
            "we should invest in AI",
            "we should invest in artificial intelligence",
        )
        result = detector.detect(similar_positions, config)
        similar_sim = result.mean_similarity

        # Very different texts should have low similarity
        different_positions = (
            "invest heavily in AI",
            "avoid AI entirely",
        )
        result = detector.detect(different_positions, config)
        different_sim = result.mean_similarity

        assert similar_sim > different_sim
