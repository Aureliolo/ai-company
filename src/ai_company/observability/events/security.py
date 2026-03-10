"""Security event constants."""

from typing import Final

SECURITY_EVALUATE_START: Final[str] = "security.evaluate.start"
SECURITY_EVALUATE_COMPLETE: Final[str] = "security.evaluate.complete"
SECURITY_RULE_MATCHED: Final[str] = "security.rule.matched"
SECURITY_VERDICT_ALLOW: Final[str] = "security.verdict.allow"
SECURITY_VERDICT_DENY: Final[str] = "security.verdict.deny"
SECURITY_VERDICT_ESCALATE: Final[str] = "security.verdict.escalate"
SECURITY_AUDIT_RECORDED: Final[str] = "security.audit.recorded"
SECURITY_OUTPUT_SCAN_START: Final[str] = "security.output_scan.start"
SECURITY_OUTPUT_SCAN_FINDING: Final[str] = "security.output_scan.finding"
SECURITY_ESCALATION_CREATED: Final[str] = "security.escalation.created"
SECURITY_CONFIG_LOADED: Final[str] = "security.config.loaded"
SECURITY_DISABLED: Final[str] = "security.disabled"
