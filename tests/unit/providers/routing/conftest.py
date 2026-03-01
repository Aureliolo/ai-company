"""Test fixtures and factories for the routing subpackage."""

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from ai_company.config.schema import (
    ProviderConfig,
    ProviderModelConfig,
    RoutingConfig,
    RoutingRuleConfig,
)
from ai_company.core.enums import SeniorityLevel
from ai_company.providers.routing.models import (
    ResolvedModel,
    RoutingDecision,
    RoutingRequest,
)
from ai_company.providers.routing.resolver import (
    ModelResolver,
)

# ── Factories ─────────────────────────────────────────────────────


class ResolvedModelFactory(ModelFactory[ResolvedModel]):
    """Factory for ResolvedModel."""

    __model__ = ResolvedModel
    provider_name = "anthropic"
    model_id = "claude-sonnet-4-6"
    alias = "sonnet"
    cost_per_1k_input = 0.003
    cost_per_1k_output = 0.015
    max_context = 200_000


class RoutingRequestFactory(ModelFactory[RoutingRequest]):
    """Factory for RoutingRequest."""

    __model__ = RoutingRequest
    agent_level = None
    task_type = None
    model_override = None
    remaining_budget = None


class RoutingDecisionFactory(ModelFactory[RoutingDecision]):
    """Factory for RoutingDecision."""

    __model__ = RoutingDecision
    resolved_model = ResolvedModelFactory
    strategy_used = "manual"
    reason = "test decision"
    fallbacks_tried = ()


# ── Standard 3-model provider config ─────────────────────────────

HAIKU_MODEL = ProviderModelConfig(
    id="claude-haiku-4-5",
    alias="haiku",
    cost_per_1k_input=0.001,
    cost_per_1k_output=0.005,
    max_context=200_000,
)

SONNET_MODEL = ProviderModelConfig(
    id="claude-sonnet-4-6",
    alias="sonnet",
    cost_per_1k_input=0.003,
    cost_per_1k_output=0.015,
    max_context=200_000,
)

OPUS_MODEL = ProviderModelConfig(
    id="claude-opus-4-6",
    alias="opus",
    cost_per_1k_input=0.015,
    cost_per_1k_output=0.075,
    max_context=200_000,
)


@pytest.fixture
def three_model_provider() -> dict[str, ProviderConfig]:
    """Provider config with haiku, sonnet, opus."""
    return {
        "anthropic": ProviderConfig(
            driver="litellm",
            api_key="sk-test",
            models=(HAIKU_MODEL, SONNET_MODEL, OPUS_MODEL),
        ),
    }


@pytest.fixture
def resolver(
    three_model_provider: dict[str, ProviderConfig],
) -> ModelResolver:
    """Resolver built from the 3-model provider."""
    return ModelResolver.from_config(three_model_provider)


@pytest.fixture
def standard_routing_config() -> RoutingConfig:
    """Routing config with role-based rules and fallback chain."""
    return RoutingConfig(
        strategy="role_based",
        rules=(
            RoutingRuleConfig(
                role_level=SeniorityLevel.JUNIOR,
                preferred_model="haiku",
            ),
            RoutingRuleConfig(
                role_level=SeniorityLevel.SENIOR,
                preferred_model="sonnet",
                fallback="haiku",
            ),
            RoutingRuleConfig(
                role_level=SeniorityLevel.C_SUITE,
                preferred_model="opus",
                fallback="sonnet",
            ),
            RoutingRuleConfig(
                task_type="review",
                preferred_model="opus",
            ),
        ),
        fallback_chain=("sonnet", "haiku"),
    )
