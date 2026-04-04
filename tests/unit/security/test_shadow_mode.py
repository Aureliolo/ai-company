"""Tests for SecurityEnforcementMode and shadow mode behavior."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from synthorg.core.enums import ApprovalRiskLevel
from synthorg.security.config import SecurityConfig, SecurityEnforcementMode
from synthorg.security.models import (
    EvaluationConfidence,
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)
from synthorg.security.service import SecOpsService


def _make_context(
    *,
    tool_name: str = "test_tool",
    action_type: str = "code:write",
) -> SecurityContext:
    from synthorg.core.enums import ToolCategory

    return SecurityContext(
        tool_name=tool_name,
        tool_category=ToolCategory.FILE_SYSTEM,
        action_type=action_type,
    )


def _make_deny_verdict() -> SecurityVerdict:
    return SecurityVerdict(
        verdict=SecurityVerdictType.DENY,
        reason="Test denial",
        risk_level=ApprovalRiskLevel.HIGH,
        confidence=EvaluationConfidence.HIGH,
        evaluated_at=datetime.now(UTC),
        evaluation_duration_ms=1.0,
    )


def _make_allow_verdict() -> SecurityVerdict:
    return SecurityVerdict(
        verdict=SecurityVerdictType.ALLOW,
        reason="Test allow",
        risk_level=ApprovalRiskLevel.LOW,
        confidence=EvaluationConfidence.HIGH,
        evaluated_at=datetime.now(UTC),
        evaluation_duration_ms=1.0,
    )


@pytest.mark.unit
class TestSecurityEnforcementMode:
    """Tests for the SecurityEnforcementMode enum."""

    def test_active_value(self) -> None:
        assert SecurityEnforcementMode.ACTIVE == "active"

    def test_shadow_value(self) -> None:
        assert SecurityEnforcementMode.SHADOW == "shadow"

    def test_disabled_value(self) -> None:
        assert SecurityEnforcementMode.DISABLED == "disabled"

    def test_default_on_config(self) -> None:
        cfg = SecurityConfig()
        assert cfg.enforcement_mode == SecurityEnforcementMode.ACTIVE


@pytest.mark.unit
class TestShadowMode:
    """Tests for SecOpsService shadow mode behavior."""

    async def test_active_mode_deny_preserved(self) -> None:
        """In active mode, DENY verdicts are returned as-is."""
        rule_engine = MagicMock()
        rule_engine.evaluate.return_value = _make_deny_verdict()
        audit_log = MagicMock()
        output_scanner = MagicMock()

        service = SecOpsService(
            config=SecurityConfig(
                enforcement_mode=SecurityEnforcementMode.ACTIVE,
            ),
            rule_engine=rule_engine,
            audit_log=audit_log,
            output_scanner=output_scanner,
        )
        verdict = await service.evaluate_pre_tool(_make_context())
        assert verdict.verdict == SecurityVerdictType.DENY

    async def test_shadow_mode_deny_becomes_allow(self) -> None:
        """In shadow mode, DENY verdicts are logged but ALLOW is returned."""
        rule_engine = MagicMock()
        rule_engine.evaluate.return_value = _make_deny_verdict()
        audit_log = MagicMock()
        output_scanner = MagicMock()

        service = SecOpsService(
            config=SecurityConfig(
                enforcement_mode=SecurityEnforcementMode.SHADOW,
            ),
            rule_engine=rule_engine,
            audit_log=audit_log,
            output_scanner=output_scanner,
        )
        verdict = await service.evaluate_pre_tool(_make_context())
        assert verdict.verdict == SecurityVerdictType.ALLOW

    async def test_shadow_mode_allow_stays_allow(self) -> None:
        """In shadow mode, ALLOW verdicts remain ALLOW."""
        rule_engine = MagicMock()
        rule_engine.evaluate.return_value = _make_allow_verdict()
        audit_log = MagicMock()
        output_scanner = MagicMock()

        service = SecOpsService(
            config=SecurityConfig(
                enforcement_mode=SecurityEnforcementMode.SHADOW,
            ),
            rule_engine=rule_engine,
            audit_log=audit_log,
            output_scanner=output_scanner,
        )
        verdict = await service.evaluate_pre_tool(_make_context())
        assert verdict.verdict == SecurityVerdictType.ALLOW

    async def test_shadow_mode_audit_still_recorded(self) -> None:
        """In shadow mode, audit entries are still recorded."""
        rule_engine = MagicMock()
        rule_engine.evaluate.return_value = _make_deny_verdict()
        audit_log = MagicMock()
        output_scanner = MagicMock()

        service = SecOpsService(
            config=SecurityConfig(
                enforcement_mode=SecurityEnforcementMode.SHADOW,
                audit_enabled=True,
            ),
            rule_engine=rule_engine,
            audit_log=audit_log,
            output_scanner=output_scanner,
        )
        await service.evaluate_pre_tool(_make_context())
        audit_log.record.assert_called_once()

    async def test_disabled_mode_returns_allow(self) -> None:
        """In disabled mode, always returns ALLOW without running rules."""
        rule_engine = MagicMock()
        audit_log = MagicMock()
        output_scanner = MagicMock()

        service = SecOpsService(
            config=SecurityConfig(
                enforcement_mode=SecurityEnforcementMode.DISABLED,
            ),
            rule_engine=rule_engine,
            audit_log=audit_log,
            output_scanner=output_scanner,
        )
        verdict = await service.evaluate_pre_tool(_make_context())
        assert verdict.verdict == SecurityVerdictType.ALLOW
        rule_engine.evaluate.assert_not_called()
