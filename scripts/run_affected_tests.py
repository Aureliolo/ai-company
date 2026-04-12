#!/usr/bin/env python3
"""Pre-push hook: run only unit tests affected by changed files.

Uses git diff against origin/main to determine which source modules changed,
then maps them to their corresponding test directories via the project's 1:1
``src/synthorg/<module>/`` -> ``tests/unit/<module>/`` layout.
Only Python (``.py``) file changes are considered; non-Python changes are ignored.

Foundational modules (core, config, observability) are imported by nearly every
other module, so changes to them trigger a full test run. Same for any
``conftest.py`` and top-level source files (``__init__.py``, ``constants.py``).

Exit codes match pytest: 0 (passed/nothing to run), 1 (failures), etc.
Git command failures fall back to running the full unit suite.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules imported by nearly everything -- changes here mean "run all tests".
_BLAST_RADIUS_MODULES = frozenset({"core", "config", "observability"})

# Top-level source files that aren't in a module directory.
_TOP_LEVEL_SRC = frozenset({"__init__.py", "constants.py"})

# Minimum path depth for src/synthorg/<module> or tests/unit/<module>.
_MIN_MODULE_DEPTH = 3

# Valid Python package directory names (prevents path traversal).
_SAFE_MODULE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class _GitError(Exception):
    """Raised when a required git command fails."""


def _git(*args: str) -> str:
    """Run a git command and return stripped stdout.

    Raises ``_GitError`` on non-zero exit so callers fail closed.
    """
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        msg = f"git {' '.join(args)} failed: {result.stderr.strip()}"
        raise _GitError(msg)
    return result.stdout.strip()


def _merge_base() -> str:
    """Find the merge base between HEAD and origin/main."""
    try:
        return _git("merge-base", "HEAD", "origin/main")
    except _GitError:
        # Fallback: if merge-base fails (e.g. origin/main not fetched, or
        # history too shallow), diff against HEAD~1 so we check *something*.
        return _git("rev-parse", "HEAD~1")


def _changed_files(base: str) -> list[str]:
    """Return files changed between *base* and HEAD.

    Includes both committed and uncommitted changes as a safety net.
    """
    committed = _git("diff", "--name-only", f"{base}...HEAD")
    uncommitted = _git("diff", "--name-only", "HEAD")
    all_files: set[str] = set()
    for block in (committed, uncommitted):
        if block:
            all_files.update(block.splitlines())
    return sorted(all_files)


def _classify_path(parts: tuple[str, ...]) -> tuple[str, str | None]:
    """Classify a file path into a category and optional module name.

    Returns ``(category, module)`` where category is one of:
    ``"conftest"``, ``"blast_radius"``, ``"top_level_src"``,
    ``"src_module"``, ``"test_unit"``, ``"other"``.
    """
    if parts[-1] == "conftest.py":
        return "conftest", None

    is_deep_enough = len(parts) >= _MIN_MODULE_DEPTH
    if is_deep_enough and parts[0] == "src" and parts[1] == "synthorg":
        if parts[2] in _TOP_LEVEL_SRC:
            return "top_level_src", None
        if not _SAFE_MODULE_NAME.match(parts[2]):
            return "other", None
        return (
            ("blast_radius", None)
            if parts[2] in _BLAST_RADIUS_MODULES
            else ("src_module", parts[2])
        )

    if is_deep_enough and parts[0] == "tests" and parts[1] == "unit":
        # The regex already rejects dotted names like test_smoke.py and
        # __init__.py, but listing them explicitly documents the intent.
        is_root = (
            not _SAFE_MODULE_NAME.match(parts[2])
            or parts[2] == "test_smoke.py"
            or parts[2] in _TOP_LEVEL_SRC
        )
        return ("test_unit", ".") if is_root else ("test_unit", parts[2])

    return "other", None


def _affected_test_dirs(changed: list[str]) -> tuple[list[str], bool]:
    """Map changed files to test directories.

    Returns ``(test_dirs, run_all)`` where *run_all* is True when a
    blast-radius module or shared infrastructure was touched.
    """
    modules: set[str] = set()

    for filepath in changed:
        parts = PurePosixPath(filepath).parts
        category, module = _classify_path(parts)

        if category in {"conftest", "blast_radius", "top_level_src"}:
            return [], True
        if module is not None:
            modules.add(module)

    # Build test directory paths (only dirs that actually exist).
    test_dirs: list[str] = []
    for mod in sorted(modules):
        if mod == ".":
            smoke = _REPO_ROOT / "tests" / "unit" / "test_smoke.py"
            if smoke.exists():
                test_dirs.append(str(smoke.relative_to(_REPO_ROOT)))
        else:
            test_dir = _REPO_ROOT / "tests" / "unit" / mod
            if test_dir.is_dir():
                test_dirs.append(str(test_dir.relative_to(_REPO_ROOT)))

    return test_dirs, False


_BASELINE_PATH = _REPO_ROOT / "tests" / "baselines" / "unit_timing.json"


def _check_timing_regression(elapsed: float, *, run_all: bool) -> bool:
    """Return True if the run shows a timing regression.

    Only checks full-suite runs (``run_all=True``) since affected-only
    runs vary widely and are not comparable to the baseline.

    Uses an absolute-seconds tolerance (``regression_threshold_secs``):
    only a few seconds of variance is allowed; larger regressions are
    real bugs that must block the push.
    """
    if not run_all or not _BASELINE_PATH.exists():
        return False
    try:
        baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        baseline_secs = float(baseline["unit_suite_seconds"])
        threshold_secs = float(baseline.get("regression_threshold_secs", 10))
    except json.JSONDecodeError, KeyError, ValueError, OSError:
        return False
    max_allowed = baseline_secs + threshold_secs
    # Honor the same override used by the conftest guard.
    import contextlib
    import os

    env_override = os.environ.get("UNIT_SUITE_MAX_SECONDS")
    if env_override is not None:
        with contextlib.suppress(ValueError):
            max_allowed = float(env_override)
    if elapsed > max_allowed:
        delta = elapsed - baseline_secs
        border = "!" * 60
        print(
            f"\n{border}\n"
            f"REGRESSION DETECTED: suite took {elapsed:.0f}s, "
            f"baseline is {baseline_secs:.0f}s (+{delta:.0f}s, "
            f"tolerance {threshold_secs:.0f}s)\n"
            f"Run A/B against origin/main before fixing anything.\n"
            f"Do NOT delete tests or use --no-verify.\n"
            f"If the new baseline is intentional, update "
            f"tests/baselines/unit_timing.json.\n"
            f"{border}",
            file=sys.stderr,
        )
        return True
    return False


def _run_pytest(paths: list[str], *, run_all: bool = False) -> int:
    """Run pytest with the given paths.

    Uses ``--dist loadscope`` instead of pyproject.toml's default
    ``worksteal`` to group tests by module, preventing xdist worker
    crashes from repeated heavy fixture teardown/setup (Litestar
    TestClient, SQLite connections) when individual tests are
    scattered across workers during full-suite runs.

    ``--max-worker-restart=0`` disables worker restarts to avoid a
    known xdist scheduler KeyError when the loadscope scheduler
    tries to reassign work to a restarted worker with a new id.
    """
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *paths,
        "-m",
        "unit",
        "-n",
        "8",
        "--dist",
        "loadscope",
        "--max-worker-restart=0",
        "-q",
    ]
    start = time.monotonic()
    result = subprocess.run(cmd, cwd=_REPO_ROOT, check=False)
    elapsed = time.monotonic() - start
    if _check_timing_regression(elapsed, run_all=run_all):
        # Regression detected -- block the push even if tests passed.
        return max(result.returncode, 1)
    return result.returncode


def main() -> int:
    """Entry point."""
    try:
        base = _merge_base()
    except _GitError as exc:
        print(f"ERROR: {exc} -- running full unit suite", file=sys.stderr)
        return _run_pytest(["tests/unit/"], run_all=True)

    try:
        changed = _changed_files(base)
    except _GitError as exc:
        print(f"ERROR: {exc} -- running full unit suite", file=sys.stderr)
        return _run_pytest(["tests/unit/"], run_all=True)

    # Filter to Python files only.
    py_changed = [f for f in changed if f.endswith(".py")]
    if not py_changed:
        print("No Python files changed -- skipping unit tests.")
        return 0

    test_dirs, run_all = _affected_test_dirs(py_changed)

    if run_all:
        print("Foundational module or conftest changed -- running full unit suite.")
        return _run_pytest(["tests/unit/"], run_all=True)

    if not test_dirs:
        print("Changed files don't map to any test directories -- skipping.")
        return 0

    print(f"Running affected tests: {', '.join(test_dirs)}")
    return _run_pytest(test_dirs)


if __name__ == "__main__":
    sys.exit(main())
