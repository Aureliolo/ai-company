"""Tests for routing strategies."""

import pytest

from ai_company.config.schema import (
    ProviderConfig,
    RoutingConfig,
    RoutingRuleConfig,
)
from ai_company.core.enums import SeniorityLevel
from ai_company.providers.routing.errors import (
    ModelResolutionError,
    NoAvailableModelError,
)
from ai_company.providers.routing.models import RoutingRequest
from ai_company.providers.routing.resolver import ModelResolver
from ai_company.providers.routing.strategies import (
    STRATEGY_MAP,
    CostAwareStrategy,
    ManualStrategy,
    RoleBasedStrategy,
    RoutingStrategy,
    SmartStrategy,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]


# ── Protocol conformance ─────────────────────────────────────────


class TestRoutingStrategyProtocol:
    @pytest.mark.parametrize(
        "cls",
        [ManualStrategy, RoleBasedStrategy, CostAwareStrategy, SmartStrategy],
    )
    def test_implements_protocol(self, cls: type) -> None:
        assert isinstance(cls(), RoutingStrategy)

    def test_strategy_map_has_all_names(self) -> None:
        expected = {"manual", "role_based", "cost_aware", "smart", "cheapest"}
        assert set(STRATEGY_MAP) == expected


# ── ManualStrategy ───────────────────────────────────────────────


class TestManualStrategy:
    def test_resolves_explicit_override(
        self,
        resolver: ModelResolver,
    ) -> None:
        strategy = ManualStrategy()
        request = RoutingRequest(model_override="sonnet")
        config = RoutingConfig()

        decision = strategy.select(request, config, resolver)

        assert decision.resolved_model.model_id == "claude-sonnet-4-6"
        assert decision.strategy_used == "manual"
        assert "override" in decision.reason.lower()

    def test_resolves_by_model_id(
        self,
        resolver: ModelResolver,
    ) -> None:
        strategy = ManualStrategy()
        request = RoutingRequest(model_override="claude-opus-4-6")

        decision = strategy.select(request, RoutingConfig(), resolver)

        assert decision.resolved_model.model_id == "claude-opus-4-6"

    def test_raises_without_override(
        self,
        resolver: ModelResolver,
    ) -> None:
        strategy = ManualStrategy()
        request = RoutingRequest()

        with pytest.raises(ModelResolutionError, match="model_override"):
            strategy.select(request, RoutingConfig(), resolver)

    def test_raises_for_unknown_model(
        self,
        resolver: ModelResolver,
    ) -> None:
        strategy = ManualStrategy()
        request = RoutingRequest(model_override="nonexistent")

        with pytest.raises(ModelResolutionError, match="not found"):
            strategy.select(request, RoutingConfig(), resolver)


# ── RoleBasedStrategy ────────────────────────────────────────────


