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
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _BaselineSnapshot:
    """Validated numeric view of ``tests/baselines/unit_timing.json``.

    ``threshold_ratio`` and ``test_count`` are ``None`` when the baseline
    does not carry the per-test rail data, which flips the caller to
    the absolute-seconds fallback.
    """

    baseline_secs: float
    threshold_secs: float
    threshold_ratio: float | None
    baseline_test_count: int | None


def _positive_finite_float(raw: object) -> float | None:
    """Coerce *raw* to a strictly positive finite float, or ``None``."""
    if raw is None:
        return None
    try:
        candidate = float(raw)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return None
    if not math.isfinite(candidate) or candidate <= 0:
        return None
    return candidate


def _positive_int(raw: object) -> int | None:
    """Coerce *raw* to a strictly positive int, or ``None``."""
    if raw is None:
        return None
    try:
        # ``int(raw)`` accepts str/bytes/SupportsInt/SupportsIndex; tolerate
        # any of those (baseline JSON could store a string or float) and
        # reject anything else as an unusable baseline value.
        candidate = int(raw)  # type: ignore[call-overload]
    except TypeError, ValueError:
        return None
    return candidate if candidate > 0 else None


def _load_baseline_snapshot() -> _BaselineSnapshot | None:
    """Parse and validate the baseline file.

    Returns ``None`` when the file is missing, malformed, or carries
    non-finite / non-positive numbers that would make the per-test
    rail meaningless (e.g. ``regression_threshold_ratio: 0`` would
    flag every run as a regression).
    """
    if not _BASELINE_PATH.exists():
        return None
    try:
        baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        baseline_secs = float(baseline["unit_suite_seconds"])
        threshold_secs = float(baseline.get("regression_threshold_secs", 10))
    except json.JSONDecodeError, KeyError, ValueError, OSError:
        return None
    if (
        not math.isfinite(baseline_secs)
        or baseline_secs <= 0
        or not math.isfinite(threshold_secs)
        or threshold_secs < 0
    ):
        return None
    return _BaselineSnapshot(
        baseline_secs=baseline_secs,
        threshold_secs=threshold_secs,
        threshold_ratio=_positive_finite_float(
            baseline.get("regression_threshold_ratio"),
        ),
        baseline_test_count=_positive_int(baseline.get("test_count")),
    )


def _parse_env_override() -> float | None:
    """Return the ``UNIT_SUITE_MAX_SECONDS`` override if usable.

    Silently swallowing a typo (``UNIT_SUITE_MAX_SECONDS=3oo``) would
    mean the guard runs with the baseline tolerance while the operator
    thinks they have relaxed it, so malformed values print a diagnostic
    to stderr before falling back.
    """
    env_override = os.environ.get("UNIT_SUITE_MAX_SECONDS")
    if env_override is None:
        return None
    try:
        parsed = float(env_override)
    except ValueError:
        print(
            f"run_affected_tests: UNIT_SUITE_MAX_SECONDS="
            f"{env_override!r} is not a valid float; ignoring "
            f"the override and using the baseline tolerance.",
            file=sys.stderr,
        )
        return None
    # ``float("nan")`` / ``float("inf")`` parse cleanly but make the
    # guard meaningless (every elapsed comparison is False for NaN;
    # Inf disables the cap entirely). A zero or negative cap would
    # block every run. Ignore these and fall back.
    if not math.isfinite(parsed) or parsed <= 0:
        print(
            f"run_affected_tests: UNIT_SUITE_MAX_SECONDS="
            f"{env_override!r} must be a finite positive "
            f"number; ignoring the override and using the "
            f"baseline tolerance.",
            file=sys.stderr,
        )
        return None
    return parsed


def _print_regression_banner(message: str) -> None:
    """Emit a regression banner with the standard footer.

    Keeping the banner footer (run A/B; do not delete tests; update
    baseline intentionally) in one place keeps every failure mode's
    remediation identical without repeating the boilerplate at each
    call site.
    """
    border = "!" * 60
    print(
        f"\n{border}\n"
        f"{message}\n"
        f"Run A/B against origin/main before fixing anything.\n"
        f"Do NOT delete tests or use --no-verify.\n"
        f"If the new baseline is intentional, update "
        f"tests/baselines/unit_timing.json.\n"
        f"{border}",
        file=sys.stderr,
    )


