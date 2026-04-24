#!/usr/bin/env python3
"""Pre-commit gate: forbid new ``RELEASE_PLEASE_TOKEN`` references.

The fine-grained PAT ``RELEASE_PLEASE_TOKEN`` was retired in favour of the
``synthorg-release-bot`` GitHub App (see issue #1555 and
``docs/reference/github-environments.md``). PAT-authored API commits are
unsigned, which means any workflow resurrecting the PAT would silently
produce commits that fail branch protection's ``required_signatures``
rule (or slip through as Unverified if it writes to a PR branch).

This gate blocks any reintroduction of the identifier anywhere under
``.github/``. There is no baseline file: after #1555 lands, zero
references should remain, and any new reference is a regression.

Why a hard zero rather than a per-file allowlist: the PAT is intended to
be revoked at the GitHub level after cutover. Once revoked, any workflow
still referencing the secret fails with a cryptic `auth` error at the
first API call. Catching the regression at commit time is strictly
cheaper than diagnosing it from a red CI run.

Usage::

    python scripts/check_no_release_please_token.py <file>...   # pre-commit
    python scripts/check_no_release_please_token.py --scan-all  # CI
"""

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GITHUB_ROOT = _REPO_ROOT / ".github"
_FORBIDDEN = "RELEASE_PLEASE_TOKEN"
_STEERING_MESSAGE = (
    "RELEASE_PLEASE_TOKEN was retired in #1555. Use the "
    "`release-runner-setup` composite (which mints a synthorg-release-bot "
    "App installation token) or invoke `actions/create-github-app-token` "
    "directly. See docs/reference/github-environments.md#release_bot_app_."
)


def _iter_workflow_files() -> Iterable[Path]:
    """Walk ``.github/`` for YAML files (workflows, composites, configs)."""
    if not _GITHUB_ROOT.exists():
        return
    for pattern in ("*.yml", "*.yaml"):
        yield from sorted(_GITHUB_ROOT.rglob(pattern))


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, stripped_line)`` for each occurrence of the token."""
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        print(
            f"{_rel(path)}: could not read file: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _FORBIDDEN in line:
            hits.append((lineno, line.strip()))
    return hits


def _rel(path: Path) -> str:
    """Repo-relative POSIX path for stable error output."""
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _report(violations: list[str]) -> int:
    """Print violations + the steering message; return pre-commit exit code."""
    if not violations:
        return 0
    for line in violations:
        print(line)
    print(f"\n{_STEERING_MESSAGE}", file=sys.stderr)
    return 1


def cmd_scan_all() -> int:
    """Walk every YAML file under ``.github/`` and report every hit."""
    violations: list[str] = []
    for path in _iter_workflow_files():
        for lineno, line in _scan_file(path):
            violations.append(f"{_rel(path)}:{lineno}: {line}")
    return _report(violations)


def cmd_scan_paths(paths: Iterable[str]) -> int:
    """Scan the provided files only -- pre-commit's canonical entry point."""
    violations: list[str] = []
    for p in paths:
        path = Path(p).resolve()
        if not path.exists() or path.suffix not in (".yml", ".yaml"):
            continue
        if not path.is_relative_to(_GITHUB_ROOT):
            continue
        for lineno, line in _scan_file(path):
            violations.append(f"{_rel(path)}:{lineno}: {line}")
    return _report(violations)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Block new RELEASE_PLEASE_TOKEN references.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files to check (pre-commit supplies these).",
    )
    parser.add_argument(
        "--scan-all",
        action="store_true",
        help="Scan every YAML file under .github/ (CI mode).",
    )
    args = parser.parse_args(argv)
    if args.scan_all:
        return cmd_scan_all()
    return cmd_scan_paths(args.paths)


if __name__ == "__main__":
    sys.exit(main())
