"""Integration tests for migration squash upgrade paths.

Verifies that databases at various migration points can upgrade
through an Atlas checkpoint created by the partial squash workflow.

The tests generate a small self-contained Atlas project with 6
migrations, squash the first 4 into a checkpoint, then verify that:

- A fresh database applies the checkpoint + remaining 2 files
- A database at the squash boundary (migration 4) applies the
  remaining 2 files, skipping the checkpoint
- A database past the squash point (migration 5) applies the last
  file, skipping the checkpoint
- A database before the squash point (migration 2) fails with a
  clear error (expected -- the individual files it needs are gone)
"""

import sqlite3
import subprocess
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# Incremental schema states for generating 6 migrations.
_SCHEMA_STEPS: tuple[str, ...] = (
    "CREATE TABLE t1 (id INTEGER PRIMARY KEY);",
    "CREATE TABLE t1 (id INTEGER PRIMARY KEY, name TEXT);",
    (
        "CREATE TABLE t1 (id INTEGER PRIMARY KEY, name TEXT);\n"
        "CREATE TABLE t2 (id INTEGER PRIMARY KEY);"
    ),
    (
        "CREATE TABLE t1 (id INTEGER PRIMARY KEY, name TEXT);\n"
        "CREATE TABLE t2 (id INTEGER PRIMARY KEY, ref INTEGER);"
    ),
    (
        "CREATE TABLE t1 (id INTEGER PRIMARY KEY, name TEXT);\n"
        "CREATE TABLE t2 (id INTEGER PRIMARY KEY, ref INTEGER);\n"
        "CREATE INDEX idx_t2_ref ON t2(ref);"
    ),
    (
        "CREATE TABLE t1 (id INTEGER PRIMARY KEY, name TEXT);\n"
        "CREATE TABLE t2 (id INTEGER PRIMARY KEY, ref INTEGER);\n"
        "CREATE INDEX idx_t2_ref ON t2(ref);\n"
        "CREATE TABLE t3 (id INTEGER PRIMARY KEY);"
    ),
)

_SQUASH_POINT = 4  # Squash first 4, keep last 2


def _to_url(path: Path, scheme: str = "file") -> str:
    """Convert a path to an Atlas-compatible URL with forward slashes."""
    return f"{scheme}://{PurePosixPath(PureWindowsPath(str(path)))}"


