"""Tests for safety classifier and uncertainty checker integration in SecOpsService."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.enums import ApprovalRiskLevel, ToolCategory
from synthorg.security.config import SecurityConfig
from synthorg.security.models import (
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)
from synthorg.security.safety_classifier import (
    SafetyClassification,
    SafetyClassifierResult,
)
from synthorg.security.service import SecOpsService
from synthorg.security.uncertainty import UncertaintyResult

# ── Helpers ───────────────────────────────────────────────────────


def _make_context(
    *,
    tool_name: str = "test-tool",
    action_type: str = "code:write",
) -> SecurityContext:
    return SecurityContext(
        tool_name=tool_name,
        tool_category=ToolCategory.FILE_SYSTEM,
        action_type=action_type,
        arguments={"path": "/workspace/test.py"},
        agent_id="agent-1",
        task_id="task-1",
    )


def _make_escalation_verdict() -> SecurityVerdict:
    return SecurityVerdict(
        verdict=SecurityVerdictType.ESCALATE,
        reason="Human approval required",
        risk_level=ApprovalRiskLevel.HIGH,
        evaluated_at=datetime.now(UTC),
        evaluation_duration_ms=1.0,
    )


def _make_service(
    *,
    safety_classifier: Any = None,
    uncertainty_checker: Any = None,
) -> SecOpsService:
    """Build a SecOpsService with mock dependencies."""
    approval_store = AsyncMock()
    approval_store.add = AsyncMock()

    rule_engine = MagicMock()
    rule_engine.evaluate = MagicMock(return_value=None)

    from synthorg.security.audit import AuditLog
    from synthorg.security.output_scanner import OutputScanner
    from synthorg.security.rules.engine import RuleEngine
    from synthorg.security.rules.risk_classifier import RiskClassifier

    real_rule_engine = RuleEngine(
        rules=(),
        risk_classifier=RiskClassifier(),
        config=SecurityConfig().rule_engine,
    )

    return SecOpsService(
        config=SecurityConfig(),
        rule_engine=real_rule_engine,
        audit_log=AuditLog(),
        output_scanner=OutputScanner(),
        approval_store=approval_store,
        safety_classifier=safety_classifier,
        uncertainty_checker=uncertainty_checker,
    )


# ── Tests: safety classifier integration ──────────────────────────


@pytest.mark.unit
class TestSafetyClassifierIntegration:
    """Safety classifier integration in _handle_escalation."""

    async def test_blocked_auto_rejects(self) -> None:
        """BLOCKED classification returns DENY, no approval item."""
        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(
            return_value=SafetyClassifierResult(
                classification=SafetyClassification.BLOCKED,
                stripped_description="stripped text",
                reason="Credential theft attempt",
                classification_duration_ms=5.0,
            ),
        )

        service = _make_service(safety_classifier=mock_classifier)
        context = _make_context()
        verdict = _make_escalation_verdict()

        result = await service._handle_escalation(context, verdict)

        assert result.verdict == SecurityVerdictType.DENY
        assert (
            "blocked" in result.reason.lower()
            or "auto-rejected" in result.reason.lower()
        )
        # Approval store should NOT have been called
        service._approval_store.add.assert_not_awaited()  # type: ignore[union-attr]

    async def test_suspicious_enriches_metadata(self) -> None:
        """SUSPICIOUS classification adds metadata to approval item."""
        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(
            return_value=SafetyClassifierResult(
                classification=SafetyClassification.SUSPICIOUS,
                stripped_description="stripped text here",
                reason="Unusual network pattern",
                classification_duration_ms=5.0,
            ),
        )

        service = _make_service(safety_classifier=mock_classifier)
        context = _make_context()
        verdict = _make_escalation_verdict()

        result = await service._handle_escalation(context, verdict)

        assert result.verdict == SecurityVerdictType.ESCALATE
        assert result.approval_id is not None

        # Check the approval item was stored with metadata
        call_args = service._approval_store.add.call_args  # type: ignore[union-attr]
        item = call_args[0][0]
        assert item.metadata["safety_classification"] == "suspicious"
        assert item.metadata["stripped_description"] == "stripped text here"
        assert item.metadata["safety_reason"] == "Unusual network pattern"

    async def test_safe_classification_normal_flow(self) -> None:
        """SAFE classification proceeds normally."""
        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(
            return_value=SafetyClassifierResult(
                classification=SafetyClassification.SAFE,
                stripped_description="stripped text",
                reason="Action appears safe",
                classification_duration_ms=3.0,
            ),
        )

        service = _make_service(safety_classifier=mock_classifier)
        context = _make_context()
        verdict = _make_escalation_verdict()

        result = await service._handle_escalation(context, verdict)

        assert result.verdict == SecurityVerdictType.ESCALATE
        assert result.approval_id is not None

        call_args = service._approval_store.add.call_args  # type: ignore[union-attr]
        item = call_args[0][0]
        assert item.metadata["safety_classification"] == "safe"

    async def test_classifier_error_still_creates_approval(self) -> None:
        """Classifier failure still creates approval item (fail-safe)."""
        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(
            side_effect=RuntimeError("LLM connection failed"),
        )

        service = _make_service(safety_classifier=mock_classifier)
        context = _make_context()
        verdict = _make_escalation_verdict()

        result = await service._handle_escalation(context, verdict)

        # Should still create the approval item despite classifier error
        assert result.verdict == SecurityVerdictType.ESCALATE
        assert result.approval_id is not None
        service._approval_store.add.assert_awaited_once()  # type: ignore[union-attr]


# ── Tests: uncertainty checker integration ────────────────────────


@pytest.mark.unit
class TestUncertaintyCheckerIntegration:
    """Uncertainty checker integration in _handle_escalation."""

    async def test_low_confidence_enriches_metadata(self) -> None:
        """Low confidence score is stored in metadata."""
        mock_checker = AsyncMock()
        mock_checker.check = AsyncMock(
            return_value=UncertaintyResult(
                confidence_score=0.3,
                provider_count=2,
                keyword_overlap=0.2,
                embedding_similarity=0.4,
                reason="Cross-provider check complete",
                check_duration_ms=50.0,
            ),
        )

        service = _make_service(uncertainty_checker=mock_checker)
        context = _make_context()
        verdict = _make_escalation_verdict()

        result = await service._handle_escalation(context, verdict)

        assert result.verdict == SecurityVerdictType.ESCALATE
        call_args = service._approval_store.add.call_args  # type: ignore[union-attr]
        item = call_args[0][0]
        assert item.metadata["confidence_score"] == "0.3"
        assert item.metadata["keyword_overlap"] == "0.2"
        assert item.metadata["embedding_similarity"] == "0.4"

    async def test_checker_error_still_creates_approval(self) -> None:
        """Checker failure still creates approval item."""
        mock_checker = AsyncMock()
        mock_checker.check = AsyncMock(
            side_effect=RuntimeError("Provider timeout"),
        )

        service = _make_service(uncertainty_checker=mock_checker)
        context = _make_context()
        verdict = _make_escalation_verdict()

        result = await service._handle_escalation(context, verdict)

        assert result.verdict == SecurityVerdictType.ESCALATE
        assert result.approval_id is not None
        service._approval_store.add.assert_awaited_once()  # type: ignore[union-attr]


# ── Tests: both features together ─────────────────────────────────


@pytest.mark.unit
class TestBothFeatures:
    """Both safety classifier and uncertainty checker active."""

    async def test_both_enrich_metadata(self) -> None:
        """Both features contribute metadata to the approval item."""
        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(
            return_value=SafetyClassifierResult(
                classification=SafetyClassification.SUSPICIOUS,
                stripped_description="stripped",
                reason="Unusual pattern",
                classification_duration_ms=5.0,
            ),
        )

        mock_checker = AsyncMock()
        mock_checker.check = AsyncMock(
            return_value=UncertaintyResult(
                confidence_score=0.7,
                provider_count=2,
                keyword_overlap=0.6,
                embedding_similarity=0.8,
                reason="Check complete",
                check_duration_ms=30.0,
            ),
        )

        service = _make_service(
            safety_classifier=mock_classifier,
            uncertainty_checker=mock_checker,
        )
        context = _make_context()
        verdict = _make_escalation_verdict()

        result = await service._handle_escalation(context, verdict)

        assert result.verdict == SecurityVerdictType.ESCALATE
        call_args = service._approval_store.add.call_args  # type: ignore[union-attr]
        item = call_args[0][0]
        assert item.metadata["safety_classification"] == "suspicious"
        assert item.metadata["confidence_score"] == "0.7"
        assert item.metadata["stripped_description"] == "stripped"

    async def test_blocked_skips_uncertainty_check(self) -> None:
        """When classifier returns BLOCKED, uncertainty check is skipped."""
        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(
            return_value=SafetyClassifierResult(
                classification=SafetyClassification.BLOCKED,
                stripped_description="stripped",
                reason="Blocked",
                classification_duration_ms=5.0,
            ),
        )

        mock_checker = AsyncMock()
        mock_checker.check = AsyncMock()

        service = _make_service(
            safety_classifier=mock_classifier,
            uncertainty_checker=mock_checker,
        )
        context = _make_context()
        verdict = _make_escalation_verdict()

        await service._handle_escalation(context, verdict)

        # Uncertainty checker should NOT be called when blocked
        mock_checker.check.assert_not_awaited()

    async def test_no_features_unchanged(self) -> None:
        """With neither feature, behavior is unchanged."""
        service = _make_service()
        context = _make_context()
        verdict = _make_escalation_verdict()

        result = await service._handle_escalation(context, verdict)

        assert result.verdict == SecurityVerdictType.ESCALATE
        assert result.approval_id is not None
        call_args = service._approval_store.add.call_args  # type: ignore[union-attr]
        item = call_args[0][0]
        # Only default metadata keys
        assert "safety_classification" not in item.metadata
        assert "confidence_score" not in item.metadata
