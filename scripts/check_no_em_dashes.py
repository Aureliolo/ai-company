#!/usr/bin/env python3
"""Pre-commit hook: reject files containing em-dashes (U+2014)."""

import sys
from pathlib import Path


def main() -> int:
    """Scan files for em-dash characters and report locations."""
    found = False
    for path in sys.argv[1:]:
        try:
            with Path(path).open(encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if "\u2014" in line:
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
