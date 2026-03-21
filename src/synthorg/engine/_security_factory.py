"""Security and tool factories for AgentEngine.

Extracted from ``agent_engine.py`` to keep that module within the
800-line limit.
"""

from typing import TYPE_CHECKING

from synthorg.engine.errors import ExecutionStateError
from synthorg.observability import get_logger
from synthorg.observability.events.security import (
    SECURITY_CONFIG_LOADED,
    SECURITY_DISABLED,
)
from synthorg.security.audit import AuditLog  # noqa: TC001
from synthorg.security.config import SecurityConfig  # noqa: TC001
from synthorg.security.output_scanner import OutputScanner
from synthorg.security.rules.credential_detector import CredentialDetector
from synthorg.security.rules.custom_policy_rule import CustomPolicyRule
from synthorg.security.rules.data_leak_detector import DataLeakDetector
from synthorg.security.rules.destructive_op_detector import (
    DestructiveOpDetector,
)
from synthorg.security.rules.engine import RuleEngine
from synthorg.security.rules.path_traversal_detector import (
    PathTraversalDetector,
)
from synthorg.security.rules.policy_validator import PolicyValidator
from synthorg.security.rules.risk_classifier import RiskClassifier
from synthorg.security.service import SecOpsService
from synthorg.security.timeout.risk_tier_classifier import DefaultRiskTierClassifier

if TYPE_CHECKING:
    from synthorg.api.approval_store import ApprovalStore
    from synthorg.core.agent import AgentIdentity
    from synthorg.security.autonomy.models import EffectiveAutonomy
    from synthorg.security.protocol import SecurityInterceptionStrategy
    from synthorg.tools.registry import ToolRegistry

logger = get_logger(__name__)


def make_security_interceptor(
    security_config: SecurityConfig | None,
    audit_log: AuditLog,
    *,
    approval_store: ApprovalStore | None = None,
    effective_autonomy: EffectiveAutonomy | None = None,
) -> SecurityInterceptionStrategy | None:
    """Build the SecOps security interceptor if configured.

    Args:
        security_config: Security configuration, or ``None`` to skip.
        audit_log: Audit log for security events.
        approval_store: Optional approval store for escalation items.
        effective_autonomy: Optional autonomy level override.

    Returns:
        A ``SecOpsService`` interceptor, or ``None`` if security is
        disabled or not configured.

    Raises:
        ExecutionStateError: If *effective_autonomy* is provided but
            no SecurityConfig is configured.
    """
    if security_config is None:
        if effective_autonomy is not None:
            msg = (
                "effective_autonomy cannot be enforced without "
                "SecurityConfig -- configure security or remove autonomy"
            )
            logger.error(SECURITY_DISABLED, note=msg)
            raise ExecutionStateError(msg)
        logger.warning(
            SECURITY_DISABLED,
            note="No SecurityConfig provided -- all security checks skipped",
        )
        return None
    if not security_config.enabled:
        if effective_autonomy is not None:
            msg = "effective_autonomy cannot be enforced when security is disabled"
            logger.error(SECURITY_DISABLED, note=msg)
            raise ExecutionStateError(msg)
        return None

    cfg = security_config
    rule_engine = _build_rule_engine(cfg)
    return SecOpsService(
        config=cfg,
        rule_engine=rule_engine,
        audit_log=audit_log,
        output_scanner=OutputScanner(),
        approval_store=approval_store,
        effective_autonomy=effective_autonomy,
        risk_classifier=DefaultRiskTierClassifier(),
    )


def _build_rule_engine(cfg: SecurityConfig) -> RuleEngine:
    """Assemble the rule engine with built-in detectors and custom policies."""
    re_cfg = cfg.rule_engine
    policy_validator = PolicyValidator(
        hard_deny_action_types=frozenset(cfg.hard_deny_action_types),
        auto_approve_action_types=frozenset(cfg.auto_approve_action_types),
    )
    rules: list[
        PolicyValidator
        | CredentialDetector
        | PathTraversalDetector
        | DestructiveOpDetector
        | DataLeakDetector
        | CustomPolicyRule
    ] = [policy_validator]

    # When custom_allow_bypasses_detectors is True, custom policies go
    # right after the policy validator (before detectors) so a custom
    # ALLOW can short-circuit security scanning.  Otherwise (default),
    # custom policies go after all detectors -- security scanning
    # always runs first.
    custom_rules = [CustomPolicyRule(p) for p in cfg.custom_policies if p.enabled]
    if re_cfg.custom_allow_bypasses_detectors:
        rules.extend(custom_rules)

    if re_cfg.credential_patterns_enabled:
        rules.append(CredentialDetector())
    if re_cfg.path_traversal_detection_enabled:
        rules.append(PathTraversalDetector())
    if re_cfg.destructive_op_detection_enabled:
        rules.append(DestructiveOpDetector())
    if re_cfg.data_leak_detection_enabled:
        rules.append(DataLeakDetector())

    if not re_cfg.custom_allow_bypasses_detectors:
        rules.extend(custom_rules)

    if custom_rules:
        log_level = (
            logger.warning if re_cfg.custom_allow_bypasses_detectors else logger.debug
        )
        log_level(
            SECURITY_CONFIG_LOADED,
            custom_policy_count=len(custom_rules),
            bypasses_detectors=re_cfg.custom_allow_bypasses_detectors,
        )

    return RuleEngine(
        rules=tuple(rules),
        risk_classifier=RiskClassifier(),
        config=re_cfg,
    )


def registry_with_approval_tool(
    tool_registry: ToolRegistry,
    approval_store: ApprovalStore | None,
    identity: AgentIdentity,
    task_id: str | None = None,
) -> ToolRegistry:
    """Build a registry with the approval tool added if applicable.

    Returns the original registry unchanged when no approval store
    is configured.
    """
    if approval_store is None:
        return tool_registry

    from synthorg.tools.approval_tool import (  # noqa: PLC0415
        RequestHumanApprovalTool,
    )
    from synthorg.tools.registry import (  # noqa: PLC0415
        ToolRegistry as _ToolRegistry,
    )

    approval_tool = RequestHumanApprovalTool(
        approval_store=approval_store,
        risk_classifier=DefaultRiskTierClassifier(),
        agent_id=str(identity.id),
        task_id=task_id,
    )
    existing = list(tool_registry.all_tools())
    return _ToolRegistry([*existing, approval_tool])
