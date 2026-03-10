"""Credential detector rule — finds secrets in tool arguments."""

import re
from datetime import UTC, datetime
from typing import Final

from ai_company.core.enums import ApprovalRiskLevel
from ai_company.security.models import (
    SecurityContext,
    SecurityVerdict,
    SecurityVerdictType,
)

_RULE_NAME: Final[str] = "credential_detector"

# Pre-compiled patterns for credential detection.
_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "AWS access key",
        re.compile(r"(?:^|[^A-Za-z0-9])(AKIA[0-9A-Z]{16})(?:[^A-Za-z0-9]|$)"),
    ),
    (
        "AWS secret key",
        re.compile(
            r"(?:aws_secret_access_key|secret_key)\s*[=:]\s*"
            r"[A-Za-z0-9/+=]{40}",
            re.IGNORECASE,
        ),
    ),
    (
        "Generic API key/token/secret",
        re.compile(
            r"(?:api[_-]?key|api[_-]?secret|auth[_-]?token|access[_-]?token"
            r"|secret[_-]?key|private[_-]?key|password)\s*[=:]\s*"
            r"""['\"]?[A-Za-z0-9_\-/.+=]{16,}['\"]?""",
            re.IGNORECASE,
        ),
    ),
    (
        "SSH private key",
        re.compile(r"-----BEGIN\s+(RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "Bearer token",
        re.compile(
            r"[Bb]earer\s+[A-Za-z0-9_\-/.+=]{20,}",
        ),
    ),
    (
        "GitHub personal access token",
        re.compile(r"(?:^|[^A-Za-z0-9])(ghp_[A-Za-z0-9]{36,})"),
    ),
    (
        "Generic secret assignment",
        re.compile(
            r"(?:SECRET|TOKEN|PASSWORD|CREDENTIAL)\s*[=:]\s*"
            r"""['\"]?[^\s'\"]{8,}['\"]?""",
            re.IGNORECASE,
        ),
    ),
)


def _scan_value(value: str) -> str | None:
    """Scan a single string for credential patterns.

    Returns the pattern name if found, else None.
    """
    for pattern_name, pattern in _PATTERNS:
        if pattern.search(value):
            return pattern_name
    return None


def _scan_arguments(arguments: dict[str, object]) -> list[str]:
    """Recursively scan all string values in arguments."""
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


class CredentialDetector:
    """Detects credentials and secrets in tool call arguments.

    Scans all string values in the arguments dict for patterns
    matching AWS keys, API tokens, SSH keys, and other secrets.
    """

    @property
    def name(self) -> str:
        """Rule name."""
        return _RULE_NAME

    def evaluate(
        self,
        context: SecurityContext,
    ) -> SecurityVerdict | None:
        """Scan arguments for credential patterns.

        Returns DENY with CRITICAL risk if any credential is found.
        """
        findings = _scan_arguments(context.arguments)
        if not findings:
            return None
        unique = sorted(set(findings))
        return SecurityVerdict(
            verdict=SecurityVerdictType.DENY,
            reason=f"Credential detected in arguments: {', '.join(unique)}",
            risk_level=ApprovalRiskLevel.CRITICAL,
            matched_rules=(_RULE_NAME,),
            evaluated_at=datetime.now(UTC),
            evaluation_duration_ms=0.0,
        )
