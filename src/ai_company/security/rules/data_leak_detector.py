"""Data leak detector rule — finds sensitive file paths and PII."""

import re
from datetime import UTC, datetime
from typing import Final

from ai_company.core.enums import ApprovalRiskLevel
from ai_company.security.models import (
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)

_RULE_NAME: Final[str] = "data_leak_detector"

# Sensitive file path patterns (case-insensitive).
_SENSITIVE_PATHS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\.env(?:\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"id_rsa(?:\.pub)?$"),
    re.compile(r"id_ed25519(?:\.pub)?$"),
    re.compile(r"id_ecdsa(?:\.pub)?$"),
    re.compile(r"id_dsa(?:\.pub)?$"),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"\.pfx$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"\.aws[/\\]credentials$"),
    re.compile(r"\.ssh[/\\]config$"),
    re.compile(r"\.netrc$"),
    re.compile(r"\.pgpass$"),
    re.compile(r"credentials\.json$", re.IGNORECASE),
    re.compile(r"secrets\.ya?ml$", re.IGNORECASE),
    re.compile(r"\.kube[/\\]config$"),
)

# PII patterns.
_PII_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "Social Security Number",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
    (
        "Credit card number",
        re.compile(r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6011)\d{12}\b"),
    ),
)


def _check_sensitive_paths(arguments: dict[str, object]) -> list[str]:
    """Find sensitive file paths in argument values."""
    findings: list[str] = []
    for value in arguments.values():
        if isinstance(value, str):
            for pattern in _SENSITIVE_PATHS:
                if pattern.search(value):
                    findings.append(f"sensitive path: {value}")
                    break
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    for pattern in _SENSITIVE_PATHS:
                        if pattern.search(item):
                            findings.append(f"sensitive path: {item}")
                            break
    return findings


def _check_pii(arguments: dict[str, object]) -> list[str]:
    """Find PII patterns in string argument values."""
    findings: list[str] = []
    for value in arguments.values():
        if isinstance(value, str):
            for name, pattern in _PII_PATTERNS:
                if pattern.search(value):
                    findings.append(name)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    for name, pattern in _PII_PATTERNS:
                        if pattern.search(item):
                            findings.append(name)
    return findings


class DataLeakDetector:
    """Detects access to sensitive file paths and PII in arguments."""

    @property
    def name(self) -> str:
        """Rule name."""
        return _RULE_NAME

    def evaluate(
        self,
        context: SecurityContext,
    ) -> SecurityVerdict | None:
        """Scan arguments for sensitive paths and PII.

        Returns DENY with HIGH risk if any sensitive data is found.
        """
        findings = _check_sensitive_paths(context.arguments)
        findings.extend(_check_pii(context.arguments))
        if not findings:
            return None
        unique = sorted(set(findings))
        return SecurityVerdict(
            verdict=SecurityVerdictType.DENY,
            reason=f"Data leak risk: {', '.join(unique)}",
            risk_level=ApprovalRiskLevel.HIGH,
            matched_rules=(_RULE_NAME,),
            evaluated_at=datetime.now(UTC),
            evaluation_duration_ms=0.0,
        )
