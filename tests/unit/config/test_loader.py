"""Tests for config loader (parsing, merging, validation)."""

from pathlib import Path

import pytest

from ai_company.config.errors import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)
from ai_company.config.loader import (
    _build_line_map,
    _deep_merge,
    _parse_yaml_file,
    _parse_yaml_string,
    _read_config_text,
    _substitute_env_vars,
    _validate_config_dict,
    discover_config,
    load_config,
    load_config_from_string,
)
from ai_company.config.schema import RootConfig

from .conftest import (
    ENV_VAR_MISSING_YAML,
    ENV_VAR_NESTED_YAML,
    ENV_VAR_SIMPLE_YAML,
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

    def test_result_does_not_share_mutable_refs_with_base(self):
        base = {"x": {"nested": [1, 2, 3]}}
        result = _deep_merge(base, {})
        result["x"]["nested"].append(4)
        assert base["x"]["nested"] == [1, 2, 3]

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_empty_override(self):
        result = _deep_merge({"a": 1}, {})
        assert result == {"a": 1}


# ── _read_config_text ────────────────────────────────────────────


@pytest.mark.unit
class TestReadConfigText:
    def test_reads_file(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("company_name: Test\n", encoding="utf-8")
        assert _read_config_text(f) == "company_name: Test\n"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ConfigFileNotFoundError, match="not found"):
            _read_config_text(tmp_path / "missing.yaml")

    def test_directory_rejected(self, tmp_path):
        with pytest.raises(ConfigFileNotFoundError, match="not found"):
            _read_config_text(tmp_path)

    def test_os_error_wrapped(self, tmp_path, monkeypatch):
        f = tmp_path / "config.yaml"
        f.write_text("content", encoding="utf-8")
        monkeypatch.setattr(
            "pathlib.Path.read_text",
            lambda *a, **kw: (_ for _ in ()).throw(PermissionError("denied")),
        )
        with pytest.raises(ConfigParseError, match="Unable to read"):
            _read_config_text(f)


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


# ── _build_line_map / _walk_node ─────────────────────────────────


@pytest.mark.unit
class TestBuildLineMap:
    def test_simple_mapping(self):
        yaml_text = "company_name: Test\nbudget:\n  total_monthly: 100\n"
        result = _build_line_map(yaml_text)
        assert "company_name" in result
        assert "budget" in result
        assert "budget.total_monthly" in result
        assert result["company_name"][0] == 1
        assert result["budget.total_monthly"][0] == 3

    def test_sequence_elements(self):
        yaml_text = "agents:\n  - name: Alice\n  - name: Bob\n"
        result = _build_line_map(yaml_text)
        assert "agents.0" in result
        assert "agents.1" in result
        assert "agents.0.name" in result

    def test_invalid_yaml_returns_empty(self):
        result = _build_line_map("invalid: [unterminated\n")
        assert result == {}

    def test_non_mapping_root_returns_empty(self):
        result = _build_line_map("- item1\n- item2\n")
        assert result == {}

    def test_empty_string_returns_empty(self):
        result = _build_line_map("")
        assert result == {}

    def test_null_yaml_returns_empty(self):
        result = _build_line_map("null\n")
        assert result == {}


# ── _validate_config_dict ────────────────────────────────────────


@pytest.mark.unit
class TestValidateConfigDict:
    def test_valid_dict(self):
        data = {"company_name": "Test Corp"}
        result = _validate_config_dict(data)
        assert isinstance(result, RootConfig)
        assert result.company_name == "Test Corp"

    def test_invalid_dict_raises(self):
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_config_dict({"company_name": ""})
        assert exc_info.value.field_errors

    def test_line_map_enriches_errors(self):
        line_map = {"company_name": (5, 16)}
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_config_dict(
                {"company_name": ""},
                source_file="test.yaml",
                line_map=line_map,
            )
        err = exc_info.value
        loc = next(
            loc
            for loc in err.locations
            if loc.key_path and "company_name" in loc.key_path
        )
        assert loc.file_path == "test.yaml"
        assert loc.line == 5
        assert loc.column == 16

    def test_none_line_map_gracefully_degrades(self):
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_config_dict(
                {"company_name": ""},
                source_file="test.yaml",
                line_map=None,
            )
        err = exc_info.value
        assert err.field_errors
        for loc in err.locations:
            assert loc.line is None
            assert loc.column is None


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

    def test_multiple_override_files_applied_in_order(self, tmp_config_file):
        base = tmp_config_file("company_name: Base\n", name="base.yaml")
        over1 = tmp_config_file("company_name: Override1\n", name="over1.yaml")
        over2 = tmp_config_file("company_name: Override2\n", name="over2.yaml")
        cfg = load_config(base, override_paths=(over1, over2))
        assert cfg.company_name == "Override2"

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

    def test_directory_path_rejected(self, tmp_path):
        with pytest.raises(ConfigFileNotFoundError):
            load_config(tmp_path)


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


# ── _substitute_env_vars ────────────────────────────────────────


@pytest.mark.unit
class TestSubstituteEnvVars:
    def test_simple_substitution(self, monkeypatch):
        monkeypatch.setenv("FOO", "bar")
        data = {"key": "${FOO}"}
        result = _substitute_env_vars(data)
        assert result == {"key": "bar"}

    def test_missing_var_raises(self):
        data = {"key": "${MISSING_VAR_XYZ}"}
        with pytest.raises(ConfigValidationError, match="MISSING_VAR_XYZ"):
            _substitute_env_vars(data)

    def test_default_used_when_missing(self):
        data = {"key": "${MISSING_VAR_XYZ:-fallback}"}
        result = _substitute_env_vars(data)
        assert result == {"key": "fallback"}

    def test_default_ignored_when_present(self, monkeypatch):
        monkeypatch.setenv("SET_VAR", "real")
        data = {"key": "${SET_VAR:-fallback}"}
        result = _substitute_env_vars(data)
        assert result == {"key": "real"}

    def test_empty_default(self):
        data = {"key": "${MISSING_VAR_XYZ:-}"}
        result = _substitute_env_vars(data)
        assert result == {"key": ""}

    def test_nested_dict(self, monkeypatch):
        monkeypatch.setenv("INNER", "resolved")
        data = {"outer": {"inner": "${INNER}"}}
        result = _substitute_env_vars(data)
        assert result == {"outer": {"inner": "resolved"}}

    def test_list_values(self, monkeypatch):
        monkeypatch.setenv("ITEM", "hello")
        data = {"items": ["${ITEM}", "static"]}
        result = _substitute_env_vars(data)
        assert result == {"items": ["hello", "static"]}

    def test_non_string_unchanged(self):
        data = {"int": 42, "float": 3.14, "bool": True, "null": None}
        result = _substitute_env_vars(data)
        assert result == {"int": 42, "float": 3.14, "bool": True, "null": None}

    def test_multiple_vars_in_one_string(self, monkeypatch):
        monkeypatch.setenv("A", "alpha")
        monkeypatch.setenv("B", "beta")
        data = {"key": "${A}:${B}"}
        result = _substitute_env_vars(data)
        assert result == {"key": "alpha:beta"}

    def test_partial_string(self, monkeypatch):
        monkeypatch.setenv("VAR", "middle")
        data = {"key": "prefix-${VAR}-suffix"}
        result = _substitute_env_vars(data)
        assert result == {"key": "prefix-middle-suffix"}

    def test_input_not_mutated(self, monkeypatch):
        monkeypatch.setenv("X", "replaced")
        original = {"key": "${X}", "nested": {"deep": "${X}"}}
        original_copy = {"key": "${X}", "nested": {"deep": "${X}"}}
        _substitute_env_vars(original)
        assert original == original_copy

    def test_no_placeholders_passthrough(self):
        data = {"key": "no vars here", "num": 123}
        result = _substitute_env_vars(data)
        assert result == {"key": "no vars here", "num": 123}

    def test_deeply_nested(self, monkeypatch):
        monkeypatch.setenv("DEEP", "found")
        data = {"a": {"b": {"c": {"d": {"e": "${DEEP}"}}}}}
        result = _substitute_env_vars(data)
        assert result == {"a": {"b": {"c": {"d": {"e": "found"}}}}}


# ── discover_config ─────────────────────────────────────────────


@pytest.mark.unit
class TestDiscoverConfig:
    def test_finds_cwd_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "ai-company.yaml"
        config_file.write_text("company_name: Test\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = discover_config()
        assert result == config_file.resolve()

    def test_finds_config_subdir(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "ai-company.yaml"
        config_file.write_text("company_name: Test\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = discover_config()
        assert result == config_file.resolve()

    def test_finds_home_config(self, tmp_path, monkeypatch):
        # CWD has no config
        monkeypatch.chdir(tmp_path)
        # Home dir has config
        fake_home = tmp_path / "fakehome"
        config_dir = fake_home / ".ai-company"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.yaml"
        config_file.write_text("company_name: Test\n", encoding="utf-8")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
        result = discover_config()
        assert result == config_file.resolve()

    def test_precedence_cwd_over_subdir(self, tmp_path, monkeypatch):
        # Both CWD and config/ have files
        cwd_file = tmp_path / "ai-company.yaml"
        cwd_file.write_text("company_name: CWD\n", encoding="utf-8")
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        subdir_file = config_dir / "ai-company.yaml"
        subdir_file.write_text("company_name: SubDir\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = discover_config()
        assert result == cwd_file.resolve()

    def test_precedence_subdir_over_home(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # config/ subdir has file
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        subdir_file = config_dir / "ai-company.yaml"
        subdir_file.write_text("company_name: SubDir\n", encoding="utf-8")
        # Home dir has file
        fake_home = tmp_path / "fakehome"
        home_config_dir = fake_home / ".ai-company"
        home_config_dir.mkdir(parents=True)
        home_file = home_config_dir / "config.yaml"
        home_file.write_text("company_name: Home\n", encoding="utf-8")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
        result = discover_config()
        assert result == subdir_file.resolve()

    def test_no_config_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
        with pytest.raises(ConfigFileNotFoundError, match="No configuration file"):
            discover_config()

    def test_returns_resolved_path(self, tmp_path, monkeypatch):
        config_file = tmp_path / "ai-company.yaml"
        config_file.write_text("company_name: Test\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = discover_config()
        assert result.is_absolute()


# ── Integration: env var substitution through load_config ───────


@pytest.mark.unit
class TestLoadConfigEnvVarIntegration:
    def test_env_var_in_load_config(self, tmp_config_file, monkeypatch):
        monkeypatch.setenv("COMPANY_NAME", "Env Corp")
        path = tmp_config_file(ENV_VAR_SIMPLE_YAML)
        cfg = load_config(path)
        assert cfg.company_name == "Env Corp"

    def test_env_var_with_default_in_load_config(self, tmp_config_file):
        yaml_content = "company_name: ${UNDEFINED_TEST_VAR:-Default Corp}\n"
        path = tmp_config_file(yaml_content)
        cfg = load_config(path)
        assert cfg.company_name == "Default Corp"

    def test_missing_env_var_raises_in_load_config(self, tmp_config_file):
        path = tmp_config_file(ENV_VAR_MISSING_YAML)
        with pytest.raises(ConfigValidationError, match="UNDEFINED_VAR"):
            load_config(path)

    def test_env_var_in_nested_config(self, tmp_config_file, monkeypatch):
        monkeypatch.setenv("COMPANY_NAME", "Nested Corp")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://custom.api")
        path = tmp_config_file(ENV_VAR_NESTED_YAML)
        cfg = load_config(path)
        assert cfg.company_name == "Nested Corp"
        assert cfg.providers["anthropic"].base_url == "https://custom.api"

    def test_env_var_in_load_config_from_string(self, monkeypatch):
        monkeypatch.setenv("COMPANY_NAME", "String Corp")
        cfg = load_config_from_string(ENV_VAR_SIMPLE_YAML)
        assert cfg.company_name == "String Corp"

    def test_env_var_default_in_load_config_from_string(self):
        yaml_content = "company_name: ${UNDEFINED_TEST_VAR:-FromString Corp}\n"
        cfg = load_config_from_string(yaml_content)
        assert cfg.company_name == "FromString Corp"

    def test_missing_env_var_raises_in_load_config_from_string(self):
        with pytest.raises(ConfigValidationError, match="UNDEFINED_VAR"):
            load_config_from_string(ENV_VAR_MISSING_YAML)

    def test_env_var_in_override_file(self, tmp_config_file, monkeypatch):
        monkeypatch.setenv("OVERRIDE_NAME", "Override Corp")
        base = tmp_config_file(MINIMAL_VALID_YAML, name="base.yaml")
        override = tmp_config_file(
            "company_name: ${OVERRIDE_NAME}\n",
            name="override.yaml",
        )
        cfg = load_config(base, override_paths=(override,))
        assert cfg.company_name == "Override Corp"


# ── Integration: discover_config with load_config ───────────────


@pytest.mark.unit
class TestLoadConfigDiscoveryIntegration:
    def test_load_config_none_uses_discovery(self, tmp_path, monkeypatch):
        config_file = tmp_path / "ai-company.yaml"
        config_file.write_text(MINIMAL_VALID_YAML, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        cfg = load_config(None)
        assert cfg.company_name == "Test Corp"

    def test_load_config_none_no_config_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
        with pytest.raises(ConfigFileNotFoundError):
            load_config(None)

    def test_load_config_explicit_path_still_works(self, tmp_config_file):
        """Backward compatibility: explicit path still works as before."""
        path = tmp_config_file(MINIMAL_VALID_YAML)
        cfg = load_config(path)
        assert cfg.company_name == "Test Corp"