class TestRoleBasedStrategy:
    def test_matches_role_rule(
        self,
        resolver: ModelResolver,
        standard_routing_config: RoutingConfig,
    ) -> None:
        strategy = RoleBasedStrategy()
        request = RoutingRequest(agent_level=SeniorityLevel.JUNIOR)

        decision = strategy.select(request, standard_routing_config, resolver)

        assert decision.resolved_model.alias == "haiku"
        assert decision.strategy_used == "role_based"

    def test_matches_senior_rule(
        self,
        resolver: ModelResolver,
        standard_routing_config: RoutingConfig,
    ) -> None:
        strategy = RoleBasedStrategy()
        request = RoutingRequest(agent_level=SeniorityLevel.SENIOR)

        decision = strategy.select(request, standard_routing_config, resolver)

        assert decision.resolved_model.alias == "sonnet"

    def test_matches_csuite_rule(
        self,
        resolver: ModelResolver,
        standard_routing_config: RoutingConfig,
    ) -> None:
        strategy = RoleBasedStrategy()
        request = RoutingRequest(agent_level=SeniorityLevel.C_SUITE)

        decision = strategy.select(request, standard_routing_config, resolver)

        assert decision.resolved_model.alias == "opus"

    def test_falls_back_to_seniority_default(
        self,
        resolver: ModelResolver,
    ) -> None:
        """MID has no rule -> uses seniority catalog (sonnet tier)."""
        strategy = RoleBasedStrategy()
        config = RoutingConfig(strategy="role_based")
        request = RoutingRequest(agent_level=SeniorityLevel.MID)

        decision = strategy.select(request, config, resolver)

        assert decision.resolved_model.alias == "sonnet"
        assert "seniority" in decision.reason.lower()

    def test_falls_back_to_global_chain(
        self,
        three_model_provider: dict[str, ProviderConfig],
    ) -> None:
        """LEAD has tier=opus; if opus not registered, use fallback chain."""
        provider = ProviderConfig(
            models=(
                three_model_provider["anthropic"].models[0],  # haiku only
            ),
        )
        resolver = ModelResolver.from_config({"anthropic": provider})
        config = RoutingConfig(
            strategy="role_based",
            fallback_chain=("haiku",),
        )
        request = RoutingRequest(agent_level=SeniorityLevel.LEAD)

        decision = RoleBasedStrategy().select(request, config, resolver)

        assert decision.resolved_model.alias == "haiku"

    def test_raises_without_agent_level(
        self,
        resolver: ModelResolver,
    ) -> None:
        strategy = RoleBasedStrategy()
        request = RoutingRequest()

        with pytest.raises(ModelResolutionError, match="agent_level"):
            strategy.select(request, RoutingConfig(), resolver)

    def test_raises_when_no_models_available(self) -> None:
        resolver = ModelResolver.from_config({})
        config = RoutingConfig(strategy="role_based")
        request = RoutingRequest(agent_level=SeniorityLevel.MID)

        with pytest.raises(NoAvailableModelError):
            RoleBasedStrategy().select(request, config, resolver)

    def test_rule_fallback_used(
        self,
        three_model_provider: dict[str, ProviderConfig],
    ) -> None:
        """When preferred not found, rule's fallback is tried."""
        provider = ProviderConfig(
            models=(
                three_model_provider["anthropic"].models[0],  # haiku only
            ),
        )
        resolver = ModelResolver.from_config({"anthropic": provider})
        config = RoutingConfig(
            strategy="role_based",
            rules=(
                RoutingRuleConfig(
                    role_level=SeniorityLevel.SENIOR,
                    preferred_model="sonnet",  # not available
                    fallback="haiku",
                ),
            ),
        )
        request = RoutingRequest(agent_level=SeniorityLevel.SENIOR)

        decision = RoleBasedStrategy().select(request, config, resolver)

        assert decision.resolved_model.alias == "haiku"
        assert "sonnet" in decision.fallbacks_tried


# ── CostAwareStrategy ────────────────────────────────────────────


class TestCostAwareStrategy:
    def test_picks_cheapest(self, resolver: ModelResolver) -> None:
        strategy = CostAwareStrategy()
        request = RoutingRequest()

        decision = strategy.select(request, RoutingConfig(), resolver)

        assert decision.resolved_model.alias == "haiku"
        assert decision.strategy_used == "cost_aware"

    def test_task_type_rule_takes_priority(
        self,
        resolver: ModelResolver,
        standard_routing_config: RoutingConfig,
    ) -> None:
        strategy = CostAwareStrategy()
        request = RoutingRequest(task_type="review")

        decision = strategy.select(request, standard_routing_config, resolver)

        assert decision.resolved_model.alias == "opus"

    def test_budget_filters_models(self, resolver: ModelResolver) -> None:
        """With tight budget, should still return cheapest."""
        strategy = CostAwareStrategy()
        request = RoutingRequest(remaining_budget=0.01)

        decision = strategy.select(request, RoutingConfig(), resolver)

        assert decision.resolved_model.alias == "haiku"

    def test_budget_exceeded_still_returns(self, resolver: ModelResolver) -> None:
        """Even if budget is 0.0, returns cheapest with warning."""
        strategy = CostAwareStrategy()
        request = RoutingRequest(remaining_budget=0.0)

        decision = strategy.select(request, RoutingConfig(), resolver)

        assert decision.resolved_model.alias == "haiku"
        assert "exceed" in decision.reason.lower()

    def test_no_models_raises(self) -> None:
        resolver = ModelResolver.from_config({})
        strategy = CostAwareStrategy()

        with pytest.raises(NoAvailableModelError):
            strategy.select(
                RoutingRequest(),
                RoutingConfig(),
                resolver,
            )

    def test_task_type_miss_falls_to_cheapest(
        self,
        resolver: ModelResolver,
    ) -> None:
        """Unmatched task_type => cheapest."""
        strategy = CostAwareStrategy()
        config = RoutingConfig(
            rules=(
                RoutingRuleConfig(
                    task_type="review",
                    preferred_model="opus",
                ),
            ),
        )
        request = RoutingRequest(task_type="development")

        decision = strategy.select(request, config, resolver)

        assert decision.resolved_model.alias == "haiku"


