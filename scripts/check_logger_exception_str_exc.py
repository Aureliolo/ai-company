#!/usr/bin/env python3
"""Pre-commit gate: forbid new ``logger.exception(..., error=str(exc))`` sites.

The pattern ``logger.exception(EVENT, ..., error=str(exc))`` is a known
secret-exfiltration vector on credential-handling code paths (SEC-1 /
audit finding 90):

* ``logger.exception`` attaches a full Python traceback; structlog
  serialises frame-local variables into the event, so any in-scope
  ``client_secret`` / ``refresh_token`` / Fernet ciphertext in the
  exception frame leaks to logs.
* ``str(exc)`` on ``httpx.HTTPStatusError`` frequently embeds the
  POST body or response body, which carries the credentials that
  triggered the failure.

This gate walks each file's AST and refuses any new site.  The existing
population at the time of SEC-1 landing is recorded in
``scripts/_logger_exception_baseline.json`` as a per-file count so that
already-grandfathered callers don't block every unrelated commit.  The
gate fires when:

* A pre-existing file exceeds its baseline count (new instance added).
* A new file introduces the pattern (no baseline entry, count > 0).

To convert a grandfathered site, replace ``logger.exception(EVENT,
..., error=str(exc))`` with::

    logger.warning(
        EVENT,
        ...,
        error_type=type(exc).__name__,
        error=safe_error_description(exc),
    )

(``from synthorg.observability.redaction import safe_error_description``)
then re-run this script with ``--refresh-baseline`` to shrink the
baseline.  The baseline can only shrink through this path; it can never
grow without an explicit SEC review.

Usage::

    python scripts/check_logger_exception_str_exc.py <file>...     # pre-commit
    python scripts/check_logger_exception_str_exc.py --scan-all    # CI / tests
    python scripts/check_logger_exception_str_exc.py --refresh-baseline
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_ROOT = _REPO_ROOT / "src"
_BASELINE_PATH = Path(__file__).resolve().parent / "_logger_exception_baseline.json"

_LOGGER_METHODS: frozenset[str] = frozenset({"exception"})
"""Which ``logger.<method>(...)`` names are covered by this gate.

We only gate ``logger.exception`` because it is the only log method
that attaches a Python traceback by default. ``logger.warning`` /
``logger.error`` do not attach traceback, so ``error=str(exc)`` in
those calls is a less severe concern handled at each callsite.
"""


class _LoggerExceptionFinder(ast.NodeVisitor):
    """Locate ``logger.<method>(..., error=str(exc))`` call sites.

    Attributes:
        hits: Tuples of ``(lineno, col_offset)`` for each match.
    """

    def __init__(self) -> None:
        self.hits: list[tuple[int, int]] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Match ``logger.<method>(...)`` calls with ``error=str(exc)``."""
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "logger"
            and func.attr in _LOGGER_METHODS
            and _has_error_str_exc_kwarg(node.keywords)
        ):
            self.hits.append((node.lineno, node.col_offset))
        self.generic_visit(node)


def _has_error_str_exc_kwarg(keywords: Iterable[ast.keyword]) -> bool:
    """Return ``True`` if any keyword is ``error=str(exc_like)``."""
    for kw in keywords:
        if kw.arg != "error":
            continue
        value = kw.value
        if not isinstance(value, ast.Call):
            continue
        if not isinstance(value.func, ast.Name) or value.func.id != "str":
            continue
        if len(value.args) != 1:
            continue
        arg = value.args[0]
        if isinstance(arg, ast.Name):
            return True
    return False


def _count_hits(path: Path) -> int:
    """Return the number of ``logger.exception(..., error=str(exc))`` hits."""
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError, OSError:
        return 0
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return 0
    finder = _LoggerExceptionFinder()
    finder.visit(tree)
    return len(finder.hits)