def _check_per_test_regression(
    elapsed: float,
    *,
    snapshot: _BaselineSnapshot,
    test_count: int | None,
) -> bool | None:
    """Per-test cost rail.

    Returns ``None`` when the baseline does not carry ratio / count
    data (caller falls back to the absolute-seconds rail). Returns
    ``True`` when the per-test cost exceeds the baseline multiplied
    by ``threshold_ratio``, else ``False`` -- the definitive decision
    when data is available.
    """
    if (
        snapshot.threshold_ratio is None
        or snapshot.baseline_test_count is None
        or test_count is None
        or test_count <= 0
    ):
        return None
    baseline_per_test = snapshot.baseline_secs / snapshot.baseline_test_count
    current_per_test = elapsed / test_count
    max_per_test = baseline_per_test * snapshot.threshold_ratio
    if current_per_test <= max_per_test:
        return False
    _print_regression_banner(
        f"REGRESSION DETECTED: per-test cost {current_per_test * 1000:.2f}ms "
        f"exceeds {max_per_test * 1000:.2f}ms "
        f"(baseline {baseline_per_test * 1000:.2f}ms, "
        f"ratio {snapshot.threshold_ratio:.2f}).\n"
        f"Suite: {elapsed:.0f}s across {test_count} tests "
        f"(baseline {snapshot.baseline_secs:.0f}s across "
        f"{snapshot.baseline_test_count}).",
    )
    return True


def _check_absolute_regression(
    elapsed: float,
    *,
    snapshot: _BaselineSnapshot,
    env_max_allowed: float | None,
) -> bool:
    """Absolute-seconds fallback rail."""
    max_allowed = (
        env_max_allowed
        if env_max_allowed is not None
        else snapshot.baseline_secs + snapshot.threshold_secs
    )
    if elapsed <= max_allowed:
        return False
    delta = elapsed - snapshot.baseline_secs
    _print_regression_banner(
        f"REGRESSION DETECTED: suite took {elapsed:.0f}s, "
        f"baseline is {snapshot.baseline_secs:.0f}s (+{delta:.0f}s, "
        f"tolerance {snapshot.threshold_secs:.0f}s).",
    )
    return True


def _check_env_cap(elapsed: float, *, env_max_allowed: float | None) -> bool:
    """Env-cap hard rail.

    If the operator set an absolute ceiling (``UNIT_SUITE_MAX_SECONDS``)
    and we blew past it, fail regardless of the per-test ratio. The
    per-test branch still catches regressions within the cap.
    """
    if env_max_allowed is None or elapsed <= env_max_allowed:
        return False
    _print_regression_banner(
        f"REGRESSION DETECTED: suite took {elapsed:.0f}s, exceeds "
        f"UNIT_SUITE_MAX_SECONDS={env_max_allowed:.0f}s.",
    )
    return True


def _check_timing_regression(
    elapsed: float,
    *,
    run_all: bool,
    test_count: int | None,
) -> bool:
    """Return ``True`` when the run shows a timing regression.

    Only checks full-suite runs (``run_all=True``); affected-only runs
    vary widely and are not comparable to the baseline. Delegates the
    actual rail logic to ``_check_env_cap`` / ``_check_per_test_regression``
    / ``_check_absolute_regression`` so this orchestrator stays under
    the 50-line function limit.
    """
    if not run_all:
        return False
    snapshot = _load_baseline_snapshot()
    if snapshot is None:
        return False
    env_max_allowed = _parse_env_override()
    if _check_env_cap(elapsed, env_max_allowed=env_max_allowed):
        return True
    per_test = _check_per_test_regression(
        elapsed,
        snapshot=snapshot,
        test_count=test_count,
    )
    if per_test is not None:
        return per_test
    return _check_absolute_regression(
        elapsed,
        snapshot=snapshot,
        env_max_allowed=env_max_allowed,
    )


def _stream_pytest(cmd: list[str]) -> tuple[int, str]:
    """Run *cmd* as pytest, tee stdout, and return ``(returncode, stdout)``.

    Streams pytest stdout line-by-line so users see live progress
    (``subprocess.run`` + ``capture_output`` buffers everything until
    the process exits, which hides the ~90s full suite behind silence).
    We still tee into a buffer so the "N passed" summary line is
    available for the per-test regression rail.
    """
    with subprocess.Popen(
        cmd,
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as proc:
        stdout_lines: list[str] = []
        if proc.stdout is None:
            # subprocess.Popen with stdout=PIPE guarantees a pipe; this
            # branch would only fire if the Popen construction itself
            # silently produced no pipe handle, which indicates a
            # platform-level failure worth surfacing rather than
            # silencing with an assert.
            returncode = proc.wait()
            return returncode, ""
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            stdout_lines.append(line)
        returncode = proc.wait()
    return returncode, "".join(stdout_lines)


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
    returncode, captured_stdout = _stream_pytest(cmd)
    elapsed = time.monotonic() - start
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