# ── SmartStrategy ────────────────────────────────────────────────


class TestSmartStrategy:
    def test_override_takes_priority(
        self,
        resolver: ModelResolver,
        standard_routing_config: RoutingConfig,
    ) -> None:
        strategy = SmartStrategy()
        request = RoutingRequest(
            model_override="opus",
            agent_level=SeniorityLevel.JUNIOR,
            task_type="review",
        )

        decision = strategy.select(request, standard_routing_config, resolver)

        assert decision.resolved_model.alias == "opus"
        assert "override" in decision.reason.lower()

    def test_task_type_before_role(
        self,
        resolver: ModelResolver,
        standard_routing_config: RoutingConfig,
    ) -> None:
        strategy = SmartStrategy()
        request = RoutingRequest(
            agent_level=SeniorityLevel.JUNIOR,
            task_type="review",
        )

        decision = strategy.select(request, standard_routing_config, resolver)

        # review rule -> opus; junior role rule -> haiku; task wins
        assert decision.resolved_model.alias == "opus"
        assert "task-type" in decision.reason.lower()

    def test_role_rule_when_no_task_match(
        self,
        resolver: ModelResolver,
        standard_routing_config: RoutingConfig,
    ) -> None:
        strategy = SmartStrategy()
        request = RoutingRequest(agent_level=SeniorityLevel.JUNIOR)

        decision = strategy.select(request, standard_routing_config, resolver)

        assert decision.resolved_model.alias == "haiku"

    def test_seniority_default_when_no_rules(
        self,
        resolver: ModelResolver,
    ) -> None:
        """No rules -> uses seniority catalog."""
        strategy = SmartStrategy()
        config = RoutingConfig()
        request = RoutingRequest(agent_level=SeniorityLevel.MID)

        decision = strategy.select(request, config, resolver)

        assert decision.resolved_model.alias == "sonnet"
        assert "seniority" in decision.reason.lower()

    def test_cheapest_when_no_level(self, resolver: ModelResolver) -> None:
        strategy = SmartStrategy()
        request = RoutingRequest()

        decision = strategy.select(request, RoutingConfig(), resolver)

        assert decision.resolved_model.alias == "haiku"

    def test_fallback_chain_last_resort(
        self,
        three_model_provider: dict[str, ProviderConfig],
    ) -> None:
        """Empty resolver but fallback chain has a valid ref."""
        # Build resolver with only haiku
        provider = ProviderConfig(
            models=(three_model_provider["anthropic"].models[0],),
        )
        resolver = ModelResolver.from_config({"anthropic": provider})
        config = RoutingConfig(fallback_chain=("haiku",))
        # Override is unknown, no role, no task
        request = RoutingRequest(model_override="nonexistent")

        decision = SmartStrategy().select(request, config, resolver)

        assert decision.resolved_model.alias == "haiku"

    def test_raises_when_nothing_available(self) -> None:
        resolver = ModelResolver.from_config({})
        config = RoutingConfig()
        request = RoutingRequest()

        with pytest.raises(NoAvailableModelError):
            SmartStrategy().select(request, config, resolver)

    def test_budget_aware_in_cheapest_fallback(
        self,
        resolver: ModelResolver,
    ) -> None:
        strategy = SmartStrategy()
        request = RoutingRequest(remaining_budget=0.0)

        decision = strategy.select(request, RoutingConfig(), resolver)

        assert decision.resolved_model.alias == "haiku"
        assert "exceed" in decision.reason.lower()
