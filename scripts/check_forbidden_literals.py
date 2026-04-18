"""Pre-push / CI forbidden-literal gate.

Stricter counterpart to ``check_backend_regional_defaults.py``: scans every
tracked Python file under ``src/synthorg/`` for a curated list of
forbidden patterns that have no legitimate use in application code.
Designed for pre-push and GitHub Actions.

Docs are intentionally NOT scanned -- operator-facing deployment guides
legitimately contain ``localhost:<port>`` examples and the occasional
``'en-US'`` / currency-code reference.

Forbidden patterns (all outside tests/, CLI Go code, and explicit allowlists):

* Identifier suffix ``_usd``
* Bare string literal ``'USD'`` / ``"USD"``
* Bare BCP 47 tag ``'en-US'`` / ``"en-US"``
* ``localhost:<port>`` references in application code

Exits non-zero with a structured list on violations.

Usage:
    python scripts/check_forbidden_literals.py
    python scripts/check_forbidden_literals.py --paths src/synthorg docs
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Final

_USD_FIELD_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*_usd\b",
)
_BARE_USD_RE: Final[re.Pattern[str]] = re.compile(
    r"""(?<![A-Z_])['"]USD['"](?![A-Z_])""",
)
_BARE_EN_US_RE: Final[re.Pattern[str]] = re.compile(
    r"""['"]en-US['"]""",
)
_LOCALHOST_PORT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:localhost|127\.0\.0\.1):\d+",
)

# Paths whose explicit purpose is to enumerate or demo these literals.
_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "src/synthorg/budget/currency.py",
        "src/synthorg/budget/config.py",
        "src/synthorg/core/types.py",
        "src/synthorg/settings/definitions/budget.py",
        "src/synthorg/settings/definitions/display.py",
        "src/synthorg/api/config.py",
        "src/synthorg/communication/config.py",
        "src/synthorg/persistence/config.py",
        "src/synthorg/providers/presets.py",
        "src/synthorg/providers/discovery.py",
        "src/synthorg/settings/definitions/api.py",
        "src/synthorg/workers/__main__.py",
        "src/synthorg/memory/embedding/fine_tune_runner.py",
        "scripts/check_backend_regional_defaults.py",
        "scripts/check_forbidden_literals.py",
        "scripts/check_web_design_system.py",
        "scripts/_web_design_patterns.py",
    }
)

_SUPPRESSION_MARKER: Final[str] = "lint-allow: regional-defaults"


def _scan_file(file_path: Path, rel: str) -> list[str]:
    """Return violation messages for a single file."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return []
    issues: list[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if _SUPPRESSION_MARKER in line:
            continue
        stripped = line.lstrip()
        # Ignore pure-comment lines -- they discuss forbidden literals.
        if stripped.startswith(("#", "//")):
            continue
        issues.extend(
            f"{rel}:{idx}: identifier {match.group(0)!r} ends in '_usd'"
            for match in _USD_FIELD_RE.finditer(line)
        )
        if _BARE_USD_RE.search(line):
            issues.append(f"{rel}:{idx}: hardcoded 'USD' literal")
        if _BARE_EN_US_RE.search(line):
            issues.append(f"{rel}:{idx}: hardcoded 'en-US' locale")
        if _LOCALHOST_PORT_RE.search(line):
            issues.append(
                f"{rel}:{idx}: hardcoded localhost:<port> in application code"
            )
    return issues


def _iter_targets(roots: list[Path], project_root: Path) -> list[tuple[Path, str]]:
    """Yield ``(absolute_path, posix_relative_path)`` for every file to scan."""
    targets: list[tuple[Path, str]] = []
    for root in roots:
        abs_root = root if root.is_absolute() else project_root / root
        if not abs_root.exists():
            continue
        for ext in ("*.py", "*.md"):
            for path in abs_root.rglob(ext):
                rel = path.relative_to(project_root).as_posix()
                if rel in _ALLOWLIST:
                    continue
                if rel.startswith("tests/") or "/tests/" in rel:
                    continue
                if rel.startswith("cli/"):
                    continue
                targets.append((path, rel))
    return targets


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["src/synthorg"],
        help="Roots to scan (relative to repo root).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    roots = [Path(p) for p in args.paths]
    total = 0
    for path, rel in _iter_targets(roots, project_root):
        issues = _scan_file(path, rel)
        for msg in issues:
            print(msg)
        total += len(issues)
    if total:
        print(
            f"\n{total} forbidden literal(s) found. "
            "Fix them or add a '# lint-allow: regional-defaults' marker "
            "if the value is legitimately demonstrative.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
