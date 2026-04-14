"""Design system validation for web dashboard files.

Checks web/src/ files for design system violations and proposes shared
building blocks when duplicate patterns are detected. Runs as a
PostToolUse hook on Edit/Write operations targeting web/src/ files.

When invoked as a hook, reads JSON from stdin with the tool input.
Also supports direct CLI invocation for testing.

Exit codes:
    0 -- no issues found, file not in web/src/, or file could not be read
         (warnings printed to stderr for read/parse failures)
    1 -- violations found (prints warnings to stdout)

Usage (hook mode -- reads JSON from stdin):
    echo '{"tool_input":{"file_path":"web/src/pages/Foo.tsx"}}' |
        python scripts/check_web_design_system.py

Usage (CLI mode -- for testing):
    python scripts/check_web_design_system.py <file_path> [--project-root <root>]
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ── Thresholds ────────────────────────────────────────────────────────
_SHORT_HEX_LEN = 4  # #rgb (3 digits + hash)
_SHORT_HEX_ALPHA_LEN = 5  # #rgba (4 digits + hash)
_LONG_HEX_ALPHA_LEN = 9  # #rrggbbaa (8 digits + hash)
_MIN_PATH_DEPTH = 2  # web/<something>
_MAP_BLOCK_COMPLEXITY = 8  # lines in .map() before suggesting extraction
_REPEATED_PATTERN_MIN = 3  # icon+text rows before suggesting DataRow

# ── Allowed raw hex values ────────────────────────────────────────────
# Must match :root variables in web/src/styles/design-tokens.css.
# Any OTHER hex color in a .tsx/.ts/.css file is a violation.
ALLOWED_HEX_COLORS: set[str] = {
    "#38bdf8",
    "#0ea5e9",  # accent, accent-dim
    "#10b981",  # success
    "#f59e0b",  # warning
    "#ef4444",  # danger
    "#e2e8f0",
    "#94a3b8",
    "#8b95a5",  # text-primary, text-secondary, text-muted
    "#0a0a12",
    "#0f0f1a",
    "#13131f",
    "#181828",  # bg-base, bg-surface, bg-card, bg-card-hover
    "#1e1e2e",
    "#2a2a3e",  # border, border-bright
}

# ── Patterns that should use design tokens ────────────────────────────
HARDCODED_COLOR_RE = re.compile(
    r"""(?x)
    (?:
        # Tailwind arbitrary color values: text-[#abc], bg-[#abc123]
        (?:text|bg|border|fill|stroke|ring|shadow|outline|from|to|via)
        -\[(?P<tw_hex>\#[0-9a-fA-F]{3,8})\]
    )
    |
    (?:
        # CSS color properties with hex values
        (?:color|background(?:-color)?|border(?:-color)?|fill|stroke|outline-color)
        \s*:\s*(?P<css_hex>\#[0-9a-fA-F]{3,8})
    )
    |
    (?:
        # Inline style hex colors in JSX: style={{ color: '#abc' }}
        (?:color|backgroundColor|borderColor|fill|stroke)
        \s*:\s*['"](?P<jsx_hex>\#[0-9a-fA-F]{3,8})['"]
    )
    """,
)

HARDCODED_RGBA_RE = re.compile(
    r"\brgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+",
)

HARDCODED_FONT_RE = re.compile(
    r"""(?x)
    font-family\s*:\s*(?!\s*var\()
    |
    fontFamily\s*:\s*['"](?!\s*var\()
    """,
)

# Motion inline transition durations (should use lib/motion presets).
# Uses re.DOTALL so [^}]* spans newlines in multiline transition objects.
HARDCODED_MOTION_DURATION_RE = re.compile(
    r"""(?x)
    # Variant object exit/animate transitions: exit: { ..., transition: { duration: N } }
    transition\s*:\s*\{[^}]*\bduration\s*:\s*[\d.]+
    |
    # Inline transition prop: transition={{ duration: N }}
    transition\s*=\s*\{\s*\{[^}]*\bduration\s*:\s*[\d.]+
    """,
    re.DOTALL,
)

# Files where inline Motion durations are intentional (relative paths).
_MOTION_DURATION_SKIP_PATHS: set[str] = {
    "web/src/lib/motion.ts",
    "web/src/hooks/useAnimationPreset.ts",
    "web/src/pages/setup/ThemePreview.tsx",
}

# ── Files to skip ────────────────────────────────────────────────────
_SKIP_PATHS: set[str] = {"design-tokens.css", "global.css"}
_SKIP_DIRS: set[str] = {"__tests__", "node_modules", ".storybook"}
_COMMENT_PREFIXES = ("//", "/*", "*")

# Regex to strip block comments (/* ... */) so full-content regex scans skip them.
_BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")


def _normalize_hex(h: str) -> str:
    """Normalize hex color to lowercase 6-digit form, stripping alpha."""
    h = h.lower()
    if len(h) == _SHORT_HEX_LEN:  # #rgb -> #rrggbb
        return f"#{h[1] * 2}{h[2] * 2}{h[3] * 2}"
    if len(h) == _SHORT_HEX_ALPHA_LEN:  # #rgba -> #rrggbb (drop alpha)
        return f"#{h[1] * 2}{h[2] * 2}{h[3] * 2}"
    if len(h) == _LONG_HEX_ALPHA_LEN:  # #rrggbbaa -> #rrggbb (drop alpha)
        return h[:7]
    return h


def _is_allowed_file(file_path: Path, project_root: Path) -> bool:
    """Check if the file should be validated."""
    if not file_path.is_relative_to(project_root):
        return False
    rel = file_path.relative_to(project_root)
    parts = rel.parts

    if file_path.name in _SKIP_PATHS:
        return False
    if any(skip_dir in parts for skip_dir in _SKIP_DIRS):
        return False
    if not (len(parts) >= _MIN_PATH_DEPTH and parts[0] == "web"):
        return False
    return file_path.suffix in {".tsx", ".ts", ".css"}


def _is_in_comment_context(line: str, match_start: int) -> bool:
    """Rough heuristic: skip matches inside single-line comments.

    Tracks string boundaries for both ``//`` and ``/*`` detection.
    Does not handle multi-line block comments or double-escaped
    backslashes -- sufficient for typical JSX/TSX patterns.
    """
    prefix = line[:match_start]
    in_string = False
    for i, ch in enumerate(prefix):
        if ch in ("'", '"', "`") and (i == 0 or prefix[i - 1] != "\\"):
            in_string = not in_string
        if not in_string and prefix[i : i + 2] == "//":
            return True
    if not in_string and "/*" in prefix:
        last_open = prefix.rfind("/*")
        return "*/" not in prefix[last_open:]
    return False


def check_hardcoded_colors(
    content: str,
    file_path: Path,
    project_root: Path,
) -> list[str]:
    """Find hardcoded color values that should use design tokens."""
    warnings: list[str] = []
    rel_path = file_path.relative_to(project_root)

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(_COMMENT_PREFIXES):
            continue

        for m in HARDCODED_COLOR_RE.finditer(line):
            hex_val = m.group("tw_hex") or m.group("css_hex") or m.group("jsx_hex")
            if (
                hex_val
                and _normalize_hex(hex_val) not in ALLOWED_HEX_COLORS
                and not _is_in_comment_context(line, m.start())
            ):
                warnings.append(
                    f"  {rel_path}:{line_num}: Hardcoded color `{hex_val}` "
                    f"-- use a design token (--so-*) or Tailwind semantic class instead.\n"
                    f"    {stripped}"
                )

        for m in HARDCODED_RGBA_RE.finditer(line):
            if _is_in_comment_context(line, m.start()):
                continue
            # Skip rgba() inside a var() fallback (unclosed var( before match)
            before = line[: m.start()]
            var_pos = before.rfind("var(")
            if var_pos >= 0:
                between = before[var_pos : m.start()]
                if between.count("(") > between.count(")"):
                    continue
            warnings.append(
                f"  {rel_path}:{line_num}: Hardcoded rgba() "
                f"-- use a design token variable instead.\n"
                f"    {stripped}"
            )

    return warnings


def check_hardcoded_fonts(
    content: str,
    file_path: Path,
    project_root: Path,
) -> list[str]:
    """Find hardcoded font-family declarations."""
    warnings: list[str] = []
    rel_path = file_path.relative_to(project_root)

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(_COMMENT_PREFIXES):
            continue

        warnings.extend(
            f"  {rel_path}:{line_num}: Hardcoded font-family "
            f"-- use `font-sans` or `font-mono` (maps to Geist tokens).\n"
            f"    {stripped}"
            for m in HARDCODED_FONT_RE.finditer(line)
            if not _is_in_comment_context(line, m.start())
        )

    return warnings


def check_hardcoded_motion_transitions(
    content: str,
    file_path: Path,
    project_root: Path,
) -> list[str]:
    """Find hardcoded Motion transition durations.

    Components should use presets from ``lib/motion.ts`` (e.g.
    ``tweenDefault``, ``tweenFast``, ``tweenExitFast``) or the
    ``useAnimationPreset()`` hook instead of inline duration values.
    """
    rel_str = file_path.relative_to(project_root).as_posix()
    if rel_str in _MOTION_DURATION_SKIP_PATHS:
        return []
    if ".stories." in file_path.name:
        return []
    if file_path.suffix not in {".tsx", ".ts"}:
        return []

    warnings: list[str] = []
    rel_path = file_path.relative_to(project_root)
    lines = content.splitlines()

    # Mask block comments with spaces (preserve newlines) so the regex
    # won't match inside /* ... */ while keeping offsets aligned with content.
    stripped = _BLOCK_COMMENT_RE.sub(
        lambda cm: "".join(" " if c != "\n" else "\n" for c in cm.group()),
        content,
    )

    # Run regex on masked content so multiline transition objects are caught.
    for m in HARDCODED_MOTION_DURATION_RE.finditer(stripped):
        line_num = stripped[: m.start()].count("\n") + 1
        col = m.start() - stripped.rfind("\n", 0, m.start()) - 1
        original_line = lines[line_num - 1]
        line_text = original_line.strip()
        if line_text.startswith(_COMMENT_PREFIXES):
            continue
        if _is_in_comment_context(original_line, col):
            continue
        warnings.append(
            f"  {rel_path}:{line_num}: Hardcoded Motion duration "
            f"-- use a preset from `@/lib/motion` or "
            f"`useAnimationPreset()` hook.\n"
            f"    {line_text}"
        )

    return warnings


def check_missing_story(file_path: Path, project_root: Path) -> list[str]:
    """Check that new components in components/ui/ have a .stories.tsx file."""
    rel_path = file_path.relative_to(project_root)
    parts = rel_path.parts

    if not (
        "components" in parts
        and "ui" in parts
        and file_path.suffix == ".tsx"
        and ".stories." not in file_path.name
        and file_path.name != "index.tsx"
        and "__tests__" not in parts
    ):
        return []

    story_path = file_path.with_suffix("").with_suffix(".stories.tsx")
    if story_path.exists():
        return []
    return [
        f"  {rel_path}: New component without Storybook story "
        f"-- create `{story_path.name}` alongside it."
    ]


def _check_status_dot(content: str, content_lower: str, rel_path: Path) -> list[str]:
    """Check for inline status dot patterns that should use StatusBadge."""
    patterns = [
        r"(?:size-[12]\.?5?|w-[23]|h-[23])\s+.*rounded-full.*(?:bg-success|bg-danger|bg-warning|bg-accent)",
        r"(?:bg-success|bg-danger|bg-warning|bg-accent).*rounded-full.*(?:size-[12]\.?5?|w-[23]|h-[23])",
    ]
    for pattern in patterns:
        if (
            re.search(pattern, content)
            and "statusbadge" not in content_lower
            and "status-badge" not in content_lower
        ):
            return [
                f"  {rel_path}: Inline status dot pattern detected "
                f"-- use `<StatusBadge>` from `@/components/ui/status-badge` instead."
            ]
    return []


def _check_avatar(content: str, rel_path: Path) -> list[str]:
    """Check for inline avatar patterns that should use Avatar.

    Heuristic: matches rounded-full + flex-center + small-text, which is
    the typical initials-circle recipe. May false-positive on non-avatar
    circular flex elements (e.g. icon badges). Kept as a soft suggestion.
    """
    pattern = r"rounded-full.*(?:flex|inline-flex).*(?:items-center|justify-center).*(?:text-xs|text-sm|text-micro)"
    has_avatar_import = (
        "<Avatar" in content
        or "from './avatar'" in content
        or "from '@/components/ui/avatar'" in content
    )
    if re.search(pattern, content) and not has_avatar_import:
        return [
            f"  {rel_path}: Possible inline avatar/initials circle detected "
            f"-- consider using `<Avatar>` from `@/components/ui/avatar` "
            f"or ignore if not applicable."
        ]
    return []


def _check_metric(content: str, content_lower: str, rel_path: Path) -> list[str]:
    """Check for inline metric patterns that should use MetricCard."""
    patterns = [
        r"text-metric.*font-bold.*font-mono",
        r"font-mono.*text-metric.*font-bold",
    ]
    for pattern in patterns:
        if (
            re.search(pattern, content)
            and "metriccard" not in content_lower
            and "metric-card" not in content_lower
        ):
            return [
                f"  {rel_path}: Inline metric display pattern detected "
                f"-- use `<MetricCard>` from `@/components/ui/metric-card` instead."
            ]
    return []


def check_duplicate_patterns(
    content: str,
    file_path: Path,
    project_root: Path,
) -> list[str]:
    """Detect patterns that duplicate existing shared components."""
    rel_path = file_path.relative_to(project_root)
    parts = rel_path.parts

    if "components" in parts and "ui" in parts:
        return []

    content_lower = content.lower()
    warnings: list[str] = []

    warnings.extend(_check_status_dot(content, content_lower, rel_path))
    warnings.extend(_check_avatar(content, rel_path))
    warnings.extend(_check_metric(content, content_lower, rel_path))

    # Check for card patterns that should use SectionCard
    if (
        "border border-border bg-card" in content
        and "border-b border-border" in content
        and "SectionCard" not in content
        and "section-card" not in content
        and file_path.name
        not in {"section-card.tsx", "metric-card.tsx", "agent-card.tsx"}
    ):
        warnings.append(
            f"  {rel_path}: Card-with-header pattern detected "
            f"-- use `<SectionCard>` from `@/components/ui/section-card` instead."
        )

    return warnings


def propose_shared_components(
    content: str,
    file_path: Path,
    project_root: Path,
) -> list[str]:
    """Propose new shared building blocks when repeated patterns are found."""
    rel_path = file_path.relative_to(project_root)
    parts = rel_path.parts

    if "components" in parts and "ui" in parts:
        return []

    proposals: list[str] = []

    # Detect complex list items in .map() that should be extracted.
    # Only matches parenthesized returns: .map((x) => (...)).
    # Misses block bodies and bare JSX returns -- acceptable heuristic.
    map_blocks = re.findall(
        r"\.map\(\s*\([^)]*\)\s*=>\s*\(([\s\S]*?)\)\s*\)",
        content,
    )
    for block in map_blocks:
        line_count = block.count("\n")
        if line_count > _MAP_BLOCK_COMPLEXITY and (
            ("className" in block and "border" in block) or "rounded" in block
        ):
            proposals.append(
                f"  {rel_path}: Complex list item ({line_count} lines) in .map() "
                f"-- consider extracting to a shared component in "
                f"`web/src/components/ui/` with a Storybook story."
            )

    # Detect repeated icon+text row layouts
    icon_label_value = re.findall(
        r'<(?:div|span)[^>]*className="[^"]*(?:flex|inline-flex)[^"]*items-center[^"]*gap[^"]*"[^>]*>'
        r"[\s\S]*?<(?:Icon|Lucide|\w+Icon)",
        content,
    )
    if len(icon_label_value) >= _REPEATED_PATTERN_MIN:
        proposals.append(
            f"  {rel_path}: {len(icon_label_value)} repeated icon+text row patterns "
            f"-- consider a `<DataRow icon label value />` shared component."
        )

    return proposals


def check_file(file_path: Path, project_root: Path) -> list[str]:
    """Run all checks on a single file."""
    if not _is_allowed_file(file_path, project_root):
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"WARNING: Could not read {file_path}: {exc} "
            f"-- design system check skipped.",
            file=sys.stderr,
        )
        return []

    all_warnings: list[str] = []
    all_warnings.extend(check_hardcoded_colors(content, file_path, project_root))
    all_warnings.extend(check_hardcoded_fonts(content, file_path, project_root))
    all_warnings.extend(
        check_hardcoded_motion_transitions(content, file_path, project_root),
    )
    all_warnings.extend(check_missing_story(file_path, project_root))
    all_warnings.extend(check_duplicate_patterns(content, file_path, project_root))
    all_warnings.extend(propose_shared_components(content, file_path, project_root))

    return all_warnings


def _resolve_project_root(file_path: Path, explicit_root: str | None) -> Path:
    """Find the project root directory."""
    if explicit_root:
        return Path(explicit_root).resolve()
    candidate = file_path.parent
    while candidate != candidate.parent:
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
        candidate = candidate.parent
    cwd = Path.cwd()
    print(
        f"WARNING: Could not detect project root from {file_path}; "
        f"falling back to cwd ({cwd}).",
        file=sys.stderr,
    )
    return cwd


def _get_file_path_from_stdin() -> str | None:
    """Try to read the file path from hook JSON on stdin."""
    if sys.stdin.isatty():
        return None
    try:
        data = json.load(sys.stdin)
        raw = data.get("tool_input", {}).get("file_path")
        return str(raw) if isinstance(raw, str) else None
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        print(
            f"WARNING: Failed to parse hook JSON from stdin: {exc}",
            file=sys.stderr,
        )
        return None


def main() -> int:
    """Entry point: hook mode (stdin JSON) or CLI mode (positional arg)."""
    stdin_path = _get_file_path_from_stdin()

    if stdin_path:
        file_path = Path(stdin_path).resolve()
        project_root = _resolve_project_root(file_path, None)
    else:
        parser = argparse.ArgumentParser(
            description="Check web design system adherence",
        )
        parser.add_argument("file_path", help="File to check")
        parser.add_argument(
            "--project-root",
            default=None,
            help="Project root (default: auto-detect)",
        )
        args = parser.parse_args()
        file_path = Path(args.file_path).resolve()
        project_root = _resolve_project_root(file_path, args.project_root)

    warnings = check_file(file_path, project_root)

    if warnings:
        print("DESIGN SYSTEM VIOLATIONS:")
        print()
        for w in warnings:
            print(w)
        print()
        print(
            "Reference: CLAUDE.md 'Web Dashboard' section and "
            "docs/design/brand-and-ux.md 'Component Inventory'."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
