"""Destructive operation detector rule."""

import re
from datetime import UTC, datetime
from typing import Final

from ai_company.core.enums import ApprovalRiskLevel
from ai_company.security.models import (
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)

_RULE_NAME: Final[str] = "destructive_op_detector"

# Patterns that indicate destructive operations.
_DESTRUCTIVE_PATTERNS: Final[tuple[tuple[str, re.Pattern[str], str], ...]] = (
    (
        "rm -rf",
        re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|rm\s+-[a-zA-Z]*f[a-zA-Z]*r"),
        "deny",
    ),
    (
        "DROP TABLE",
        re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
        "escalate",
    ),
    (
        "DROP DATABASE",
        re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE),
        "deny",
    ),
    (
        "DELETE without WHERE",
        re.compile(
            r"\bDELETE\s+FROM\s+\w+\s*;",
            re.IGNORECASE,
        ),
        "escalate",
    ),
    (
        "TRUNCATE TABLE",
        re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
        "escalate",
    ),
    (
        "git push --force",
        re.compile(r"\bgit\s+push\s+.*--force\b"),
        "escalate",
    ),
    (
        "git reset --hard",
        re.compile(r"\bgit\s+reset\s+--hard\b"),
        "escalate",
    ),
    (
        "format/mkfs",
        re.compile(r"\b(?:mkfs|format)\b", re.IGNORECASE),
        "deny",
    ),
)


def _scan_value(value: str) -> tuple[str, str] | None:
    """Scan a single string for destructive patterns.

    Returns (pattern_name, verdict_str) or None.
    """
    for pattern_name, pattern, verdict_str in _DESTRUCTIVE_PATTERNS:
        if pattern.search(value):
            return pattern_name, verdict_str
    return None


def _scan_arguments(
    arguments: dict[str, object],
) -> list[tuple[str, str]]:
    """Recursively scan all string values for destructive patterns."""
    findings: list[tuple[str, str]] = []
    for value in arguments.values():
        if isinstance(value, str):
            if match := _scan_value(value):
                findings.append(match)
        elif isinstance(value, dict):
            findings.extend(_scan_arguments(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    if match := _scan_value(item):
                        findings.append(match)
                elif isinstance(item, dict):
                    findings.extend(_scan_arguments(item))
    return findings


class DestructiveOpDetector:
    """Detects destructive operations in tool call arguments.

    Scans for dangerous commands like ``rm -rf``, ``DROP TABLE``,
    ``git push --force``, etc.  Returns DENY for the most dangerous
    operations and ESCALATE for recoverable ones.
    """

    @property
    def name(self) -> str:
        """Rule name."""
        return _RULE_NAME

    def evaluate(
        self,
        context: SecurityContext,
    ) -> SecurityVerdict | None:
        """Scan arguments for destructive operations.

        Returns the most severe verdict found (DENY > ESCALATE).
        """
        findings = _scan_arguments(context.arguments)
        if not findings:
            return None

        # Pick the most severe verdict: deny > escalate.
        names = sorted({f[0] for f in findings})
        has_deny = any(f[1] == "deny" for f in findings)
        verdict = SecurityVerdictType.DENY if has_deny else SecurityVerdictType.ESCALATE
        return SecurityVerdict(
            verdict=verdict,
            reason=f"Destructive operation detected: {', '.join(names)}",
            risk_level=ApprovalRiskLevel.HIGH,
            matched_rules=(_RULE_NAME,),
            evaluated_at=datetime.now(UTC),
            evaluation_duration_ms=0.0,
        )
