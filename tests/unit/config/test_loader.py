"""Tests for config loader (parsing, merging, validation)."""

import pytest

from ai_company.config.errors import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)
from ai_company.config.loader import (
    _deep_merge,
    _parse_yaml_file,
    _parse_yaml_string,
    load_config,
    load_config_from_string,
)
from ai_company.config.schema import RootConfig

from .conftest import (
    FULL_VALID_YAML,
    INVALID_FIELD_VALUES_YAML,
    INVALID_SYNTAX_YAML,
    MINIMAL_VALID_YAML,
    MISSING_REQUIRED_YAML,
)

# ── _deep_merge ──────────────────────────────────────────────────


@pytest.mark.unit
class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3, "c": 4}}
        result = _deep_merge(base, override)
        assert result == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_list_replaced_entirely(self):
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = _deep_merge(base, override)
        assert result == {"items": [4, 5]}

    def test_base_preserved(self):
        base = {"a": 1, "b": 2}
        override = {"c": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_new_keys_added(self):
        base = {"a": 1}
        override = {"b": 2, "c": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_inputs_not_mutated(self):
        base = {"x": {"a": 1}}
        override = {"x": {"b": 2}}
        base_copy = {"x": {"a": 1}}
        override_copy = {"x": {"b": 2}}
        _deep_merge(base, override)
        assert base == base_copy
        assert override == override_copy

    def test_deeply_nested(self):
        base = {"a": {"b": {"c": 1}}}
        override = {"a": {"b": {"d": 2}}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": {"c": 1, "d": 2}}}


# ── _parse_yaml_file ─────────────────────────────────────────────


@pytest.mark.unit
class TestParseYamlFile:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("company_name: Test\n", encoding="utf-8")
        result = _parse_yaml_file(f)
        assert result == {"company_name": "Test"}

    def test_syntax_error(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(INVALID_SYNTAX_YAML, encoding="utf-8")
        with pytest.raises(ConfigParseError, match="YAML syntax error"):
            _parse_yaml_file(f)

    def test_non_mapping_top_level(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ConfigParseError, match="mapping"):
            _parse_yaml_file(f)

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        assert _parse_yaml_file(f) == {}

    def test_null_file(self, tmp_path):
        f = tmp_path / "null.yaml"
        f.write_text("null\n", encoding="utf-8")
        assert _parse_yaml_file(f) == {}

    def test_file_not_found(self, tmp_path):
        f = tmp_path / "missing.yaml"
        with pytest.raises(ConfigFileNotFoundError, match="not found"):
            _parse_yaml_file(f)


# ── _parse_yaml_string ───────────────────────────────────────────


@pytest.mark.unit
class TestParseYamlString:
    def test_valid_string(self):
        result = _parse_yaml_string("key: value\n", "<test>")
        assert result == {"key": "value"}

    def test_syntax_error(self):
        with pytest.raises(ConfigParseError, match="syntax error"):
            _parse_yaml_string(INVALID_SYNTAX_YAML, "<test>")

    def test_empty_string(self):
        assert _parse_yaml_string("", "<test>") == {}

    def test_non_mapping(self):
        with pytest.raises(ConfigParseError, match="mapping"):
            _parse_yaml_string("- a\n- b\n", "<test>")


# ── load_config ──────────────────────────────────────────────────


@pytest.mark.unit
class TestLoadConfig:
    def test_explicit_path(self, tmp_config_file):
        path = tmp_config_file(MINIMAL_VALID_YAML)
        cfg = load_config(path)
        assert isinstance(cfg, RootConfig)
        assert cfg.company_name == "Test Corp"

    def test_full_config(self, tmp_config_file):
        path = tmp_config_file(FULL_VALID_YAML)
        cfg = load_config(path)
        assert cfg.company_name == "Test Corp"
        assert len(cfg.agents) == 1
        assert cfg.agents[0].name == "Alice"
        assert "anthropic" in cfg.providers

    def test_layered_override(self, tmp_config_file):
        base_path = tmp_config_file(
            "company_name: Base Corp\ncompany_type: custom\n",
            name="base.yaml",
        )
        override_path = tmp_config_file(
            "company_name: Override Corp\n",
            name="override.yaml",
        )
        cfg = load_config(base_path, override_paths=(override_path,))
        assert cfg.company_name == "Override Corp"

    def test_defaults_applied(self, tmp_config_file):
        path = tmp_config_file(MINIMAL_VALID_YAML)
        cfg = load_config(path)
        assert cfg.budget.total_monthly == 100.0
        assert cfg.routing.strategy == "cost_aware"

    def test_validation_error_with_location(self, tmp_config_file):
        path = tmp_config_file(MISSING_REQUIRED_YAML)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(path)
        err = exc_info.value
        assert err.field_errors
        assert any("company_name" in key for key, _ in err.field_errors)

    def test_frozen_result(self, tmp_config_file):
        from pydantic import ValidationError

        path = tmp_config_file(MINIMAL_VALID_YAML)
        cfg = load_config(path)
        with pytest.raises(ValidationError):
            cfg.company_name = "Nope"  # type: ignore[misc]

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ConfigFileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_syntax_error(self, tmp_config_file):
        path = tmp_config_file(INVALID_SYNTAX_YAML)
        with pytest.raises(ConfigParseError):
            load_config(path)

    def test_nested_override_merge(self, tmp_config_file):
        base_path = tmp_config_file(
            "company_name: X\nbudget:\n  total_monthly: 200.0\n",
            name="base.yaml",
        )
        override_path = tmp_config_file(
            "budget:\n  per_task_limit: 10.0\n",
            name="override.yaml",
        )
        cfg = load_config(base_path, override_paths=(override_path,))
        assert cfg.budget.total_monthly == 200.0
        assert cfg.budget.per_task_limit == 10.0


# ── load_config_from_string ──────────────────────────────────────


@pytest.mark.unit
class TestLoadConfigFromString:
    def test_minimal(self):
        cfg = load_config_from_string(MINIMAL_VALID_YAML)
        assert cfg.company_name == "Test Corp"
        assert isinstance(cfg, RootConfig)

    def test_full(self):
        cfg = load_config_from_string(FULL_VALID_YAML)
        assert cfg.company_name == "Test Corp"
        assert len(cfg.agents) == 1
        assert cfg.budget.total_monthly == 500.0

    def test_invalid_yaml(self):
        with pytest.raises(ConfigParseError):
            load_config_from_string(INVALID_SYNTAX_YAML)

    def test_validation_error(self):
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config_from_string(INVALID_FIELD_VALUES_YAML)
        assert exc_info.value.field_errors

    def test_defaults_merged(self):
        cfg = load_config_from_string(MINIMAL_VALID_YAML)
        assert cfg.budget.total_monthly == 100.0

    def test_custom_source_name(self):
        with pytest.raises(ConfigParseError, match="my-source"):
            load_config_from_string(
                INVALID_SYNTAX_YAML,
                source_name="my-source",
            )

    def test_empty_string_uses_defaults(self):
        cfg = load_config_from_string("")
        assert cfg.company_name == "AI Company"
