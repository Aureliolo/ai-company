"""Factory for the self-improvement meta-loop components.

Constructs strategies, guards, appliers, rollout strategies,
and regression detectors from configuration, filtering by
enabled altitudes and disabled rules.
"""

from copy import deepcopy
from types import MappingProxyType
from typing import TYPE_CHECKING

from synthorg.meta.appliers.architecture_applier import (
    ArchitectureApplier,
)
from synthorg.meta.appliers.config_applier import ConfigApplier
from synthorg.meta.appliers.prompt_applier import PromptApplier
from synthorg.meta.guards.approval_gate import ApprovalGateGuard
from synthorg.meta.guards.rate_limit import RateLimitGuard
from synthorg.meta.guards.rollback_plan import RollbackPlanGuard
from synthorg.meta.guards.scope_check import ScopeCheckGuard
from synthorg.meta.models import ProposalAltitude
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
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_CONFIG_LOADED,
    META_STRATEGY_REGISTERED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.meta.config import SelfImprovementConfig
    from synthorg.meta.protocol import (
        ImprovementStrategy,
        ProposalApplier,
        ProposalGuard,
    )

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
) -> tuple[ImprovementStrategy, ...]:
    """Build enabled improvement strategies.

    Args:
        config: Self-improvement configuration.

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


def build_appliers() -> Mapping[ProposalAltitude, ProposalApplier]:
    """Build proposal appliers for each altitude.

    Returns:
        Read-only mapping of altitude to applier.
    """
    return MappingProxyType(
        deepcopy(
            {
                ProposalAltitude.CONFIG_TUNING: ConfigApplier(),
                ProposalAltitude.ARCHITECTURE: ArchitectureApplier(),
                ProposalAltitude.PROMPT_TUNING: PromptApplier(),
            }
        )
    )


def build_regression_detector() -> TieredRegressionDetector:
    """Build the tiered regression detector.

    Returns:
        Configured TieredRegressionDetector.
    """
    return TieredRegressionDetector()


def build_rollout_strategies() -> Mapping[
    str, BeforeAfterRollout | CanarySubsetRollout
]:
    """Build available rollout strategies.

    Returns:
        Read-only mapping of strategy name to rollout strategy.
    """
    return MappingProxyType(
        deepcopy(
            {
                "before_after": BeforeAfterRollout(),
                "canary": CanarySubsetRollout(),
            }
        )
    )
