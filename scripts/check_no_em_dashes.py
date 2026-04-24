#!/usr/bin/env python3
"""Pre-commit hook: reject files containing em-dashes (U+2014)."""

import sys
from pathlib import Path

# Build patterns without embedding the literal HTML entity in this file
# (otherwise the pre-commit hook flags this script itself).
_PATTERNS = ("\u2014", "&" + "mdash;", "&" + "#8212;", "&" + "#x2014;")
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Auto-generated files whose em-dash content is produced by tooling
# (release-please regenerates the changelog on every release from
# historical commit subjects). Hand-edits are discouraged; excluding
# them avoids forcing manual scrubs that would be overwritten on the
# next release anyway.
_EXCLUDED_RELATIVE: frozenset[str] = frozenset({".github/CHANGELOG.md"})


def main() -> int:
    """Scan files for em-dash characters and report locations."""
    found = False
    for path in sys.argv[1:]:
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(_REPO_ROOT):
            continue
        relative = resolved.relative_to(_REPO_ROOT).as_posix()
        if relative in _EXCLUDED_RELATIVE:
            continue
        try:
            with resolved.open(encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if any(p in line for p in _PATTERNS):
                        print(f"{path}:{lineno}: {line.rstrip()}")
                        found = True
        except (UnicodeDecodeError, OSError) as exc:
            print(f"WARNING: skipping {path}: {exc}", file=sys.stderr)
            continue
    if found:
        print("\nEm-dashes (U+2014) found -- use ASCII double-dashes (--) instead.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
