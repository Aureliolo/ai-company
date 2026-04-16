"""Factory for the self-improvement meta-loop components.

Constructs strategies, guards, appliers, rollout strategies,
and regression detectors from configuration, filtering by
enabled altitudes and disabled rules.
"""

from copy import deepcopy
from types import MappingProxyType
from typing import TYPE_CHECKING, assert_never

from synthorg.meta.appliers.architecture_applier import (
    ArchitectureApplier,
    ArchitectureApplierContext,
)
from synthorg.meta.appliers.config_applier import (
    ConfigApplier,
    ConfigProvider,
)
from synthorg.meta.appliers.prompt_applier import (
    PromptApplier,
    PromptApplierContext,
)
from synthorg.meta.chief_of_staff.learning import (
    BayesianConfidenceAdjuster,
    ExponentialMovingAverageAdjuster,
)
from synthorg.meta.guards.approval_gate import ApprovalGateGuard
from synthorg.meta.guards.rate_limit import RateLimitGuard
from synthorg.meta.guards.rollback_plan import RollbackPlanGuard
from synthorg.meta.guards.scope_check import ScopeCheckGuard
from synthorg.meta.models import ProposalAltitude
from synthorg.meta.rollout.ab_test import ABTestRollout
from synthorg.meta.rollout.before_after import BeforeAfterRollout
from synthorg.meta.rollout.canary import CanarySubsetRollout
from synthorg.meta.rollout.regression.composite import (
    TieredRegressionDetector,
)
from synthorg.meta.rules.builtin import default_rules
from synthorg.meta.rules.engine import RuleEngine
from synthorg.meta.strategies.architecture import (
    ArchitectureProposalStrategy,
)
from synthorg.meta.strategies.config_tuning import ConfigTuningStrategy
from synthorg.meta.strategies.prompt_tuning import PromptTuningStrategy
from synthorg.meta.validation.scope_validator import ScopeValidator
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_CONFIG_LOADED,
    META_STRATEGY_REGISTERED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.meta.chief_of_staff.protocol import ConfidenceAdjuster
    from synthorg.meta.config import SelfImprovementConfig
    from synthorg.meta.protocol import (
        ImprovementStrategy,
        ProposalApplier,
        ProposalGuard,
    )
    from synthorg.providers.base import BaseCompletionProvider

logger = get_logger(__name__)


def build_rule_engine(
    config: SelfImprovementConfig,
) -> RuleEngine:
    """Build a RuleEngine from configuration.

    Loads default rules, filters out disabled rules.

    Args:
        config: Self-improvement configuration.

    Returns:
        Configured RuleEngine.
    """
    all_rules = default_rules()
    disabled = set(config.rules.disabled_rules)
    enabled = tuple(r for r in all_rules if r.name not in disabled)
    logger.info(
        META_CONFIG_LOADED,
        total_rules=len(all_rules),
        enabled_rules=len(enabled),
        disabled_rules=list(disabled),
    )
    return RuleEngine(rules=enabled)


def build_strategies(
    config: SelfImprovementConfig,
    *,
    provider: BaseCompletionProvider | None = None,
) -> tuple[ImprovementStrategy, ...]:
    """Build enabled improvement strategies.

    Args:
        config: Self-improvement configuration.
        provider: Completion provider for LLM-based strategies
            (required when code_modification_enabled is True).

    Returns:
        Tuple of enabled strategies.
    """
    strategies: list[ImprovementStrategy] = []
    if config.config_tuning_enabled:
        strategies.append(ConfigTuningStrategy(config=config))
        logger.debug(
            META_STRATEGY_REGISTERED,
            altitude="config_tuning",
        )
    if config.architecture_proposals_enabled:
        strategies.append(ArchitectureProposalStrategy(config=config))
        logger.debug(
            META_STRATEGY_REGISTERED,
            altitude="architecture",
        )
    if config.prompt_tuning_enabled:
        strategies.append(PromptTuningStrategy(config=config))
        logger.debug(
            META_STRATEGY_REGISTERED,
            altitude="prompt_tuning",
        )
    if config.code_modification_enabled:
        if provider is None:
            logger.warning(
                META_STRATEGY_REGISTERED,
                altitude="code_modification",
                reason="skipped_no_provider",
            )
        else:
            from synthorg.meta.strategies.code_modification import (  # noqa: PLC0415
                CodeModificationStrategy,
            )

            scope_validator = ScopeValidator(
                allowed_paths=tuple(
                    config.code_modification.allowed_paths,
                ),
                forbidden_paths=tuple(
                    config.code_modification.forbidden_paths,
                ),
            )
            strategies.append(
                CodeModificationStrategy(
                    config=config,
                    provider=provider,
                    scope_validator=scope_validator,
                ),
            )
            logger.debug(
                META_STRATEGY_REGISTERED,
                altitude="code_modification",
            )
    return tuple(strategies)


