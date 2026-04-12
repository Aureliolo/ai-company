"""Root test configuration and shared fixtures."""

import contextlib
import json
import logging
import os
import shutil
import sys
import time
from collections.abc import AsyncGenerator, Iterable
from pathlib import Path

import aiosqlite
import pytest
import structlog
from hypothesis import HealthCheck, settings
from hypothesis.database import (
    DirectoryBasedExampleDatabase,
    ExampleDatabase,
    MultiplexedDatabase,
)

from synthorg.persistence import atlas


class _WriteOnlyDatabase(ExampleDatabase):
    """Wraps a database so it only receives writes -- fetch returns nothing.

    Used for the shared failure log: we want to capture every failing
    example for later analysis, but never replay them automatically
    (that would block all worktrees until someone fixes the bug).
    """

    def __init__(self, db: ExampleDatabase) -> None:
        super().__init__()
        self._db = db

    def save(self, key: bytes, value: bytes) -> None:
        self._db.save(key, value)

    def fetch(self, key: bytes) -> Iterable[bytes]:
        return iter(())

    def delete(self, key: bytes, value: bytes) -> None:
        pass  # No-op: shared DB is a failure log, never delete entries

    def move(
        self,
        src: bytes,
        dest: bytes,
        value: bytes,
    ) -> None:
        self._db.save(dest, value)  # Treat as save-to-dest (preserve the entry)


# ── Hypothesis shared example database ──────────────────────────
# Failing examples are written to a central directory outside any
# worktree so they survive worktree deletion.  The shared DB is
# write-only: failures are logged for analysis but never replayed
# automatically (that would block all test runs until fixed).
# Review captured failures with: ls ~/.synthorg/hypothesis-examples/
_local_db = DirectoryBasedExampleDatabase(".hypothesis/examples/")

try:
    _shared_dir = Path.home() / ".synthorg" / "hypothesis-examples"
    _shared_dir.mkdir(parents=True, exist_ok=True)
    _shared_db: ExampleDatabase = _WriteOnlyDatabase(
        DirectoryBasedExampleDatabase(str(_shared_dir)),
    )
    _local_combined_db = MultiplexedDatabase(_local_db, _shared_db)
except OSError:
    # HOME unwritable (containerized CI, read-only filesystem) --
    # fall back to local-only DB.  Failures still captured in
    # .hypothesis/examples/ for the duration of this worktree.
    _local_combined_db = MultiplexedDatabase(_local_db)

settings.register_profile(
    "ci",
    # Deterministic: derandomize=True uses a fixed seed per test function,
    # so the same 10 examples run every time.  Not random, not skipped.
    max_examples=10,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "dev",
    max_examples=1000,
    database=_local_combined_db,
)
settings.register_profile(
    "fuzz",
    # Dedicated long-running fuzzing sessions -- run locally or on a
    # schedule.  High example count + no deadline to explore deep
    # input spaces.  Failures captured to shared DB for analysis.
    # Suppress health checks so Hypothesis doesn't abandon slow or
    # heavily-filtered tests before reaching max_examples.
    # IMPORTANT: also pass --timeout=0 to pytest to disable the
    # per-test wall-clock limit (the default 30s kills 10k runs).
    max_examples=10_000,
    deadline=None,
    suppress_health_check=list(HealthCheck),
    database=_local_combined_db,
)
settings.register_profile(
    "extreme",
    # Deep overnight fuzzing -- 500k examples per test, no deadline,
    # no health checks, no seed (true randomness).  Expect hours.
    max_examples=500_000,
    deadline=None,
    suppress_health_check=list(HealthCheck),
    database=_local_combined_db,
)
# Configure Hypothesis globally for the test session.
# Override by setting HYPOTHESIS_PROFILE=dev in the environment.
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

# ── Vendor-agnostic guardrail ───────────────────────────────────
# Centralized set of disallowed vendor identifiers so tests that
# scan for vendor names do not embed the literals themselves.
DISALLOWED_VENDOR_NAMES: frozenset[str] = frozenset(
    {"anthropic", "openai", "claude", "gpt", "gemini", "mistral"}
)

# ── Slow test guardrail ──────────────────────────────────────────
# Fail any unit test whose *total* wall-clock time (setup + call +
# teardown) exceeds this threshold.  This catches regressions like
# backup-service filesystem I/O in fixtures before they snowball
# into 10-minute test runs.  Integration and e2e tests are exempt.
# Disabled for fuzz profile where 10k examples per test routinely
# exceed the limit.
_UNIT_TEST_WALL_CLOCK_LIMIT = 8.0  # seconds
_FUZZ_PROFILE_ACTIVE = os.environ.get("HYPOTHESIS_PROFILE") in ("fuzz", "extreme")
_start_key = pytest.StashKey[float]()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Record wall-clock start time before each test."""
    item.stash[_start_key] = time.monotonic()


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Fail unit tests that exceed the wall-clock limit."""
    start = item.stash.get(_start_key, None)
    if start is None:
        return
    elapsed = time.monotonic() - start
    if (
        not _FUZZ_PROFILE_ACTIVE
        and item.get_closest_marker("unit")
        and elapsed > _UNIT_TEST_WALL_CLOCK_LIMIT
    ):
        pytest.fail(
            f"Unit test exceeded {_UNIT_TEST_WALL_CLOCK_LIMIT}s "
            f"wall-clock limit ({elapsed:.1f}s). This usually means "
            f"a fixture is doing heavy I/O -- check setup/teardown.",
            pytrace=False,
        )


