"""Policy validator rule — checks action types against config lists."""

from datetime import UTC, datetime
from typing import Final

from ai_company.core.enums import ApprovalRiskLevel
from ai_company.security.models import (
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)

_RULE_NAME: Final[str] = "policy_validator"


class PolicyValidator:
    """Checks action type against hard-deny and auto-approve lists.

    This is the first rule evaluated — it provides the fast path for
    action types that are always denied or always approved.

    Args:
        hard_deny_action_types: Action types that are always denied.
        auto_approve_action_types: Action types that are always approved.
    """

    def __init__(
        self,
        *,
        hard_deny_action_types: frozenset[str],
        auto_approve_action_types: frozenset[str],
    ) -> None:
        self._hard_deny = hard_deny_action_types
        self._auto_approve = auto_approve_action_types

    @property
    def name(self) -> str:
        """Rule name."""
        return _RULE_NAME

    def evaluate(
        self,
        context: SecurityContext,
    ) -> SecurityVerdict | None:
        """Check action type against policy lists.

        Hard deny takes priority over auto approve. Returns None
        if the action type is in neither list.
        """
        if context.action_type in self._hard_deny:
            return SecurityVerdict(
                verdict=SecurityVerdictType.DENY,
                reason=(
                    f"Action type {context.action_type!r} is in the hard-deny list"
                ),
                risk_level=ApprovalRiskLevel.CRITICAL,
                matched_rules=(_RULE_NAME,),
                evaluated_at=datetime.now(UTC),
                evaluation_duration_ms=0.0,
            )
        if context.action_type in self._auto_approve:
            return SecurityVerdict(
                verdict=SecurityVerdictType.ALLOW,
                reason=(
                    f"Action type {context.action_type!r} is in the auto-approve list"
                ),
                risk_level=ApprovalRiskLevel.LOW,
                matched_rules=(_RULE_NAME,),
                evaluated_at=datetime.now(UTC),
                evaluation_duration_ms=0.0,
            )
        return None
