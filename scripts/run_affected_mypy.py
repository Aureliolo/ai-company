#!/usr/bin/env python3
"""Pre-push hook: run mypy only on modules affected by changed files.

Uses git diff against origin/main to determine which source modules changed,
then type-checks only those module directories (both ``src/synthorg/<module>/``
and ``tests/unit/<module>/``).

Foundational modules (core, config, observability) trigger a full mypy run
because they define types imported across the entire codebase. The ``.mypy_cache/``
directory keeps subsequent full runs fast (~15-20s with warm cache).

Exit codes:
    0 -- type-check passed (or nothing to check)
    1 -- type errors found
    2 -- script error
"""

import subprocess
import sys
from pathlib import Path, PurePosixPath

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules imported by nearly everything -- changes here mean "full mypy".
_BLAST_RADIUS_MODULES = frozenset({"core", "config", "observability"})

# Top-level source files that aren't in a module directory.
_TOP_LEVEL_SRC = frozenset({"__init__.py", "constants.py", "py.typed"})

# Minimum path depth for src/synthorg/<module> or tests/<kind>/<module>.
_MIN_MODULE_DEPTH = 3

# Test subdirectories that mypy should cover.
_TEST_KINDS = frozenset({"unit", "integration"})


def _git(*args: str) -> str:
    """Run a git command and return stripped stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(f"git {' '.join(args)} failed: {result.stderr}", file=sys.stderr)
        return ""
    return result.stdout.strip()


def _merge_base() -> str:
    """Find the merge base between HEAD and origin/main."""
    base = _git("merge-base", "HEAD", "origin/main")
    if not base:
        base = _git("rev-parse", "HEAD~1")
    return base


def _changed_files(base: str) -> list[str]:
    """Return files changed between *base* and HEAD."""
    committed = _git("diff", "--name-only", f"{base}...HEAD")
    uncommitted = _git("diff", "--name-only", "HEAD")
    all_files: set[str] = set()
    for block in (committed, uncommitted):
        if block:
            all_files.update(block.splitlines())
    return sorted(all_files)


def _classify_path(
    parts: tuple[str, ...],
) -> tuple[str, str | None, str | None]:
    """Classify a file path for mypy target selection.

    Returns ``(category, module, test_path)`` where category is one of:
    ``"conftest"``, ``"blast_radius"``, ``"top_level_src"``,
    ``"src_module"``, ``"test_module"``, ``"other"``.
    """
    if parts[-1] == "conftest.py":
        return "conftest", None, None

    if len(parts) >= _MIN_MODULE_DEPTH and parts[0] == "src" and parts[1] == "synthorg":
        if parts[2] in _TOP_LEVEL_SRC:
            return "top_level_src", None, None
        if parts[2] in _BLAST_RADIUS_MODULES:
            return "blast_radius", None, None
        return "src_module", parts[2], None

    if (
        len(parts) >= _MIN_MODULE_DEPTH
        and parts[0] == "tests"
        and parts[1] in _TEST_KINDS
        and parts[2] not in _TOP_LEVEL_SRC
        and parts[2] != "test_smoke.py"
    ):
        return "test_module", None, f"tests/{parts[1]}/{parts[2]}"

    return "other", None, None


def _affected_mypy_paths(changed: list[str]) -> tuple[list[str], bool]:
    """Map changed files to mypy target directories.

    Returns ``(paths, run_all)`` where *run_all* is True when a
    blast-radius module or shared infrastructure was touched.
    """
    src_modules: set[str] = set()
    test_paths: set[str] = set()

    for filepath in changed:
        parts = PurePosixPath(filepath).parts
        category, module, test_path = _classify_path(parts)

        if category in {"conftest", "blast_radius", "top_level_src"}:
            return [], True
        if module is not None:
            src_modules.add(module)
        if test_path is not None:
            test_paths.add(test_path)

    # Build mypy target paths (only dirs that exist).
    paths: list[str] = []
    for mod in sorted(src_modules):
        src_dir = _REPO_ROOT / "src" / "synthorg" / mod
        if src_dir.is_dir():
            paths.append(f"src/synthorg/{mod}")
        test_dir = _REPO_ROOT / "tests" / "unit" / mod
        if test_dir.is_dir():
            paths.append(f"tests/unit/{mod}")

    # Also include directly-changed test dirs not covered by src_modules.
    for tp in sorted(test_paths):
        if tp not in paths and (_REPO_ROOT / tp).is_dir():
            paths.append(tp)

    return paths, False


def _run_mypy(paths: list[str]) -> int:
    """Run mypy with the given paths."""
    cmd = [sys.executable, "-m", "mypy", *paths]
    result = subprocess.run(cmd, cwd=_REPO_ROOT, check=False)
    return result.returncode


def main() -> int:
    """Entry point."""
    base = _merge_base()
    if not base:
        print(
            "WARNING: could not determine merge base, running full mypy",
            file=sys.stderr,
        )
        return _run_mypy(["src/", "tests/"])

    changed = _changed_files(base)

    # Filter to Python files only.
    py_changed = [f for f in changed if f.endswith(".py")]
    if not py_changed:
        print("No Python files changed -- skipping mypy.")
        return 0

    paths, run_all = _affected_mypy_paths(py_changed)

    if run_all:
        print("Foundational module or conftest changed -- running full mypy.")
        return _run_mypy(["src/", "tests/"])

    if not paths:
        print("Changed files don't map to any mypy targets -- skipping.")
        return 0

    print(f"Running mypy on: {', '.join(paths)}")
    return _run_mypy(paths)


if __name__ == "__main__":
    sys.exit(main())
