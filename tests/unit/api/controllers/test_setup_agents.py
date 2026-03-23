"""Tests for expand_template_agents dict-model handling."""

from typing import Any

import pytest

from synthorg.api.controllers.setup_agents import expand_template_agents
from synthorg.core.enums import CompanyType
from synthorg.templates.schema import (
    CompanyTemplate,
    TemplateAgentConfig,
    TemplateMetadata,
)


def _make_template(agents: list[dict[str, Any]]) -> CompanyTemplate:
    """Build a minimal CompanyTemplate with the given agent configs."""
    agent_cfgs = tuple(TemplateAgentConfig(**a) for a in agents)
    return CompanyTemplate(
        metadata=TemplateMetadata(
            name="test-template",
            company_type=CompanyType.CUSTOM,
        ),
        agents=agent_cfgs,
    )


@pytest.mark.unit
class TestExpandTemplateAgentsDictModel:
    def test_dict_model_produces_model_requirement(self) -> None:
        """Dict model in template populates model_requirement in output."""
        template = _make_template(
            [
                {
                    "role": "CEO",
                    "model": {
                        "tier": "large",
                        "priority": "quality",
                        "min_context": 100_000,
                    },
                },
            ]
        )
        agents = expand_template_agents(template)
        assert len(agents) == 1
        agent = agents[0]
        assert agent["tier"] == "large"
        assert "model_requirement" in agent
        req = agent["model_requirement"]
        assert req["tier"] == "large"
        assert req["priority"] == "quality"
        assert req["min_context"] == 100_000

    def test_string_model_has_no_model_requirement(self) -> None:
        """String model in template does not produce model_requirement."""
        template = _make_template(
            [
                {"role": "Developer", "model": "medium"},
            ]
        )
        agents = expand_template_agents(template)
        assert len(agents) == 1
        agent = agents[0]
        assert agent["tier"] == "medium"
        assert "model_requirement" not in agent

    def test_mixed_models_in_same_template(self) -> None:
        """Dict and string models coexist in the same template."""
        template = _make_template(
            [
                {
                    "role": "CEO",
                    "model": {"tier": "large", "priority": "quality"},
                },
                {"role": "Developer", "model": "small"},
            ]
        )
        agents = expand_template_agents(template)
        assert len(agents) == 2

        ceo = next(a for a in agents if a["role"] == "CEO")
        dev = next(a for a in agents if a["role"] == "Developer")

        assert "model_requirement" in ceo
        assert ceo["tier"] == "large"
        assert "model_requirement" not in dev
        assert dev["tier"] == "small"

    def test_dict_model_empty_uses_defaults(self) -> None:
        """Empty dict model produces defaults in model_requirement."""
        template = _make_template(
            [
                {"role": "Dev", "model": {}},
            ]
        )
        agents = expand_template_agents(template)
        assert len(agents) == 1
        agent = agents[0]
        assert agent["tier"] == "medium"
        assert "model_requirement" in agent
        assert agent["model_requirement"]["tier"] == "medium"
        assert agent["model_requirement"]["priority"] == "balanced"
