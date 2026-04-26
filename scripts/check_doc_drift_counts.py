#!/usr/bin/env python3
"""Pre-commit + CI gate: block precise doc counts that fall below reality.

Public-facing docs make precise floor claims like "100+ event constant
modules". This script asserts that each registered claim still satisfies
``actual >= floor``: the docs may understate (rounded down) but must
never overstate. When actual grows past the next clean threshold, the
doc bumps to the new floor in the same PR.

Marketing-style counts (eg "25,000+ unit tests" in README/roadmap) are
deliberately NOT gated here. They are rounded narrative claims under
human editorial control, not mechanically-verified invariants -- a
strict gate would either fight the rounding or force the doc to track
every test addition. The event-module count, by contrast, is a
load-bearing precise number used by docs that point readers at code,
so we keep it strict.
"""

import re
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
    label: str


CLAIMS: tuple[Claim, ...] = (
    Claim(
        "docs/design/observability.md",
        r"(\d+)\+ domain-specific event constant modules",
        label="observability event modules",
    ),
    Claim(
        "docs/design/agent-execution.md",
        r"\((\d+)\+ constants\)",
        label="agent-execution event constants",
    ),
    Claim(
        "docs/research/control-plane-audit.md",
        r"(\d+)\+ event constant modules",
        label="control-plane-audit event modules",
    ),
    Claim(
        "docs/research/control-plane-audit.md",
        r"(\d+)\+ structured event constants",
        label="control-plane-audit structured event constants",
    ),
    Claim(
        "docs/research/control-plane-audit.md",
        r"observability \((\d+)\+ structured events\)",
        label="control-plane-audit observability events",
    ),
    Claim(
        "docs/research/acg-formalism-evaluation.md",
        r"(\d+)\+ event constant domains",
        label="acg-formalism event domains",
    ),
)


def count_event_modules() -> int:
    """Return the number of domain event-constant modules."""
    return sum(
        1 for path in EVENT_MODULES_DIR.glob("*.py") if path.name != "__init__.py"
    )


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
    actual = count_event_modules()

    failures: list[str] = []
    for claim in CLAIMS:
        floor = parse_claim(claim)
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

    print(
        f"OK: all {len(CLAIMS)} claims satisfy floor <= actual (event_modules={actual})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
