"""Tests for scripts/generate_comparison.py."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Import the script module dynamically since it's not a package
SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "generate_comparison.py"
_spec = importlib.util.spec_from_file_location("generate_comparison", SCRIPT_PATH)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


# -- Fixtures --


DIMS = [
    {"key": "memory", "label": "Memory", "description": "Mem"},
    {"key": "tool_use", "label": "Tool Use", "description": "Tools"},
    {"key": "org_structure", "label": "Org Structure", "description": ""},
    {"key": "multi_agent", "label": "Multi-Agent", "description": ""},
    {"key": "task_delegation", "label": "Task Delegation", "description": ""},
    {"key": "human_in_loop", "label": "HITL", "description": ""},
    {"key": "budget_tracking", "label": "Budget", "description": ""},
    {"key": "security_model", "label": "Security", "description": ""},
    {"key": "observability", "label": "Observability", "description": ""},
    {"key": "web_dashboard", "label": "Dashboard", "description": ""},
    {"key": "cli", "label": "CLI", "description": ""},
    {"key": "production_ready", "label": "Prod Ready", "description": ""},
    {"key": "workflow_types", "label": "Workflows", "description": ""},
    {"key": "template_system", "label": "Templates", "description": ""},
]

CATS = [{"key": "framework", "label": "Multi-Agent Framework"}]

COMP = {
    "name": "TestFramework",
    "slug": "test-framework",
    "url": "https://example.com",
    "description": "A test framework",
    "license": "MIT",
    "language": "Python",
    "category": "framework",
    "features": {
        "memory": {"support": "full", "note": "Built-in memory"},
        "tool_use": {"support": "partial", "note": "Limited tools"},
    },
}

MINIMAL_YAML = {
    "meta": {"last_updated": "2026-04-02"},
    "dimensions": DIMS,
    "categories": CATS,
    "competitors": [COMP],
}


@pytest.fixture
def minimal_yaml_file(tmp_path):
    """Write minimal valid YAML and patch DATA_FILE."""
    f = tmp_path / "competitors.yaml"
    f.write_text(yaml.dump(MINIMAL_YAML), encoding="utf-8")
    with patch.object(gen, "DATA_FILE", f):
        yield f


def _write_yaml(tmp_path, data, name="test.yaml"):
    f = tmp_path / name
    f.write_text(yaml.dump(data), encoding="utf-8")
    return f


# -- _load_data --


@pytest.mark.unit
class TestLoadData:
    """Tests for _load_data validation logic."""

    def test_valid_data(self, minimal_yaml_file):
        data = gen._load_data()
        assert data["meta"]["last_updated"] == "2026-04-02"
        assert len(data["competitors"]) == 1
        assert data["competitors"][0]["name"] == "TestFramework"

    def test_missing_file(self, tmp_path):
        with (
            patch.object(gen, "DATA_FILE", tmp_path / "nope.yaml"),
            pytest.raises(FileNotFoundError, match="Data file not found"),
        ):
            gen._load_data()

    def test_empty_yaml(self, tmp_path):
        f = _write_yaml(tmp_path, None, "empty.yaml")
        f.write_text("", encoding="utf-8")
        with (
            patch.object(gen, "DATA_FILE", f),
            pytest.raises(ValueError, match="empty or contains no data"),
        ):
            gen._load_data()

    def test_missing_top_level_keys(self, tmp_path):
        data = {"meta": {"last_updated": "2026-01-01"}}
        f = _write_yaml(tmp_path, data)
        with (
            patch.object(gen, "DATA_FILE", f),
            pytest.raises(ValueError, match="Missing top-level keys"),
        ):
            gen._load_data()

    def test_empty_competitors_list(self, tmp_path):
        data = {**MINIMAL_YAML, "competitors": []}
        f = _write_yaml(tmp_path, data)
        with (
            patch.object(gen, "DATA_FILE", f),
            pytest.raises(ValueError, match="No competitors found"),
        ):
            gen._load_data()

    def test_missing_last_updated(self, tmp_path):
        data = {**MINIMAL_YAML, "meta": {}}
        f = _write_yaml(tmp_path, data)
        with (
            patch.object(gen, "DATA_FILE", f),
            pytest.raises(ValueError, match=r"Missing meta\.last_updated"),
        ):
            gen._load_data()

    def test_competitor_missing_name(self, tmp_path):
        bad = {"slug": "x", "category": "framework"}
        data = {**MINIMAL_YAML, "competitors": [bad]}
        f = _write_yaml(tmp_path, data)
        with (
            patch.object(gen, "DATA_FILE", f),
            pytest.raises(ValueError, match=r"missing required keys.*name"),
        ):
            gen._load_data()

    def test_competitor_missing_slug(self, tmp_path):
        bad = {"name": "Test", "category": "framework"}
        data = {**MINIMAL_YAML, "competitors": [bad]}
        f = _write_yaml(tmp_path, data)
        with (
            patch.object(gen, "DATA_FILE", f),
            pytest.raises(ValueError, match=r"missing required keys.*slug"),
        ):
            gen._load_data()

    def test_competitor_not_a_mapping(self, tmp_path):
        data = {**MINIMAL_YAML, "competitors": ["not-a-dict"]}
        f = _write_yaml(tmp_path, data)
        with (
            patch.object(gen, "DATA_FILE", f),
            pytest.raises(TypeError, match="not a mapping"),
        ):
            gen._load_data()


# -- Helper functions --


HELPER_DIMS = [
    {"key": "memory", "label": "Memory"},
    {"key": "tool_use", "label": "Tool Use"},
]

HELPER_CATS = [
    {"key": "framework", "label": "Multi-Agent Framework"},
    {"key": "platform", "label": "Commercial Platform"},
]


@pytest.mark.unit
class TestHelpers:
    """Tests for helper functions."""

    def test_dimension_label_known(self):
        assert gen._dimension_label(HELPER_DIMS, "memory") == "Memory"

    def test_dimension_label_unknown(self, capsys):
        result = gen._dimension_label(HELPER_DIMS, "unknown_dim")
        assert result == "unknown_dim"
        assert "WARNING" in capsys.readouterr().err

    def test_category_label_known(self):
        label = gen._category_label(HELPER_CATS, "framework")
        assert label == "Multi-Agent Framework"

    def test_category_label_unknown(self, capsys):
        result = gen._category_label(HELPER_CATS, "unknown_cat")
        assert result == "unknown_cat"
        assert "WARNING" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("full", "\u2714"),
            ("partial", "~"),
            ("none", "-"),
            ("planned", "\u23f2"),
        ],
    )
    def test_support_icon_known(self, value, expected):
        assert gen._support_icon(value) == expected

    def test_support_icon_unknown(self, capsys):
        result = gen._support_icon("bogus")
        assert result == "bogus"
        assert "WARNING" in capsys.readouterr().err


# -- Markdown generation --


@pytest.mark.unit
class TestMarkdownGeneration:
    """Tests for Markdown output."""

    def test_generate_markdown_structure(self):
        markdown = gen._generate_markdown(MINIMAL_YAML)
        assert "# Framework Comparison" in markdown
        assert "## Organization & Coordination" in markdown
        assert "## Technical Capabilities" in markdown
        assert "## Operations & Tooling" in markdown
        assert "## Maturity" in markdown
        assert "## Project Links" in markdown

    def test_generate_markdown_contains_competitor(self):
        markdown = gen._generate_markdown(MINIMAL_YAML)
        assert "TestFramework" in markdown
        assert "example.com" in markdown
        assert "MIT" in markdown

    def test_frontmatter_contains_date(self):
        lines = gen._frontmatter_and_intro("2026-04-02")
        text = "\n".join(lines)
        assert "Last updated: 2026-04-02" in text

    def test_frontmatter_contains_legend(self):
        lines = gen._frontmatter_and_intro("2026-04-02")
        text = "\n".join(lines)
        assert "Full support" in text
        assert "Partial support" in text

    def test_competitor_row_with_url(self):
        row = gen._competitor_row(COMP, ["memory", "tool_use"], CATS)
        assert "[TestFramework](https://example.com)" in row
        assert "\u2714" in row  # full support for memory
        assert "~" in row  # partial support for tool_use

    def test_competitor_row_without_url(self):
        comp = {**COMP, "url": ""}
        row = gen._competitor_row(comp, ["memory"], CATS)
        assert "TestFramework" in row
        assert "[" not in row  # no link

    def test_competitor_row_synthorg_bold(self):
        comp = {**COMP, "is_synthorg": True}
        row = gen._competitor_row(comp, ["memory"], CATS)
        assert "**TestFramework**" in row

    def test_project_links(self):
        lines = gen._project_links(MINIMAL_YAML["competitors"])
        text = "\n".join(lines)
        assert "**TestFramework**" in text
        assert "[Website](https://example.com)" in text


# -- main() --


@pytest.mark.unit
class TestMain:
    """Tests for the main() entrypoint."""

    def test_main_success(self, tmp_path, minimal_yaml_file):
        out = tmp_path / "output.md"
        with (
            patch.object(gen, "OUTPUT_FILE", out),
            patch.object(gen, "REPO_ROOT", tmp_path),
        ):
            result = gen.main()
        assert result == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "# Framework Comparison" in content

    def test_main_missing_data_file(self, tmp_path):
        with (
            patch.object(gen, "DATA_FILE", tmp_path / "missing.yaml"),
            patch.object(gen, "OUTPUT_FILE", tmp_path / "out.md"),
        ):
            assert gen.main() == 1
