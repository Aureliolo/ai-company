"""Generate the framework comparison Markdown page from YAML data.

Used by CI (pages.yml, pages-preview.yml) to generate:
- ``docs/reference/comparison.md`` -- Markdown comparison tables

The same YAML data (``data/competitors.yaml``) is also consumed
directly by the Astro landing page (``site/src/pages/compare.astro``).

Run ``uv run python scripts/generate_comparison.py`` before
``uv run zensical build``.
"""

import sys
import traceback
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_ROOT / "data" / "competitors.yaml"
OUTPUT_FILE = REPO_ROOT / "docs" / "reference" / "comparison.md"

# Support value display symbols
SUPPORT_ICONS = {
    "full": "\u2714",  # checkmark
    "partial": "~",
    "none": "-",
    "planned": "\u23f2",  # timer clock
}

# Thematic groupings for splitting the table
TABLE_GROUPS = [
    {
        "title": "Organization & Coordination",
        "keys": ["org_structure", "multi_agent", "task_delegation", "human_in_loop"],
    },
    {
        "title": "Technical Capabilities",
        "keys": ["memory", "tool_use", "security_model", "workflow_types"],
    },
    {
        "title": "Operations & Tooling",
        "keys": ["budget_tracking", "observability", "web_dashboard", "cli"],
    },
    {
        "title": "Maturity",
        "keys": ["production_ready", "template_system"],
    },
]


def _load_data() -> dict:
    """Load and validate the competitors YAML file.

    Raises:
        FileNotFoundError: If the data file does not exist.
        ValueError: If the YAML is empty or missing required keys.
    """
    if not DATA_FILE.exists():
        msg = f"Data file not found: {DATA_FILE}"
        raise FileNotFoundError(msg)

    with DATA_FILE.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        msg = f"YAML file is empty or contains no data: {DATA_FILE}"
        raise ValueError(msg)

    required_keys = {"meta", "dimensions", "categories", "competitors"}
    missing = required_keys - set(data.keys())
    if missing:
        msg = f"Missing top-level keys in {DATA_FILE}: {missing}"
        raise ValueError(msg)

    if not data["competitors"]:
        msg = f"No competitors found in {DATA_FILE}"
        raise ValueError(msg)

    if "last_updated" not in data.get("meta", {}):
        msg = f"Missing meta.last_updated in {DATA_FILE}"
        raise ValueError(msg)

    return data


def _dimension_label(dimensions: list[dict], key: str) -> str:
    """Get the display label for a dimension key."""
    for dim in dimensions:
        if dim["key"] == key:
            return dim["label"]
    return key


def _support_icon(value: str) -> str:
    """Convert a support value to its display symbol."""
    return SUPPORT_ICONS.get(value, value)


def _category_label(categories: list[dict], key: str) -> str:
    """Get the display label for a category key."""
    for cat in categories:
        if cat["key"] == key:
            return cat["label"]
    return key


def _frontmatter_and_intro(last_updated: str) -> list[str]:
    """Generate the frontmatter, title, legend, and intro callout."""
    return [
        "---",
        "title: Framework Comparison",
        "description: >-",
        "  How SynthOrg compares to every notable agent orchestration",
        "  framework, platform, and research project.",
        "---",
        "",
        "<!-- Generated from data/competitors.yaml"
        " by scripts/generate_comparison.py --"
        " do not edit directly -->",
        "",
        "# Framework Comparison",
        "",
        "How SynthOrg compares to agent orchestration frameworks,"
        " platforms, and research projects.",
        "",
        f"Last updated: {last_updated}",
        "",
        "**Legend:**",
        f"{SUPPORT_ICONS['full']} Full support"
        f" | ~ Partial support"
        f" | {SUPPORT_ICONS['none']} Not supported"
        f" | {SUPPORT_ICONS['planned']} Planned",
        "",
        '!!! tip "Interactive Version"',
        "    For a filterable, sortable version of this comparison,"
        " visit the [interactive comparison page](https://synthorg.io/compare/).",
        "",
    ]


def _competitor_row(
    comp: dict,
    group_keys: list[str],
    categories: list[dict],
) -> str:
    """Build a single Markdown table row for a competitor."""
    name = comp["name"]
    url = comp.get("url", "")
    if url:
        name_cell = (
            f"[**{name}**]({url})" if comp.get("is_synthorg") else f"[{name}]({url})"
        )
    else:
        name_cell = f"**{name}**" if comp.get("is_synthorg") else name

    cat_label = _category_label(categories, comp.get("category", ""))
    license_val = comp.get("license", "")
    features = comp.get("features", {})

    dim_cells = []
    for key in group_keys:
        feat = features.get(key, {})
        support = feat.get("support", "none") if isinstance(feat, dict) else "none"
        dim_cells.append(_support_icon(support))

    return (
        f"| {name_cell} | {cat_label} | {license_val} | " + " | ".join(dim_cells) + " |"
    )


def _thematic_tables(
    dimensions: list[dict],
    categories: list[dict],
    competitors: list[dict],
) -> list[str]:
    """Generate the thematic comparison tables."""
    lines: list[str] = []
    for group in TABLE_GROUPS:
        lines.append(f"## {group['title']}")
        lines.append("")

        dim_headers = [_dimension_label(dimensions, k) for k in group["keys"]]
        header = "| Framework | Category | License | " + " | ".join(dim_headers) + " |"
        separator = (
            "|:----------|:---------|:--------|"
            + "|".join([":---:" for _ in group["keys"]])
            + "|"
        )
        lines.append(header)
        lines.append(separator)

        lines.extend(
            _competitor_row(comp, group["keys"], categories) for comp in competitors
        )
        lines.append("")
    return lines


def _project_links(competitors: list[dict]) -> list[str]:
    """Generate the project links section."""
    lines = ["## Project Links", ""]
    for comp in competitors:
        name = comp["name"]
        url = comp.get("url", "")
        repo = comp.get("repo", "")
        parts = [f"**{name}**"]
        if url:
            parts.append(f"[Website]({url})")
        if repo:
            parts.append(f"[Repository]({repo})")
        lines.append(f"- {' -- '.join(parts)}")
    lines.append("")
    return lines


def _generate_markdown(data: dict) -> str:
    """Generate the full Markdown page from the structured data."""
    lines: list[str] = []
    lines.extend(_frontmatter_and_intro(data["meta"]["last_updated"]))
    lines.extend(
        _thematic_tables(data["dimensions"], data["categories"], data["competitors"])
    )
    lines.extend(_project_links(data["competitors"]))
    return "\n".join(lines)


def main() -> int:
    """Load YAML data and generate the comparison Markdown page."""
    try:
        data = _load_data()
        markdown = _generate_markdown(data)
    except Exception as exc:
        print("Failed to generate comparison page:", file=sys.stderr)
        traceback.print_exception(exc)
        return 1

    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(markdown, encoding="utf-8")
        print(f"Wrote comparison page to {OUTPUT_FILE.relative_to(REPO_ROOT)}")
    except OSError as exc:
        print("Failed to write output file:", file=sys.stderr)
        traceback.print_exception(exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
