#!/usr/bin/env python3
"""Pre-commit hook: reject files containing em-dashes (U+2014)."""

import sys
from pathlib import Path

# Build patterns without embedding the literal HTML entity in this file
# (otherwise the pre-commit hook flags this script itself).
_PATTERNS = ("\u2014", "&" + "mdash;", "&" + "#8212;", "&" + "#x2014;")


def main() -> int:
    """Scan files for em-dash characters and report locations."""
    found = False
    for path in sys.argv[1:]:
        try:
            with Path(path).open(encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if any(p in line for p in _PATTERNS):
                        print(f"{path}:{lineno}: {line.rstrip()}")
                        found = True
        except UnicodeDecodeError, OSError:
            continue
    if found:
        print("\nEm-dashes (U+2014) found -- use ASCII double-dashes (--) instead.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