def build_guards(
    config: SelfImprovementConfig,
) -> tuple[ProposalGuard, ...]:
    """Build the proposal guard chain.

    Guards are always in this order: scope check, rollback plan,
    rate limit, approval gate.

    Args:
        config: Self-improvement configuration.

    Returns:
        Tuple of guards in evaluation order.
    """
    return (
        ScopeCheckGuard(config=config),
        RollbackPlanGuard(),
        RateLimitGuard(
            max_proposals=config.guards.proposal_rate_limit,
            window_hours=config.guards.rate_limit_window_hours,
        ),
        ApprovalGateGuard(),
    )


def build_appliers(
    config: SelfImprovementConfig | None = None,
    *,
    config_provider: ConfigProvider | None = None,
    prompt_context: PromptApplierContext | None = None,
    architecture_context: ArchitectureApplierContext | None = None,
) -> Mapping[ProposalAltitude, ProposalApplier]:
    """Build proposal appliers for each altitude.

    Args:
        config: Self-improvement configuration. When provided
            and ``code_modification_enabled``, includes the
            ``CodeApplier``.
        config_provider: Zero-arg callable returning the current
            ``RootConfig``.  Required for ``ConfigApplier.dry_run``
            to validate changes; callers that do not provide it get
            an applier whose ``dry_run`` returns an explicit error.
        prompt_context: Read-only view of prompt-scope targets.
            Required for ``PromptApplier.dry_run``.
        architecture_context: Read-only view of role / department /
            workflow registries.  Required for
            ``ArchitectureApplier.dry_run``.

    Returns:
        Read-only mapping of altitude to applier.
    """
    appliers: dict[ProposalAltitude, ProposalApplier] = {
        ProposalAltitude.CONFIG_TUNING: ConfigApplier(
            config_provider=config_provider,
        ),
        ProposalAltitude.ARCHITECTURE: ArchitectureApplier(
            context=architecture_context,
        ),
        ProposalAltitude.PROMPT_TUNING: PromptApplier(context=prompt_context),
    }
    if config is not None and config.code_modification_enabled:
        code_cfg = config.code_modification
        if code_cfg.github_token is None or code_cfg.github_repo is None:
            logger.warning(
                META_STRATEGY_REGISTERED,
                altitude="code_modification_applier",
                reason="skipped_no_github_credentials",
            )
        else:
            from synthorg.meta.appliers.code_applier import (  # noqa: PLC0415
                CodeApplier,
            )
            from synthorg.meta.appliers.github_client import (  # noqa: PLC0415
                HttpGitHubClient,
            )
            from synthorg.meta.validation.ci_validator import (  # noqa: PLC0415
                LocalCIValidator,
            )

            ci_validator = LocalCIValidator(
                timeout_seconds=code_cfg.ci_timeout_seconds,
            )
            github_client = HttpGitHubClient(
                token=str(code_cfg.github_token),
                repo=str(code_cfg.github_repo),
                base_branch=str(code_cfg.base_branch),
                timeout=code_cfg.api_timeout_seconds,
            )
            appliers[ProposalAltitude.CODE_MODIFICATION] = CodeApplier(
                ci_validator=ci_validator,
                github_client=github_client,
                code_modification_config=code_cfg,
            )
    return MappingProxyType(deepcopy(appliers))


def build_regression_detector() -> TieredRegressionDetector:
    """Build the tiered regression detector.

    Returns:
        Configured TieredRegressionDetector.
    """
    return TieredRegressionDetector()


def build_confidence_adjuster(
    config: SelfImprovementConfig,
) -> ConfidenceAdjuster:
    """Build a confidence adjuster strategy from config.

    Args:
        config: Self-improvement configuration.

    Returns:
        Configured confidence adjuster.
    """
    strategy = config.chief_of_staff.adjuster_strategy
    if strategy == "ema":
        return ExponentialMovingAverageAdjuster(
            alpha=config.chief_of_staff.ema_alpha,
        )
    if strategy == "bayesian":
        return BayesianConfidenceAdjuster()
    assert_never(strategy)


def build_rollout_strategies(
    config: SelfImprovementConfig | None = None,
) -> Mapping[str, BeforeAfterRollout | CanarySubsetRollout | ABTestRollout]:
    """Build available rollout strategies.

    Args:
        config: Self-improvement configuration. When provided,
            A/B test strategy uses its rollout.ab_test settings.

    Returns:
        Read-only mapping of strategy name to rollout strategy.
    """
    ab_cfg = config.rollout.ab_test if config else None
    return MappingProxyType(
        deepcopy(
            {
                "before_after": BeforeAfterRollout(),
                "canary": CanarySubsetRollout(),
                "ab_test": ABTestRollout(
                    control_fraction=(ab_cfg.control_fraction if ab_cfg else 0.5),
                    min_agents_per_group=(ab_cfg.min_agents_per_group if ab_cfg else 5),
                    min_observations_per_group=(
                        ab_cfg.min_observations_per_group if ab_cfg else 10
                    ),
                    improvement_threshold=(
                        ab_cfg.improvement_threshold if ab_cfg else 0.15
                    ),
                ),
            }
        )
    )
