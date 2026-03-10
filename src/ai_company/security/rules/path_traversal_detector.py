"""Path traversal detector rule."""

import re
from datetime import UTC, datetime
from typing import Final

from ai_company.core.enums import ApprovalRiskLevel
from ai_company.security.models import (
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)

_RULE_NAME: Final[str] = "path_traversal_detector"

# Pre-compiled patterns for path traversal attacks.
_TRAVERSAL_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "directory traversal (../)",
        re.compile(r"(?:^|[/\\])\.\.(?:[/\\]|$)"),
    ),
    (
        "null byte injection",
        re.compile(r"\x00"),
    ),
    (
        "URL-encoded traversal (%2e%2e)",
        re.compile(r"%2e%2e[%/\\]|[/\\]%2e%2e", re.IGNORECASE),
    ),
    (
        "double-encoded traversal",
        re.compile(r"%252e%252e", re.IGNORECASE),
    ),
)


def _scan_value(value: str) -> str | None:
    """Scan a single string for traversal patterns."""
    for pattern_name, pattern in _TRAVERSAL_PATTERNS:
        if pattern.search(value):
            return pattern_name
    return None


def _scan_arguments(arguments: dict[str, object]) -> list[str]:
    """Recursively scan all string values for path traversal."""
    findings: list[str] = []
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


class PathTraversalDetector:
    """Detects path traversal attacks in tool call arguments.

    Looks for ``../`` sequences, null bytes, URL-encoded traversal,
    and double-encoded traversal patterns.
    """

    @property
    def name(self) -> str:
        """Rule name."""
        return _RULE_NAME

    def evaluate(
        self,
        context: SecurityContext,
    ) -> SecurityVerdict | None:
        """Scan arguments for path traversal patterns.

        Returns DENY with CRITICAL risk if traversal is detected.
        """
        findings = _scan_arguments(context.arguments)
        if not findings:
            return None
        unique = sorted(set(findings))
        return SecurityVerdict(
            verdict=SecurityVerdictType.DENY,
            reason=f"Path traversal detected: {', '.join(unique)}",
            risk_level=ApprovalRiskLevel.CRITICAL,
            matched_rules=(_RULE_NAME,),
            evaluated_at=datetime.now(UTC),
            evaluation_duration_ms=0.0,
        )
