"""Tests for trust domain enumerations."""

import pytest

from ai_company.security.trust.enums import TrustChangeReason, TrustStrategyType

pytestmark = pytest.mark.timeout(30)


# ── TrustStrategyType ────────────────────────────────────────────


@pytest.mark.unit
class TestTrustStrategyType:
    """Tests for TrustStrategyType enum values."""

    def test_disabled_value(self) -> None:
        assert TrustStrategyType.DISABLED.value == "disabled"

    def test_weighted_value(self) -> None:
        assert TrustStrategyType.WEIGHTED.value == "weighted"

    def test_per_category_value(self) -> None:
        assert TrustStrategyType.PER_CATEGORY.value == "per_category"

    def test_milestone_value(self) -> None:
        assert TrustStrategyType.MILESTONE.value == "milestone"

    def test_members_are_strings(self) -> None:
        for member in TrustStrategyType:
            assert isinstance(member, str)

    def test_member_count(self) -> None:
        assert len(TrustStrategyType) == 4


# ── TrustChangeReason ────────────────────────────────────────────


@pytest.mark.unit
class TestTrustChangeReason:
    """Tests for TrustChangeReason enum values."""

    def test_score_threshold(self) -> None:
        assert TrustChangeReason.SCORE_THRESHOLD.value == "score_threshold"

    def test_milestone_achieved(self) -> None:
        assert TrustChangeReason.MILESTONE_ACHIEVED.value == "milestone_achieved"

    def test_human_approval(self) -> None:
        assert TrustChangeReason.HUMAN_APPROVAL.value == "human_approval"

    def test_trust_decay(self) -> None:
        assert TrustChangeReason.TRUST_DECAY.value == "trust_decay"

    def test_re_verification_failed(self) -> None:
        assert (
            TrustChangeReason.RE_VERIFICATION_FAILED.value == "re_verification_failed"
        )

    def test_manual(self) -> None:
        assert TrustChangeReason.MANUAL.value == "manual"

    def test_error_rate(self) -> None:
        assert TrustChangeReason.ERROR_RATE.value == "error_rate"

    def test_members_are_strings(self) -> None:
        for member in TrustChangeReason:
            assert isinstance(member, str)

    def test_member_count(self) -> None:
        assert len(TrustChangeReason) == 7
