"""Security domain models.

Defines the value objects used by the SecOps service: security
verdicts, evaluation contexts, audit entries, and output scan results.
"""

from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ai_company.core.enums import ApprovalRiskLevel, ToolCategory  # noqa: TC001
from ai_company.core.types import NotBlankStr  # noqa: TC001


class SecurityVerdictType:
    """Security verdict constants (plain strings, not an enum).

    Using module-level constants avoids adding yet another StrEnum
    while keeping the same interface for comparisons.
    """

    ALLOW: str = "allow"
    DENY: str = "deny"
    ESCALATE: str = "escalate"


class SecurityVerdict(BaseModel):
    """Result of a security evaluation.

    Attributes:
        verdict: One of ``allow``, ``deny``, ``escalate``.
        reason: Human-readable explanation.
        risk_level: Assessed risk level for the action.
        matched_rules: Names of rules that triggered.
        evaluated_at: Timestamp of evaluation.
        evaluation_duration_ms: How long the evaluation took.
        approval_id: Set when verdict is ``escalate``.
    """

    model_config = ConfigDict(frozen=True)

    verdict: str
    reason: NotBlankStr
    risk_level: ApprovalRiskLevel
    matched_rules: tuple[NotBlankStr, ...] = ()
    evaluated_at: AwareDatetime
    evaluation_duration_ms: float = Field(ge=0.0)
    approval_id: NotBlankStr | None = None


class SecurityContext(BaseModel):
    """Context passed to the security evaluator before tool execution.

    Attributes:
        tool_name: Name of the tool being invoked.
        tool_category: Tool's category for access-level gating.
        action_type: Two-level ``category:action`` type string.
        arguments: Tool call arguments (deep-copied for inspection).
        agent_id: ID of the agent requesting the tool.
        task_id: ID of the task being executed.
    """

    model_config = ConfigDict(frozen=True)

    tool_name: NotBlankStr
    tool_category: ToolCategory
    action_type: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    agent_id: NotBlankStr | None = None
    task_id: NotBlankStr | None = None


class AuditEntry(BaseModel):
    """Immutable record of a security evaluation for the audit log.

    Attributes:
        id: Unique entry identifier.
        timestamp: When the evaluation occurred.
        agent_id: Agent that requested the tool.
        task_id: Task being executed.
        tool_name: Tool that was evaluated.
        tool_category: Tool category.
        action_type: Action type string.
        arguments_hash: SHA-256 of serialized arguments (never raw).
        verdict: Allow / deny / escalate.
        risk_level: Assessed risk level.
        reason: Explanation of the verdict.
        matched_rules: Rules that triggered.
        evaluation_duration_ms: Duration of evaluation.
        approval_id: Set when verdict is escalate.
    """

    model_config = ConfigDict(frozen=True)

    id: NotBlankStr
    timestamp: AwareDatetime
    agent_id: NotBlankStr | None = None
    task_id: NotBlankStr | None = None
    tool_name: NotBlankStr
    tool_category: ToolCategory
    action_type: str
    arguments_hash: str
    verdict: str
    risk_level: ApprovalRiskLevel
    reason: NotBlankStr
    matched_rules: tuple[NotBlankStr, ...] = ()
    evaluation_duration_ms: float = Field(ge=0.0)
    approval_id: NotBlankStr | None = None


class OutputScanResult(BaseModel):
    """Result of scanning tool output for sensitive data.

    Attributes:
        has_sensitive_data: Whether sensitive data was detected.
        findings: Descriptions of findings.
        redacted_content: Content with sensitive data replaced, or None.
    """

    model_config = ConfigDict(frozen=True)

    has_sensitive_data: bool = False
    findings: tuple[NotBlankStr, ...] = ()
    redacted_content: str | None = None
