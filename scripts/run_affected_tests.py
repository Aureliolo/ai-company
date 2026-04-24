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


_PASSED_COUNT_RE = re.compile(r"(\d+)\s+passed")


def _parse_test_count(pytest_output: str) -> int | None:
    """Extract the number of passed tests from pytest's final summary.

    Returns ``None`` when the summary line cannot be parsed (degraded
    output, unexpected failure mode, etc.) -- the caller falls back
    to the absolute-seconds rail in that case.
    """
    # pytest prints the summary on the final non-empty line, e.g.
    # ``23373 passed, 16 skipped in 91.86s (0:01:31)``.
    for line in reversed(pytest_output.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        match = _PASSED_COUNT_RE.search(stripped)
        if match:
            return int(match.group(1))
    return None


def _check_timing_regression(  # noqa: PLR0911 -- branching by data shape
    elapsed: float,
    *,
    run_all: bool,
    test_count: int | None,
) -> bool:
    """Return True if the run shows a timing regression.

    Only checks full-suite runs (``run_all=True``) since affected-only
    runs vary widely and are not comparable to the baseline.

    Uses per-test cost as the primary signal (so adding legitimate new
    tests does not trip the alarm): if
    ``elapsed / test_count > baseline_per_test * regression_threshold_ratio``
    the suite is genuinely slower per test. Falls back to the
    absolute-seconds rail when ``test_count`` is unavailable or the
    baseline lacks the ratio field.
    """
    if not run_all or not _BASELINE_PATH.exists():
        return False
    try:
        baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        baseline_secs = float(baseline["unit_suite_seconds"])
        threshold_secs = float(baseline.get("regression_threshold_secs", 10))
        threshold_ratio_raw = baseline.get("regression_threshold_ratio")
        threshold_ratio = (
            float(threshold_ratio_raw) if threshold_ratio_raw is not None else None
        )
        baseline_test_count_raw = baseline.get("test_count")
        baseline_test_count = (
            int(baseline_test_count_raw)
            if baseline_test_count_raw is not None
            else None
        )
    except json.JSONDecodeError, KeyError, ValueError, OSError:
        return False

    # Honor the same override used by the conftest guard.
    import os

    env_override = os.environ.get("UNIT_SUITE_MAX_SECONDS")
    env_max_allowed: float | None = None
    if env_override is not None:
        try:
            env_max_allowed = float(env_override)
        except ValueError:
            # Fail closed on malformed env -- silently swallowing a
            # typo (``UNIT_SUITE_MAX_SECONDS=3oo``) would mean the
            # guard runs with the baseline tolerance while the
            # operator thinks they've relaxed it.
            print(
                f"run_affected_tests: UNIT_SUITE_MAX_SECONDS="
                f"{env_override!r} is not a valid float; ignoring "
                f"the override and using the baseline tolerance.",
                file=sys.stderr,
            )

    border = "!" * 60
    # Env-cap hard rail: if the operator set an absolute ceiling
    # (UNIT_SUITE_MAX_SECONDS) and we blew past it, fail regardless
    # of the per-test ratio. The per-test branch below still catches
    # regressions within the cap.
    if env_max_allowed is not None and elapsed > env_max_allowed:
        print(
            f"\n{border}\n"
            f"REGRESSION DETECTED: suite took {elapsed:.0f}s, exceeds "
            f"UNIT_SUITE_MAX_SECONDS={env_max_allowed:.0f}s.\n"
            f"Baseline: {baseline_secs:.0f}s.\n"
            f"Run A/B against origin/main before fixing anything.\n"
            f"Do NOT delete tests or use --no-verify.\n"
            f"If the new baseline is intentional, update "
            f"tests/baselines/unit_timing.json.\n"
            f"{border}",
            file=sys.stderr,
        )
        return True

    # Prefer per-test cost when we have the data (ratio + both
    # counts). This is the signal the user actually cares about --
    # adding a few hundred tests should not trip the alarm.
    have_per_test = (
        threshold_ratio is not None
        and baseline_test_count is not None
        and baseline_test_count > 0
        and test_count is not None
        and test_count > 0
    )
    if have_per_test:
        # have_per_test already narrows to non-None, positive values,
        # but the type-narrowing flow doesn't propagate across the
        # conjunction so re-assert the invariants inline for mypy.
        assert threshold_ratio is not None  # noqa: S101
        assert baseline_test_count is not None  # noqa: S101
        assert test_count is not None  # noqa: S101
        baseline_per_test = baseline_secs / baseline_test_count
        current_per_test = elapsed / test_count
        max_per_test = baseline_per_test * threshold_ratio
        if current_per_test > max_per_test:
            print(
                f"\n{border}\n"
                f"REGRESSION DETECTED: per-test cost {current_per_test * 1000:.2f}ms "
                f"exceeds {max_per_test * 1000:.2f}ms "
                f"(baseline {baseline_per_test * 1000:.2f}ms, "
                f"ratio {threshold_ratio:.2f}).\n"
                f"Suite: {elapsed:.0f}s across {test_count} tests "
                f"(baseline {baseline_secs:.0f}s across {baseline_test_count}).\n"
                f"Run A/B against origin/main before fixing anything.\n"
                f"Do NOT delete tests or use --no-verify.\n"
                f"If the new baseline is intentional, update "
                f"tests/baselines/unit_timing.json.\n"
                f"{border}",
                file=sys.stderr,
            )
            return True
        return False

    # Fallback: absolute-seconds tolerance when we could not compute
    # per-test cost (no ratio in the baseline, or pytest output was
    # missing a summary line).
    max_allowed = baseline_secs + threshold_secs
    if env_max_allowed is not None:
        max_allowed = env_max_allowed
    if elapsed > max_allowed:
        delta = elapsed - baseline_secs
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
    # Stream pytest stdout line-by-line so users see live progress
    # (subprocess.run + capture_output buffers everything until the
    # process exits, which hides the ~90s full suite behind silence).
    # We still tee into a buffer so the "N passed" summary line is
    # available to ``_parse_test_count`` below.
    with subprocess.Popen(
        cmd,
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as proc:
        stdout_lines: list[str] = []
        assert proc.stdout is not None  # noqa: S101 -- guaranteed by PIPE above
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            stdout_lines.append(line)
        returncode = proc.wait()
    elapsed = time.monotonic() - start
    captured_stdout = "".join(stdout_lines)
    test_count = _parse_test_count(captured_stdout)
    # Skip the regression guard when tests failed / crashed: worker
    # crashes skew ``elapsed / test_count`` upward (time spent before
    # the crash is charged against the surviving test count) and
    # produce false-positive regressions. The underlying failure is
    # already surfaced via ``returncode`` and the test output. When
    # tests fail the operator needs to fix those first; flipping the
    # regression banner on top of a crash output adds noise without
    # pointing at the real root cause.
    if returncode == 0 and _check_timing_regression(
        elapsed,
        run_all=run_all,
        test_count=test_count,
    ):
        # Regression detected -- block the push even if tests passed.
        return max(returncode, 1)
    return returncode


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