def _atlas(
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an Atlas CLI command.

    Retries up to 5 times on lock contention (Atlas uses a global
    lock for some operations, causing failures when multiple xdist
    workers invoke atlas concurrently).
    """
    result: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr=""
    )
    for attempt in range(5):
        result = subprocess.run(  # noqa: S603
            ["atlas", *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result
        if "lock" not in result.stderr.lower() or attempt == 4:
            break
        time.sleep(1 + attempt)
    if check and result.returncode != 0:
        msg = f"atlas {' '.join(args[:4])}: {result.stderr.strip()}"
        raise RuntimeError(msg)
    return result


def _generate_migrations(project_dir: Path) -> list[str]:
    """Generate 6 SQLite migrations from incremental schema changes.

    Inserts a 3-second pause between migration 4 and 5 to ensure
    there is at least a 2-second gap between their timestamps, which
    is needed for the checkpoint to have a unique timestamp between
    them.

    Uses a file-backed dev database to avoid lock contention when
    multiple xdist workers generate migrations concurrently.

    Returns the sorted list of .sql filenames.
    """
    revisions = project_dir / "revisions"
    revisions.mkdir(exist_ok=True)
    schema = project_dir / "schema.sql"
    dev_db = project_dir / "dev.db"
    dev_url = _to_url(dev_db, "sqlite")

    for i, ddl in enumerate(_SCHEMA_STEPS):
        if i == _SQUASH_POINT:
            time.sleep(3)
        schema.write_text(ddl)
        _atlas(
            "migrate",
            "diff",
            "--dev-url",
            dev_url,
            "--dir",
            _to_url(revisions),
            "--to",
            _to_url(schema),
            "--lock-timeout",
            "60s",
            f"m{i + 1}",
        )

    return sorted(f.name for f in revisions.glob("*.sql"))


def _build_squashed_dir(
    original_rev: Path,
    files: list[str],
    dest: Path,
) -> str:
    """Build a squashed revisions directory.

    Creates a checkpoint from the first ``_SQUASH_POINT`` files,
    renames it to sit between the last squashed and first kept
    file, then assembles the final directory.

    Returns the checkpoint filename.
    """
    dest.mkdir(exist_ok=True)

    # Copy first N files to a temp dir for checkpoint creation.
    partial = dest.parent / "partial_checkpoint"
    partial.mkdir(exist_ok=True)
    for name in files[:_SQUASH_POINT]:
        (partial / name).write_bytes((original_rev / name).read_bytes())
    _atlas("migrate", "hash", "--dir", _to_url(partial))

    # Create checkpoint using file-backed dev DB to avoid lock contention.
    cp_dev = dest.parent / "cp_dev.db"
    pre = {f.name for f in partial.glob("*.sql")}
    _atlas(
        "migrate",
        "checkpoint",
        "--dev-url",
        _to_url(cp_dev, "sqlite"),
        "--dir",
        _to_url(partial),
    )
    post = {f.name for f in partial.glob("*.sql")}
    cp_orig = sorted(post - pre)[0]

    # Compute checkpoint timestamp between m4 and m5.
    m4_ts = int(files[_SQUASH_POINT - 1][:14])
    m5_ts = int(files[_SQUASH_POINT][:14])
    cp_ts = m4_ts + 1
    assert cp_ts < m5_ts, f"No room for checkpoint between {m4_ts} and {m5_ts}"
    cp_name = f"{cp_ts}_checkpoint.sql"

    # Assemble squashed dir: checkpoint + remaining files.
    (dest / cp_name).write_bytes((partial / cp_orig).read_bytes())
    for name in files[_SQUASH_POINT:]:
        (dest / name).write_bytes((original_rev / name).read_bytes())
    _atlas("migrate", "hash", "--dir", _to_url(dest))

    return cp_name


def _apply(revisions: Path, db_path: Path, count: int | None = None) -> bool:
    """Apply migrations. Returns True on success."""
    cmd = [
        "migrate",
        "apply",
        "--dir",
        _to_url(revisions),
        "--url",
        _to_url(db_path, "sqlite"),
    ]
    if count is not None:
        cmd.append(str(count))
    result = _atlas(*cmd, check=False)
    return result.returncode == 0


def _tables(db_path: Path) -> list[str]:
    """Return user table names from a SQLite database."""
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'atlas%' "
            "ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows]


def _indexes(db_path: Path) -> list[str]:
    """Return user index names from a SQLite database."""
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' "
            "AND name NOT LIKE 'sqlite%' "
            "AND name NOT LIKE 'atlas%' "
            "ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows]


@pytest.fixture(scope="session")
def squash_project(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, list[str]]:
    """Create a project with 6 migrations and a squashed variant.

    Session-scoped so the expensive migration generation + checkpoint
    creation happens once, shared across all xdist workers.

    Returns (original_revisions, squashed_revisions, migration_files).
    """
    base = tmp_path_factory.mktemp("squash_project")
    project = base / "project"
    project.mkdir()
    files = _generate_migrations(project)
    original = project / "revisions"

    squashed = base / "squashed"
    _build_squashed_dir(original, files, squashed)

    return original, squashed, files


class TestMigrationSquashUpgradePaths:
    """Verify databases at various migration points upgrade through squash."""

    def test_fresh_db_applies_checkpoint_and_remaining(
        self,
        squash_project: tuple[Path, Path, list[str]],
        tmp_path: Path,
    ) -> None:
        """Fresh DB applies checkpoint + remaining 2 migrations."""
        _, squashed, _ = squash_project
        db = tmp_path / "fresh.db"

        assert _apply(squashed, db)
        assert _tables(db) == ["t1", "t2", "t3"]
        assert _indexes(db) == ["idx_t2_ref"]

    def test_db_at_squash_boundary_upgrades(
        self,
        squash_project: tuple[Path, Path, list[str]],
        tmp_path: Path,
    ) -> None:
        """DB at migration 4 (squash boundary) applies remaining 2."""
        original, squashed, _ = squash_project
        db = tmp_path / "boundary.db"

        assert _apply(original, db, count=_SQUASH_POINT)
        assert _tables(db) == ["t1", "t2"]

        assert _apply(squashed, db)
        assert _tables(db) == ["t1", "t2", "t3"]
        assert _indexes(db) == ["idx_t2_ref"]

    def test_db_past_squash_point_upgrades(
        self,
        squash_project: tuple[Path, Path, list[str]],
        tmp_path: Path,
    ) -> None:
        """DB at migration 5 (past squash) applies remaining 1."""
        original, squashed, _ = squash_project
        db = tmp_path / "past.db"

        assert _apply(original, db, count=_SQUASH_POINT + 1)
        assert _tables(db) == ["t1", "t2"]
        assert _indexes(db) == ["idx_t2_ref"]

        assert _apply(squashed, db)
        assert _tables(db) == ["t1", "t2", "t3"]

    def test_db_before_squash_point_fails(
        self,
        squash_project: tuple[Path, Path, list[str]],
        tmp_path: Path,
    ) -> None:
        """DB at migration 2 (before squash) fails -- files are gone."""
        original, squashed, _ = squash_project
        db = tmp_path / "old.db"

        assert _apply(original, db, count=2)
        assert _tables(db) == ["t1"]

        assert not _apply(squashed, db)

    def test_squash_script_below_threshold(self) -> None:
        """Squash script reports 'below threshold' for both backends."""
        # The bash subprocess may not have atlas on PATH (Windows
        # Git Bash vs. system PATH).  Skip when unavailable.
        probe = subprocess.run(
            ["bash", "-c", "command -v atlas"],  # noqa: S607
            capture_output=True,
            check=False,
        )
        if probe.returncode != 0:
            pytest.skip("atlas not available in bash PATH")

        result = subprocess.run(
            ["bash", "scripts/squash_migrations.sh"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "Below threshold" in result.stdout
        assert "sqlite" in result.stdout.lower()
        assert "postgres" in result.stdout.lower()
