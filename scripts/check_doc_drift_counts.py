#!/usr/bin/env python3
"""Pre-commit + CI gate: block doc claims that fall below the codebase counts.

Public-facing docs make rounded floor claims like "20,000+ unit tests" or
"100+ event constant modules". This script asserts that each registered
claim site still satisfies ``actual >= floor``: the docs may understate
(rounded down) but must never overstate. When the actual count grows past
the next clean threshold, the doc bumps to the new floor in the same PR.

The script has two modes:

- ``--fast`` (pre-commit): event-module count only. No pytest collection,
  so the hook stays under one second.
- default (CI): full check, including ``pytest --collect-only`` for the
  unit-test claim. Slow (~30s) but authoritative.

Both modes share the same claim registry; the ``source`` field controls
which counter runs in which mode.
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENT_MODULES_DIR = REPO_ROOT / "src" / "synthorg" / "observability" / "events"


@dataclass(frozen=True)
class Claim:
    """A single floor claim registered against a docs file."""

    path: str
    pattern: str
    source: str  # "pytest" or "event_modules"
    label: str


CLAIMS: tuple[Claim, ...] = (
    Claim(
        "README.md",
        r"\((\d[\d,]*)\+ unit tests",
        source="pytest",
        label="README test count",
    ),
    Claim(
        "docs/roadmap/index.md",
        r"\((\d[\d,]*)\+ unit tests",
        source="pytest",
        label="roadmap test count",
    ),
    Claim(
        "docs/design/observability.md",
        r"(\d+)\+ domain-specific event constant modules",
        source="event_modules",
        label="observability event modules",
    ),
    Claim(
        "docs/design/agent-execution.md",
        r"\((\d+)\+ constants\)",
        source="event_modules",
        label="agent-execution event constants",
    ),
    Claim(
        "docs/research/control-plane-audit.md",
        r"(\d+)\+ event constant modules",
        source="event_modules",
        label="control-plane-audit event modules",
    ),
    Claim(
        "docs/research/acg-formalism-evaluation.md",
        r"(\d+)\+ event constant domains",
        source="event_modules",
        label="acg-formalism event domains",
    ),
)


def count_event_modules() -> int:
    """Return the number of domain event-constant modules."""
    return sum(
        1 for path in EVENT_MODULES_DIR.glob("*.py") if path.name != "__init__.py"
    )


def count_unit_tests() -> int:
    """Return the number of tests pytest would collect."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            "tests/",
            "--collect-only",
            "-q",
            "-n",
            "8",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        msg = (
            "pytest --collect-only failed; cannot verify test-count claims.\n"
            f"stderr:\n{result.stderr}"
        )
        raise RuntimeError(msg)
    match = re.search(r"(\d+) tests collected", result.stdout)
    if not match:
        msg = (
            "pytest --collect-only output did not contain a 'N tests collected'"
            f" line. stdout tail:\n{result.stdout[-500:]}"
        )
        raise RuntimeError(msg)
    return int(match.group(1))


def parse_claim(claim: Claim) -> int:
    """Read the file, run the pattern, and return the parsed integer floor."""
    text = (REPO_ROOT / claim.path).read_text(encoding="utf-8")
    match = re.search(claim.pattern, text)
    if not match:
        msg = (
            f"Could not find claim pattern in {claim.path}: {claim.pattern!r}.\n"
            "If the claim was rewritten, update CLAIMS in"
            " scripts/check_doc_drift_counts.py."
        )
        raise RuntimeError(msg)
    return int(match.group(1).replace(",", ""))


def main() -> int:
    """Verify every registered claim's floor is at or below actual."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip pytest-backed claims (suitable for pre-commit).",
    )
    args = parser.parse_args()

    actuals: dict[str, int] = {"event_modules": count_event_modules()}
    if not args.fast:
        actuals["pytest"] = count_unit_tests()

    failures: list[str] = []
    for claim in CLAIMS:
        if claim.source not in actuals:
            continue
        floor = parse_claim(claim)
        actual = actuals[claim.source]
        if actual < floor:
            failures.append(
                f"  {claim.label} ({claim.path}): claim '{floor:,}+' but"
                f" actual is {actual:,}. Lower the floor or investigate."
            )

    if failures:
        print("Doc count drift detected:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        print(
            "\nThe doc value is the lower bound; the codebase has fallen"
            " below it. Adjust the floor in the affected docs (or restore"
            " the deleted tests / event modules).",
            file=sys.stderr,
        )
        return 1

    if not args.fast:
        print(
            f"OK: all {len(CLAIMS)} claims satisfy floor <= actual"
            f" (tests={actuals['pytest']:,},"
            f" event_modules={actuals['event_modules']})."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
