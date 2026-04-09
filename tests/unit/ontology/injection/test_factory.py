"""Tests for injection strategy factory."""

from unittest.mock import AsyncMock

import pytest

from synthorg.ontology.config import InjectionStrategy, OntologyInjectionConfig
from synthorg.ontology.injection.factory import create_injection_strategy
from synthorg.ontology.injection.hybrid import HybridInjectionStrategy
from synthorg.ontology.injection.memory import MemoryBasedInjectionStrategy
from synthorg.ontology.injection.prompt import PromptInjectionStrategy
from synthorg.ontology.injection.tool import ToolBasedInjectionStrategy


@pytest.mark.unit
class TestCreateInjectionStrategy:
    """Tests for create_injection_strategy factory."""

    def test_prompt_strategy(self, mock_backend: AsyncMock) -> None:
        """PROMPT config creates PromptInjectionStrategy."""
        config = OntologyInjectionConfig(strategy=InjectionStrategy.PROMPT)
        strategy = create_injection_strategy(config, mock_backend)
        assert isinstance(strategy, PromptInjectionStrategy)

    def test_tool_strategy(self, mock_backend: AsyncMock) -> None:
        """TOOL config creates ToolBasedInjectionStrategy."""
        config = OntologyInjectionConfig(strategy=InjectionStrategy.TOOL)
        strategy = create_injection_strategy(config, mock_backend)
        assert isinstance(strategy, ToolBasedInjectionStrategy)

    def test_hybrid_strategy(self, mock_backend: AsyncMock) -> None:
        """HYBRID config creates HybridInjectionStrategy."""
        config = OntologyInjectionConfig(strategy=InjectionStrategy.HYBRID)
        strategy = create_injection_strategy(config, mock_backend)
        assert isinstance(strategy, HybridInjectionStrategy)

    def test_memory_strategy(self, mock_backend: AsyncMock) -> None:
        """MEMORY config creates MemoryBasedInjectionStrategy."""
        config = OntologyInjectionConfig(strategy=InjectionStrategy.MEMORY)
        strategy = create_injection_strategy(config, mock_backend)
        assert isinstance(strategy, MemoryBasedInjectionStrategy)

    def test_default_is_hybrid(self, mock_backend: AsyncMock) -> None:
        """Default config creates HybridInjectionStrategy."""
        config = OntologyInjectionConfig()
        strategy = create_injection_strategy(config, mock_backend)
        assert isinstance(strategy, HybridInjectionStrategy)

    def test_custom_token_budget_forwarded(
        self,
        mock_backend: AsyncMock,
    ) -> None:
        """core_token_budget is forwarded to prompt-based strategies."""
        config = OntologyInjectionConfig(
            strategy=InjectionStrategy.PROMPT,
            core_token_budget=500,
        )
        strategy = create_injection_strategy(config, mock_backend)
        assert isinstance(strategy, PromptInjectionStrategy)
        assert strategy._core_token_budget == 500

    def test_custom_tool_name_forwarded(
        self,
        mock_backend: AsyncMock,
    ) -> None:
        """tool_name is forwarded to tool-based strategies."""
        config = OntologyInjectionConfig(
            strategy=InjectionStrategy.TOOL,
            tool_name="get_entity",
        )
        strategy = create_injection_strategy(config, mock_backend)
        assert isinstance(strategy, ToolBasedInjectionStrategy)
        assert strategy.tool.name == "get_entity"
