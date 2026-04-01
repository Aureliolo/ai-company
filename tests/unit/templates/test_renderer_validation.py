"""Tests for validate_preset_references pre-flight validation."""

from typing import Any

import pytest

from synthorg.core.enums import CompanyType
from synthorg.templates.renderer import validate_preset_references
from synthorg.templates.schema import (
    CompanyTemplate,
    TemplateAgentConfig,
    TemplateMetadata,
)


def _make_template(
    agents: list[dict[str, Any]],
) -> CompanyTemplate:
    agent_cfgs = tuple(TemplateAgentConfig(**a) for a in agents)
    return CompanyTemplate(
        metadata=TemplateMetadata(
            name="Validation Test",
            company_type=CompanyType.CUSTOM,
        ),
        agents=agent_cfgs,
    )


@pytest.mark.unit
class TestValidatePresetReferences:
    def test_no_warnings_for_builtin_presets(self) -> None:
        template = _make_template(
            [
                {"role": "CEO", "personality_preset": "visionary_leader"},
                {"role": "Dev", "personality_preset": "pragmatic_builder"},
            ]
        )
        warnings = validate_preset_references(template)
        assert warnings == ()

    def test_no_warnings_when_no_presets(self) -> None:
        template = _make_template([{"role": "Dev"}])
        warnings = validate_preset_references(template)
        assert warnings == ()

    def test_warning_for_unknown_preset(self) -> None:
        template = _make_template(
            [{"role": "Dev", "personality_preset": "totally_unknown"}]
        )
        warnings = validate_preset_references(template)
        assert len(warnings) == 1
        assert "totally_unknown" in warnings[0]
        assert "Dev" in warnings[0]

    def test_no_warning_for_custom_preset(self) -> None:
        custom = {
            "my_custom": {
                "traits": ("a",),
                "communication_style": "test",
            },
        }
        template = _make_template([{"role": "Dev", "personality_preset": "my_custom"}])
        warnings = validate_preset_references(
            template,
            custom_presets=custom,
        )
        assert warnings == ()

    def test_multiple_unknown_presets(self) -> None:
        template = _make_template(
            [
                {"role": "CEO", "personality_preset": "unknown_a"},
                {"role": "Dev", "personality_preset": "unknown_b"},
                {"role": "QA", "personality_preset": "visionary_leader"},
            ]
        )
        warnings = validate_preset_references(template)
        assert len(warnings) == 2
        names = " ".join(warnings)
        assert "unknown_a" in names
        assert "unknown_b" in names

    def test_case_insensitive_validation(self) -> None:
        template = _make_template(
            [
                {"role": "CEO", "personality_preset": "VISIONARY_LEADER"},
            ]
        )
        warnings = validate_preset_references(template)
        assert warnings == ()

    def test_returns_tuple(self) -> None:
        template = _make_template([{"role": "Dev"}])
        result = validate_preset_references(template)
        assert isinstance(result, tuple)