def _scan_file(path: Path) -> tuple[int, list[tuple[int, int]]]:
    """Return ``(count, locations)`` for a single file."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    finder = _LoggerExceptionFinder()
    finder.visit(tree)
    return len(finder.hits), finder.hits


def _iter_source_files() -> Iterable[Path]:
    """Walk ``src/synthorg/`` for ``.py`` files."""
    yield from sorted(_SRC_ROOT.rglob("*.py"))


def _load_baseline() -> dict[str, int]:
    """Load the per-file baseline count map."""
    if not _BASELINE_PATH.exists():
        return {}
    with _BASELINE_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    counts = data.get("counts", {})
    if not isinstance(counts, dict):
        return {}
    return {str(k): int(v) for k, v in counts.items()}


def _save_baseline(counts: dict[str, int]) -> None:
    """Write a refreshed baseline snapshot."""
    payload = {
        "description": (
            "SEC-1 baseline: count of `logger.exception(..., error=str(exc))`"
            " sites per file. Generated by"
            " scripts/check_logger_exception_str_exc.py --refresh-baseline."
            " Do not hand-edit."
        ),
        "counts": dict(sorted(counts.items())),
    }
    with _BASELINE_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def _rel(path: Path) -> str:
    """Repo-relative POSIX path for stable baseline keys."""
    return path.resolve().relative_to(_REPO_ROOT).as_posix()


def cmd_refresh_baseline() -> int:
    """Recompute the baseline from current source state."""
    counts: dict[str, int] = {}
    for src_path in _iter_source_files():
        count = _count_hits(src_path)
        if count > 0:
            counts[_rel(src_path)] = count
    _save_baseline(counts)
    total = sum(counts.values())
    print(
        f"Baseline refreshed: {total} sites across {len(counts)} files "
        f"-> {_BASELINE_PATH.relative_to(_REPO_ROOT).as_posix()}",
    )
    return 0


class _AnyLoggerExceptionFinder(ast.NodeVisitor):
    """Count ``logger.exception(...)`` calls regardless of kwargs."""

    def __init__(self) -> None:
        self.total = 0

    def visit_Call(self, node: ast.Call) -> None:
        """Count any ``logger.exception(...)`` call."""
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "logger"
            and func.attr == "exception"
        ):
            self.total += 1
        self.generic_visit(node)


def cmd_classify() -> int:
    """Print per-file classification: ``all|mixed|none`` for SEC-1 sweep.

    Useful during the SEC-1 sweep to know which files can use
    ``replace_all=True`` on ``logger.exception`` -> ``logger.warning``
    safely (``all``) versus which need per-site handling (``mixed``).
    """
    for src_path in _iter_source_files():
        try:
            source = src_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(src_path))
        except UnicodeDecodeError, OSError, SyntaxError:
            continue
        str_exc = _LoggerExceptionFinder()
        any_exc = _AnyLoggerExceptionFinder()
        str_exc.visit(tree)
        any_exc.visit(tree)
        total = any_exc.total
        hits = len(str_exc.hits)
        if total == 0:
            continue
        if hits == 0:
            classification = "none"
        elif hits == total:
            classification = "all"
        else:
            classification = "mixed"
        print(f"{classification}\t{hits}\t{total}\t{_rel(src_path)}")
    return 0


def cmd_scan_all() -> int:
    """Scan the whole src tree and compare to the baseline."""
    baseline = _load_baseline()
    violations: list[str] = []
    for src_path in _iter_source_files():
        count = _count_hits(src_path)
        key = _rel(src_path)
        allowed = baseline.get(key, 0)
        if count > allowed:
            _, locations = _scan_file(src_path)
            for lineno, col in locations[allowed:]:
                violations.append(
                    f"{key}:{lineno}:{col}: new logger.exception(..., error=str(exc)) site"
                )
    return _report(violations)


def cmd_scan_paths(paths: Iterable[str]) -> int:
    """Scan the given files (pre-commit entry point)."""
    baseline = _load_baseline()
    violations: list[str] = []
    for p in paths:
        path = Path(p).resolve()
        if not path.is_relative_to(_SRC_ROOT):
            continue
        if not path.exists() or path.suffix != ".py":
            continue
        try:
            count, locations = _scan_file(path)
        except SyntaxError as exc:
            print(f"WARNING: skipping {p}: {exc}", file=sys.stderr)
            continue
        key = _rel(path)
        allowed = baseline.get(key, 0)
        if count > allowed:
            for lineno, col in locations[allowed:]:
                violations.append(
                    f"{key}:{lineno}:{col}: new logger.exception(..., error=str(exc)) site"
                )
    return _report(violations)


def _report(violations: list[str]) -> int:
    """Print violations and return a pre-commit-friendly exit code."""
    if not violations:
        return 0
    for line in violations:
        print(line)
    print(
        "\nSEC-1: `logger.exception(..., error=str(exc))` leaks credential"
        " material via traceback frame-locals AND str(exc) embedding."
        "\nReplace with:"
        "\n    logger.warning("
        "\n        EVENT_NAME,"
        "\n        ...,"
        "\n        error_type=type(exc).__name__,"
        "\n        error=safe_error_description(exc),"
        "\n    )"
        "\n"
        "\nAdd: from synthorg.observability.redaction import safe_error_description"
        "\n"
        "\nAfter converting one or more grandfathered sites, refresh the baseline:"
        "\n    python scripts/check_logger_exception_str_exc.py --refresh-baseline",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Gate on logger.exception(..., error=str(exc)) sites.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files to check (pre-commit supplies these).",
    )
    parser.add_argument(
        "--scan-all",
        action="store_true",
        help="Scan the full src tree (CI mode).",
    )
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="Rewrite _logger_exception_baseline.json from current state.",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help=(
            "Print per-file classification (all|mixed|none) to help the "
            "SEC-1 sweep know where replace_all is safe."
        ),
    )
    args = parser.parse_args(argv)

    if args.refresh_baseline:
        return cmd_refresh_baseline()
    if args.classify:
        return cmd_classify()
    if args.scan_all:
        return cmd_scan_all()
    return cmd_scan_paths(args.paths)


if __name__ == "__main__":
    sys.exit(main())
