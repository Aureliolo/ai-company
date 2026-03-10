"""Output scanner — post-tool output scanning for sensitive data.

Reuses credential and PII patterns from rule detectors to scan tool
output.  Never silently suppresses — always logs findings at WARNING.
"""

import re
from typing import Final

from ai_company.observability import get_logger
from ai_company.observability.events.security import (
    SECURITY_OUTPUT_SCAN_FINDING,
    SECURITY_OUTPUT_SCAN_START,
)
from ai_company.security.models import OutputScanResult

logger = get_logger(__name__)

# Patterns reused from credential_detector and data_leak_detector.
_OUTPUT_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "AWS access key",
        re.compile(r"(?:^|[^A-Za-z0-9])(AKIA[0-9A-Z]{16})(?:[^A-Za-z0-9]|$)"),
    ),
    (
        "SSH private key",
        re.compile(r"-----BEGIN\s+(RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "Bearer token",
        re.compile(r"[Bb]earer\s+[A-Za-z0-9_\-/.+=]{20,}"),
    ),
    (
        "GitHub PAT",
        re.compile(r"(?:^|[^A-Za-z0-9])(ghp_[A-Za-z0-9]{36,})"),
    ),
    (
        "Generic secret value",
        re.compile(
            r"(?:SECRET|TOKEN|PASSWORD|CREDENTIAL)\s*[=:]\s*"
            r"""['\"]?[^\s'\"]{8,}['\"]?""",
            re.IGNORECASE,
        ),
    ),
    (
        "Social Security Number",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
    (
        "Credit card number",
        re.compile(r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6011)\d{12}\b"),
    ),
)

# Replacement placeholder.
_REDACTED: Final[str] = "[REDACTED]"


class OutputScanner:
    """Scans tool output for sensitive data and optionally redacts it."""

    def scan(self, output: str) -> OutputScanResult:
        """Scan output text for sensitive patterns.

        Args:
            output: The tool's output string.

        Returns:
            An ``OutputScanResult`` with findings and optional
            redacted content.
        """
        logger.debug(
            SECURITY_OUTPUT_SCAN_START,
            output_length=len(output),
        )
        findings: list[str] = []
        redacted = output

        for pattern_name, pattern in _OUTPUT_PATTERNS:
            if pattern.search(output):
                findings.append(pattern_name)
                logger.warning(
                    SECURITY_OUTPUT_SCAN_FINDING,
                    finding=pattern_name,
                )
                redacted = pattern.sub(_REDACTED, redacted)

        if not findings:
            return OutputScanResult()

        return OutputScanResult(
            has_sensitive_data=True,
            findings=tuple(sorted(set(findings))),
            redacted_content=redacted,
        )
