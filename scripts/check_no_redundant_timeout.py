#!/usr/bin/env python3
"""Pre-commit hook: reject tests with redundant pytest.mark.timeout(30).

The global ``timeout = 30`` in pyproject.toml already applies to every test.
Per-file ``pytest.mark.timeout(30)`` markers are redundant noise.
Non-default overrides (e.g. ``timeout(60)``) are allowed.
"""

import re
import sys
from pathlib import Path

_PATTERN = re.compile(r"pytest\.mark\.timeout\(\s*30\s*\)")
_REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    """Scan files for redundant pytest.mark.timeout(30) and report locations."""
    found = False
    for path in sys.argv[1:]:
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(_REPO_ROOT):
            continue
        try:
            with resolved.open(encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if _PATTERN.search(line):
                        print(f"{path}:{lineno}: {line.rstrip()}")
                        found = True
        except (UnicodeDecodeError, OSError) as exc:
            print(f"WARNING: skipping {path}: {exc}", file=sys.stderr)
            continue
    if found:
        print(
            "\npytest.mark.timeout(30) is redundant"
            " -- pyproject.toml sets timeout = 30 globally."
            "\nRemove the marker or use a different value for intentional overrides."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