# ── Suite-level regression guard ─────────────────────────────────
# Compares total wall-clock time against the committed baseline in
# tests/baselines/unit_timing.json.  Fires after every full suite
# run (locally, in pre-push hooks, in CI).  When a regression is
# detected, prints a loud warning so the cause is investigated
# instead of "fixing" by deleting tests or bypassing hooks.
_BASELINE_PATH = Path(__file__).parent / "baselines" / "unit_timing.json"
_suite_start: float | None = None


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    """Record suite start time for regression detection."""
    global _suite_start  # noqa: PLW0603
    _suite_start = time.monotonic()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    """Warn loudly if the unit suite regressed beyond the baseline."""
    if _suite_start is None or _FUZZ_PROFILE_ACTIVE:
        return
    # Only check when running unit tests (not integration/e2e-only).
    if not any(item.get_closest_marker("unit") for item in session.items):
        return
    elapsed = time.monotonic() - _suite_start
    if not _BASELINE_PATH.exists():
        return
    try:
        baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        baseline_secs = float(baseline["unit_suite_seconds"])
        baseline_count = int(baseline.get("test_count", 0))
        threshold_pct = float(baseline.get("regression_threshold_pct", 30))
    except json.JSONDecodeError, KeyError, ValueError, OSError:
        return  # Malformed baseline -- skip check, don't block.
    # Only compare against baseline when running (roughly) the full
    # suite.  Partial runs have very different timing profiles and
    # would produce noisy false positives.
    unit_count = sum(1 for item in session.items if item.get_closest_marker("unit"))
    if baseline_count and unit_count < baseline_count * 0.8:
        return
    max_allowed = baseline_secs * (1 + threshold_pct / 100)
    # Allow override for optimization work where the suite is
    # intentionally being re-measured at a new (lower) baseline.
    env_override = os.environ.get("UNIT_SUITE_MAX_SECONDS")
    if env_override is not None:
        with contextlib.suppress(ValueError):
            max_allowed = float(env_override)
    if elapsed > max_allowed:
        pct = (elapsed - baseline_secs) / baseline_secs * 100
        border = "!" * 60
        msg = (
            f"\n{border}\n"
            f"REGRESSION DETECTED: suite took {elapsed:.0f}s, "
            f"baseline is {baseline_secs:.0f}s (+{pct:.0f}%)\n"
            f"Run A/B against origin/main before fixing anything.\n"
            f"Do NOT delete tests or use --no-verify.\n"
            f"{border}\n"
        )
        print(msg, file=sys.stderr)  # noqa: T201


def clear_logging_state() -> None:
    """Clear structlog context and stdlib root handlers.

    Shared helper for observability test fixtures that need to reset
    logging state between tests.
    """
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)


_TEMPLATE_DB: Path | None = None
"""Session-wide migrated template DB.  Created once, copied per test."""


async def _get_template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return path to the session-wide migrated template database.

    Migrates a fresh SQLite file via Atlas on first call, then
    reuses the same file for all subsequent calls.  Each test
    copies this file instead of spawning a new Atlas subprocess.
    """
    global _TEMPLATE_DB  # noqa: PLW0603
    if _TEMPLATE_DB is not None:
        return _TEMPLATE_DB
    base = tmp_path_factory.mktemp("atlas_template")
    db_path = base / "template.db"
    rev_url = atlas.copy_revisions(base / "revisions")
    await atlas.migrate_apply(
        atlas.to_sqlite_url(str(db_path)),
        revisions_url=rev_url,
        skip_lock=True,
    )
    _TEMPLATE_DB = db_path
    return _TEMPLATE_DB


@pytest.fixture
async def migrated_db(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncGenerator[aiosqlite.Connection]:
    """Temp-file SQLite connection with Atlas migrations applied.

    Copies a session-wide template database instead of spawning
    an Atlas subprocess per test -- eliminates ~hundreds of Go
    process launches during a full test run.
    """
    template = await _get_template_db(tmp_path_factory)
    db_path = tmp_path / "test.db"
    shutil.copy2(str(template), str(db_path))
    db = await aiosqlite.connect(str(db_path))
    try:
        db.row_factory = aiosqlite.Row
        yield db
    finally:
        await db.close()
